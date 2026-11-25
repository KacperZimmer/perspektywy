from collections import defaultdict
from contextlib import contextmanager
import json
import logging
import re
from typing import Any, Callable, Dict, Generator, List, Optional

from django.core.management.base import BaseCommand
from django.db import DatabaseError, connection, transaction
import feedparser
import numpy as np
import requests

from analytics_engine.create_embeddings import (
    generate_embeddings,
    prepare_texts_for_embedding,
)
from analytics_engine.llm import News_LLM
from analytics_engine.sources_config import SOURCES

logger = logging.getLogger(__name__)

POLITE_HEADERS = {"User-Agent": "KontekstBot/1.0 (+http://horyzonty.pl)"}
HTML_TAG_REGEX = re.compile(r"<.*?>")
DEFAULT_DISTANCE_THRESHOLD = 0.30


class DatabaseManager:
    @contextmanager
    def get_cursor(self) -> Generator[Any, None, None]:
        try:
            with transaction.atomic():
                with connection.cursor() as cur:
                    yield cur
        except DatabaseError as e:
            logger.error("Błąd bazy danych: %s", e)
            raise

    def get_publisher_map(self) -> Dict[str, int]:
        with self.get_cursor() as cur:
            cur.execute("SELECT name, id FROM stories_publisher;")
            return {name: pub_id for name, pub_id in cur.fetchall()}


def clean_html(raw_html: Optional[str]) -> str:
    if not raw_html:
        return ""
    text = re.sub(HTML_TAG_REGEX, "", raw_html)
    return " ".join(text.split())


def extract_tags(raw_tags: Any) -> List[str]:
    if isinstance(raw_tags, list):
        return [str(tag).strip() for tag in raw_tags if tag]
    if isinstance(raw_tags, str):
        match = re.search(r"\[.*?\]", raw_tags, re.DOTALL)
        json_str = match.group(0) if match else raw_tags.strip()
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                return [str(tag).strip() for tag in parsed if tag]
        except json.JSONDecodeError:
            pass
    return []


class ClusterEnricher:
    def __init__(self, db: DatabaseManager, llm: News_LLM) -> None:
        self.db = db
        self.llm = llm

    def enrich_summaries(self, min_articles: int = 5) -> None:
        query = """
            SELECT c.id, json_agg(e.article_description) AS descriptions
            FROM clusters c
            JOIN embedded_articles e ON c.id = e.cluster_id
            WHERE c.ai_summary IS NULL
            GROUP BY c.id
            HAVING COUNT(e.id) >= %s;
        """
        with self.db.get_cursor() as cur:
            cur.execute(query, (min_articles,))
            clusters = cur.fetchall()

        if not clusters:
            return

        updates = [(self.llm.generate_summary(content), cid) for cid, content in clusters]
        with self.db.get_cursor() as cur:
            cur.executemany("UPDATE clusters SET ai_summary = %s WHERE id = %s;", updates)

    def enrich_titles(self, min_articles: int = 5) -> None:
        query = """
            SELECT c.id, array_agg(a.article_description ORDER BY a.id) as article_descriptions
            FROM embedded_articles a
            JOIN clusters c ON a.cluster_id = c.id
            WHERE c.title IS NULL
            GROUP BY c.id
            HAVING count(a.cluster_id) >= %s;
        """
        with self.db.get_cursor() as cur:
            cur.execute(query, (min_articles,))
            clusters = cur.fetchall()

        if not clusters:
            return

        updates = [(self.llm.generate_title(content), cid) for cid, content in clusters]
        with self.db.get_cursor() as cur:
            cur.executemany("UPDATE clusters SET title = %s WHERE id = %s;", updates)

    def enrich_tags(self, min_articles: int = 5) -> None:
        query = """
            SELECT c.id, c.ai_summary
            FROM clusters c
            JOIN embedded_articles e ON c.id = e.cluster_id
            WHERE (c.tags IS NULL OR cardinality(c.tags) = 0 OR c.tags = '{}')
              AND c.ai_summary IS NOT NULL
            GROUP BY c.id, c.ai_summary
            HAVING COUNT(e.id) >= %s;
        """
        with self.db.get_cursor() as cur:
            cur.execute(query, (min_articles,))
            clusters = cur.fetchall()

        if not clusters:
            return

        updates = []
        for cluster_id, summary in clusters:
            raw_tags = self.llm.tag_cluster(summary)
            clean_tags = extract_tags(raw_tags)
            if clean_tags:
                updates.append((clean_tags, cluster_id))

        if updates:
            with self.db.get_cursor() as cur:
                cur.executemany("UPDATE clusters SET tags = %s WHERE id = %s;", updates)


