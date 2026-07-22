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


def save_data_to_postgres(embeddings_array: np.ndarray, article_list: list) -> None:
    sql_to_insert_into_db = """
    INSERT INTO embedded_articles (title, url, source, embedding) 
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (url) DO NOTHING;
    """

    data_to_insert = []
    embeddings_array_as_list = embeddings_array.tolist()

    for idx in range(len(article_list)):
        source_name = article_list[idx]['source_name']
        title = article_list[idx]['title']
        url = article_list[idx]['url']
        single_embedding_for_article = embeddings_array_as_list[idx]

        data_to_insert.append(
            (title, url, source_name, single_embedding_for_article)
        )

    conn = None
    try:
        conn = psycopg2.connect(host='localhost', database='kontekst_db', user='newuser', password='password')
        cur = conn.cursor()

        cur.executemany(
            sql_to_insert_into_db,
            data_to_insert
        )
        conn.commit()
        print(f"✅ Próba zapisu {len(data_to_insert)} artykułów zakończona (nowe zapisane, duplikaty pominięte).")

    except psycopg2.OperationalError as e:
        print(f"Błąd operacyjny: {e}")
    except psycopg2.ProgrammingError as e:
        print(f"Błąd programistyczny: {e}")
    except Exception as e:
        print(f'Błąd ogólny: {e}')
    finally:
        if conn:
            conn.close()


def create_init_db():
    create_table_command = """
          CREATE TABLE IF NOT EXISTS embedded_articles(
              id bigserial primary key,
              title text,
              url text UNIQUE,
              source text,
              embedding vector(1024)
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
        cur.execute(create_table_command)
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
            # Pobieramy feed RSS przy pomocy własnych nagłówków
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

            # Podstawa dla wektorów: Tytuł + zajawka
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


# Uruchomienie
create_init_db()
agg_news_artictles(SOURCES, 20)