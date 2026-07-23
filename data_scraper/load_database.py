from collections import defaultdict

import feedparser
import numpy as np
import psycopg2
import requests
import re

from data_scraper.test_sources import SOURCES
from analytics_engine.create_embeddings import (
    prepare_texts_for_embedding,
    generate_embeddings,
)

POLITE_HEADERS = {'User-Agent': 'KontekstBot/1.0 (+http://twojadomena.pl)'}


def clean_html(raw_html: str) -> str:
    """Usuwa tagi HTML z opisów w kanałach RSS, zostawiając czysty tekst."""
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return " ".join(cleantext.split())


def print_db_clusters() -> None:
    conn = None
    try:
        conn = psycopg2.connect(host='localhost', database='kontekst_db', user='newuser', password='password')
        cur = conn.cursor()

        query = """
            SELECT c.id, a.source, a.title
            FROM clusters c
            JOIN embedded_articles a ON c.id = a.cluster_id
            ORDER BY c.updated_at DESC;
        """
        cur.execute(query)
        rows = cur.fetchall()

        if not rows:
            print("Brak danych w bazie. Uruchom najpierw scraper!")
            return

        clusters = defaultdict(list)
        for cluster_id, source, title in rows:
            clusters[cluster_id].append({'source': source, 'title': title})

        print("\n" + "=" * 65)
        print(" AKTUALNY STAN KLASTRÓW W BAZIE (GROUND NEWS PL)")
        print("=" * 65)


        sorted_clusters = sorted(
            clusters.items(),
            key=lambda item: (len(set(x['source'] for x in item[1])), len(item[1])),
            reverse=True
        )

        for cluster_id, articles in sorted_clusters:
            unique_sources = set(article['source'] for article in articles)

            if len(unique_sources) == 1:
                if len(articles) == 1:
                    print(f"\n⚫ POJEDYNCZY NEWS (ID Klastra: {cluster_id}):")
                else:
                    source_name = list(unique_sources)[0]
                    print(f"\n🟡 ŚLEPY PUNKT / TEMAT LOKALNY (ID: {cluster_id}) - Zdominowany przez [{source_name}]:")
            else:
                print(
                    f"\n🟢 GŁÓWNY TEMAT (ID Klastra: {cluster_id}) [{len(unique_sources)} różnych źródeł, łącznie {len(articles)} artykułów]:")

            for article in articles:
                print(f"  - [{article['source']}] {article['title']}")

        print("\n" + "=" * 65)

    except psycopg2.Error as e:
        print(f"Błąd bazy danych podczas pobierania klastrów: {e}")
    except Exception as e:
        print(f"Błąd ogólny: {e}")
    finally:
        if conn:
            conn.close()
def save_data_to_postgres(embeddings_array: np.ndarray, article_list: list) -> None:
    DISTANCE_THRESHOLD = 0.30

    conn = None
    try:
        conn = psycopg2.connect(host='localhost', database='kontekst_db', user='newuser', password='password')
        cur = conn.cursor()

        embeddings_array_as_list = embeddings_array.tolist()

        for idx, article in enumerate(article_list):
            title = article['title']
            url = article['url']
            source_name = article['source_name']
            embedding = embeddings_array_as_list[idx]

            find_cluster_query = """
                SELECT id, (centroid <=> %s::vector) AS distance
                FROM clusters
                ORDER BY distance ASC
                LIMIT 1;
            """
            cur.execute(find_cluster_query, (embedding,))
            nearest_cluster = cur.fetchone()

            cluster_id = None

            if nearest_cluster and nearest_cluster[1] <= DISTANCE_THRESHOLD:
                cluster_id = nearest_cluster[0]
                cur.execute("UPDATE clusters SET updated_at = current_timestamp WHERE id = %s", (cluster_id,))
            else:
                insert_cluster_query = """
                    INSERT INTO clusters (centroid)
                    VALUES (%s::vector)
                    RETURNING id;
                """
                cur.execute(insert_cluster_query, (embedding,))
                cluster_id = cur.fetchone()[0]

            insert_article_query = """
                INSERT INTO embedded_articles (cluster_id, title, url, source, embedding) 
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING;
            """
            cur.execute(insert_article_query, (cluster_id, title, url, source_name, embedding))

        conn.commit()
        print(f"✅ Zapisano pomyślnie paczkę {len(article_list)} artykułów do bazy.")

    except psycopg2.Error as e:
        print(f"Błąd bazy danych: {e}")
    except Exception as e:
        print(f"Błąd ogólny: {e}")
    finally:
        if conn:
            conn.close()

def create_init_db():

    create_table_articles_command = """
          CREATE TABLE IF NOT EXISTS embedded_articles(
              id bigserial primary key,
              cluster_id bigint references clusters(id),
              title text,
              url text UNIQUE,
              source text,
              embedding vector(1024),
              created_at timestamp default current_timestamp
          );
      """

    create_table_clusters_command = """
        CREATE TABLE IF NOT EXISTS clusters(
            id bigserial primary key, 
            centroid vector(1024),
            created_at timestamp default current_timestamp,
            updated_at timestamp default current_timestamp
        );    
    """

    conn = None
    try:
        conn = psycopg2.connect(
            host='localhost',
            database='kontekst_db',
            user='newuser',
            password='password'
        )
        cur = conn.cursor()
        cur.execute(create_table_clusters_command)

        cur.execute(create_table_articles_command)
        conn.commit()
        print("✅ Tabela embedded_articles utworzona pomyślnie.")
    except Exception as e:
        print(f"❌ Nieoczekiwany błąd podczas tworzenia tabeli: {e}")
    finally:
        if conn:
            conn.close()


def agg_news_artictles(data_news_companies_map, num_of_data_to_collect: int):
    collected_data = []

    for source in data_news_companies_map:
        if source.get('type') != 'rss':
            continue

        try:
            response = requests.get(source['url'], headers=POLITE_HEADERS, timeout=10)
            feed = feedparser.parse(response.content)
        except Exception as e:
            print(f"Błąd sieci dla {source['name']}: {e}")
            continue

        print(f"\nPrzeszukuję: {source['name']}...")

        for entry in feed.entries:
            article_title = entry.get("title", "Brak tytułu")
            article_url = entry.get("link")

            if not article_url:
                continue

            print(f"  -> Ekstrakcja nagłówka: {article_title}")

            raw_summary = entry.get("summary", "")
            clean_summary = clean_html(raw_summary)

            if len(clean_summary) > 300:
                clean_summary = clean_summary[:300] + "..."

            text_for_embedding = f"{article_title}. {clean_summary}"

            collected_data.append({
                "source_id": source.get("id"),
                "source_name": source.get("name"),
                "bias": source.get("bias", "unknown"),
                "title": article_title,
                "url": article_url,
                "text_for_embedding": text_for_embedding
            })

            if len(collected_data) >= num_of_data_to_collect:
                clean_data = prepare_texts_for_embedding(collected_data)
                embeddings = generate_embeddings(clean_data)
                save_data_to_postgres(embeddings, collected_data)

                collected_data = []

    if len(collected_data) > 0:
        print(f"\nZapisuję ostatnią paczkę ({len(collected_data)} artykułów)...")
        clean_data = prepare_texts_for_embedding(collected_data)
        embeddings = generate_embeddings(clean_data)
        save_data_to_postgres(embeddings, collected_data)


create_init_db()
agg_news_artictles(SOURCES, 20)
print_db_clusters()