def save_data_to_postgres(
    db_manager: DatabaseManager,
    embeddings_array: np.ndarray,
    article_list: List[Dict[str, Any]],
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
) -> None:
    embeddings = embeddings_array.tolist()

    find_cluster_query = """
        SELECT id, (centroid <=> %s::vector) AS distance
        FROM clusters
        ORDER BY distance ASC
        LIMIT 1;
    """
    insert_cluster_query = "INSERT INTO clusters (centroid) VALUES (%s::vector) RETURNING id;"
    touch_cluster_query = "UPDATE clusters SET updated_at = current_timestamp WHERE id = %s;"
    insert_article_query = """
        INSERT INTO embedded_articles (cluster_id, title, url, source, embedding, publisher_id, article_description)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING;
    """

    with db_manager.get_cursor() as cur:
        for idx, article in enumerate(article_list):
            embedding = embeddings[idx]
            cur.execute(find_cluster_query, (embedding,))
            nearest = cur.fetchone()

            if nearest and nearest[1] <= distance_threshold:
                cluster_id = nearest[0]
                cur.execute(touch_cluster_query, (cluster_id,))
            else:
                cur.execute(insert_cluster_query, (embedding,))
                cluster_id = cur.fetchone()[0]

            cur.execute(
                insert_article_query,
                (
                    cluster_id,
                    article["title"],
                    article["url"],
                    article["source_name"],
                    embedding,
                    article["publisher_db_id"],
                    article["description"],
                ),
            )


def process_batch(
    db_manager: DatabaseManager,
    batch: List[Dict[str, Any]],
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
) -> None:
    if not batch:
        return
    clean_texts = prepare_texts_for_embedding(batch)
    embeddings = generate_embeddings(clean_texts)
    save_data_to_postgres(db_manager, embeddings, batch, distance_threshold=distance_threshold)


def aggregate_news_articles(
    db_manager: DatabaseManager,
    sources: List[Dict[str, Any]],
    batch_size: int = 20,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
) -> None:
    publisher_map = db_manager.get_publisher_map()
    batch = []

    for source in sources:
        if source.get("type") != "rss":
            continue

        try:
            response = requests.get(source["url"], headers=POLITE_HEADERS, timeout=10)
            feed = feedparser.parse(response.content)
        except Exception as e:
            logger.warning("Błąd sieci dla %s: %s", source.get("name"), e)
            continue

        for entry in feed.entries:
            article_url = entry.get("link")
            if not article_url:
                continue

            pub_name = source.get("name")
            publisher_id = publisher_map.get(pub_name)
            if not publisher_id:
                continue

            title = entry.get("title", "Brak tytułu")
            summary = clean_html(entry.get("summary", ""))[:300]
            if len(summary) == 300:
                summary += "..."

            batch.append({
                "source_id": source.get("id"),
                "source_name": pub_name,
                "publisher_db_id": publisher_id,
                "bias": source.get("bias", "unknown"),
                "title": title,
                "url": article_url,
                "text_for_embedding": f"{title}. {summary}",
                "description": clean_html(entry.get("description", "")),
            })

            if len(batch) >= batch_size:
                process_batch(db_manager, batch, distance_threshold=distance_threshold)
                batch.clear()

    if batch:
        process_batch(db_manager, batch, distance_threshold=distance_threshold)


