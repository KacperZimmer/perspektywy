from collections import defaultdict
from contextlib import contextmanager
import json
import logging
import os
import re
from typing import Any, Dict, Generator, List, Optional

import feedparser
import numpy as np
import psycopg2
from psycopg2.extensions import cursor as PgCursor
import requests

from analytics_engine.create_embeddings import (
    generate_embeddings,
    prepare_texts_for_embedding,
)
from analytics_engine.llm import News_LLM
from analytics_engine.sources_config import SOURCES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

POLITE_HEADERS = {"User-Agent": "KontekstBot/1.0 (+http://horyzonty.pl)"}
HTML_TAG_REGEX = re.compile(r"<.*?>")
DISTANCE_THRESHOLD = 0.30


class DatabaseManager:
    def __init__(self, host: str, database: str, user: str, password: str) -> None:
        self.host = host
        self.database = database
        self.user = user
        self.password = password

    @contextmanager
    def get_cursor(self) -> Generator[PgCursor, None, None]:
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
            )
            with conn:
                with conn.cursor() as cur:
                    yield cur
        except psycopg2.Error as e:
            logging.error(f"Błąd bazy danych: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def get_publisher_map(self) -> Dict[str, int]:
        with self.get_cursor() as cur:
            cur.execute("SELECT name, id FROM stories_publisher;")
            return {name: pub_id for name, pub_id in cur.fetchall()}


db_manager = DatabaseManager(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "kontekst_db"),
    user=os.getenv("DB_USER", "newuser"),
    password=os.getenv("DB_PASSWORD", "password"),
)
llm_news = News_LLM("qwen3.6:35b")


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


def save_data_to_postgres(embeddings_array: np.ndarray, article_list: List[Dict[str, Any]]) -> None:
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

            if nearest and nearest[1] <= DISTANCE_THRESHOLD:
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


def process_batch(batch: List[Dict[str, Any]]) -> None:
    if not batch:
        return
    clean_texts = prepare_texts_for_embedding(batch)
    embeddings = generate_embeddings(clean_texts)
    save_data_to_postgres(embeddings, batch)


def aggregate_news_articles(sources: List[Dict[str, Any]], batch_size: int = 20) -> None:
    publisher_map = db_manager.get_publisher_map()
    batch = []

    for source in sources:
        if source.get("type") != "rss":
            continue

        try:
            response = requests.get(source["url"], headers=POLITE_HEADERS, timeout=10)
            feed = feedparser.parse(response.content)
        except Exception as e:
            logging.warning(f"Błąd sieci dla {source.get('name')}: {e}")
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
                process_batch(batch)
                batch.clear()

    if batch:
        process_batch(batch)


def print_db_clusters() -> None:
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
            print(f"\n{label} (ID: {cluster_id}):")
        else:
            print(f"\nGŁÓWNY TEMAT (ID: {cluster_id}) [{len(sources)} źródeł, {len(articles)} artykułów]:")

        for article in articles:
            print(f"  - [{article['source']}] {article['title']}")


def run_pipeline() -> None:
    enricher = ClusterEnricher(db_manager, llm_news)

    aggregate_news_articles(SOURCES, batch_size=20)
    enricher.enrich_summaries()
    enricher.enrich_titles()
    enricher.enrich_tags()

    print_db_clusters()


if __name__ == "__main__":
    run_pipeline()