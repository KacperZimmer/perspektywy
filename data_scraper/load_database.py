import feedparser
import psycopg2
import requests
import trafilatura
import json

from psycopg2._psycopg import cursor
from trafilatura import extract
from configparser import ConfigParser

from data_scraper.test_sources import SOURCES, headers
from analytics_engine.create_embeddings import (
    prepare_texts_for_embedding,
    generate_embeddings,
)

def create_init_db():
      create_table_command = """
          CREATE TABLE IF NOT EXISTS embedded_articles(
              id bigserial primary key,
              title text,
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
          cur.close()
          conn.commit()

          print("✅ Tabela embedded_articles utworzona pomyślnie.")
      except psycopg2.OperationalError as e:
          print(f"❌ Błąd połączenia z bazą: {e}")
      except psycopg2.ProgrammingError as e:
          print(f"❌ Błąd polecenia SQL: {e}")
      except Exception as e:
          print(f"❌ Nieoczekiwany błąd: {e}")
      finally:
          if conn:
              conn.close()
              print("🔌 Połączenie zamknięte.")



def connect(config):
    """ Connect to the PostgreSQL database server """
    try:
        with psycopg2.connect(**config) as conn:
            print('Connected to the PostgreSQL server.')
            return conn
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


def agg_news_artictles(data_news_companies_map):
    collected_data = []

    for source in data_news_companies_map:

        if len(collected_data) >= 100:
            clean_data = prepare_texts_for_embedding(collected_data)
            generate_embeddings(clean_data)

            collected_data = []
        if source.get('type') != 'rss':
            continue

        try:
            response = requests.get(source['url'], headers=headers, timeout=10)
            feed = feedparser.parse(response.content)
        except Exception as e:
            print(f"Błąd sieci dla {source['name']}: {e}")
            continue

        print(f"\nPrzeszukuję: {source['name']}...")


        for entry in feed.entries:

            print(f"  -> Ekstrakcja: {entry.link}")

            downloaded = trafilatura.fetch_url(entry.link)

            if not downloaded:
                print("     (Nie udało się pobrać HTML)")
                continue

            metadata = extract(downloaded, output_format="json", with_metadata=True)

            if not metadata:
                print("     (Błąd ekstrakcji)")
                continue

            data = json.loads(metadata)
            text = data.get('text')

            if not text:
                print("(Brak treści w artykule)")
                continue

            collected_data.append({
                "source_id": source["id"],
                "source_name": source["name"],
                "bias": source["bias"],
                "title": data.get("title", entry.title),
                "url": entry.link,
                "text_for_embedding": f"{data.get('title', entry.title)}. {text}"
            })




    with open('articles.jsonl', 'a', encoding='utf-8') as f:
        for article in collected_data:
            f.write(json.dumps(article, ensure_ascii=False) + '\n')

    print(f"\nSukces! Zapisano łącznie {len(collected_data)} artykułów do pliku 'articles.jsonl'.")


# agg_news_artictles(SOURCES)  # uruchamiane przez main.py

create_init_db()