def print_db_clusters(db_manager: DatabaseManager, write: Callable[[str], Any] = print) -> None:
    query = """
        SELECT c.id, a.source, a.title
        FROM clusters c
        JOIN embedded_articles a ON c.id = a.cluster_id
        ORDER BY c.updated_at DESC;
    """
    with db_manager.get_cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    if not rows:
        return

    clusters = defaultdict(list)
    for cluster_id, source, title in rows:
        clusters[cluster_id].append({"source": source, "title": title})

    sorted_clusters = sorted(
        clusters.items(),
        key=lambda item: (len(set(x["source"] for x in item[1])), len(item[1])),
        reverse=True,
    )

    for cluster_id, articles in sorted_clusters:
        sources = {a["source"] for a in articles}
        if len(sources) == 1:
            label = "POJEDYNCZY NEWS" if len(articles) == 1 else f"ŚLEPY PUNKT [{next(iter(sources))}]"
            write(f"\n{label} (ID: {cluster_id}):")
        else:
            write(f"\nGŁÓWNY TEMAT (ID: {cluster_id}) [{len(sources)} źródeł, {len(articles)} artykułów]:")

        for article in articles:
            write(f"  - [{article['source']}] {article['title']}")


class Command(BaseCommand):
    help = "Scrape RSS news articles, generate embeddings, cluster them, and enrich clusters with LLM summaries, titles, and tags."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--batch-size",
            type=int,
            default=20,
            help="Number of articles to embed and insert per batch (default: 20).",
        )
        parser.add_argument(
            "--min-articles",
            type=int,
            default=5,
            help="Minimum number of articles in a cluster before LLM enrichment (default: 5).",
        )
        parser.add_argument(
            "--model",
            type=str,
            default="qwen3.6:35b",
            help="Ollama model name for cluster enrichment (default: qwen3.6:35b).",
        )
        parser.add_argument(
            "--distance-threshold",
            type=float,
            default=DEFAULT_DISTANCE_THRESHOLD,
            help=f"Cosine distance threshold for assigning articles to existing clusters (default: {DEFAULT_DISTANCE_THRESHOLD}).",
        )
        parser.add_argument(
            "--skip-enrichment",
            action="store_true",
            help="Skip LLM summary, title, and tag enrichment.",
        )
        parser.add_argument(
            "--no-print",
            action="store_true",
            help="Do not print the resulting clusters at the end.",
        )

    def handle(self, *args, **options) -> None:
        batch_size = options["batch_size"]
        min_articles = options["min_articles"]
        model_name = options["model"]
        distance_threshold = options["distance_threshold"]
        skip_enrichment = options["skip_enrichment"]
        no_print = options["no_print"]

        db_manager = DatabaseManager()

        self.stdout.write(self.style.NOTICE("Aggregating and embedding news articles..."))
        aggregate_news_articles(
            db_manager,
            SOURCES,
            batch_size=batch_size,
            distance_threshold=distance_threshold,
        )

        if not skip_enrichment:
            llm_news = News_LLM(model_name)
            enricher = ClusterEnricher(db_manager, llm_news)

            self.stdout.write(self.style.NOTICE("Enriching cluster summaries..."))
            enricher.enrich_summaries(min_articles=min_articles)

            self.stdout.write(self.style.NOTICE("Enriching cluster titles..."))
            enricher.enrich_titles(min_articles=min_articles)

            self.stdout.write(self.style.NOTICE("Enriching cluster tags..."))
            enricher.enrich_tags(min_articles=min_articles)

        if not no_print:
            print_db_clusters(db_manager, write=self.stdout.write)

        self.stdout.write(self.style.SUCCESS("Database loading pipeline completed."))
