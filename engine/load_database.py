import feedparser
import psycopg2
import requests
import trafilatura
import json
from trafilatura import extract
from configparser import ConfigParser
from test_sources import SOURCES, headers

def connect(config):
    """ Connect to the PostgreSQL database server """
    try:
        with psycopg2.connect(**config) as conn:
            print('Connected to the PostgreSQL server.')
            return conn
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)

def get_db_config(filename='database.ini', section='postgresql') -> dict:

    parser = ConfigParser()
    parser.read(filename)

    config = {}

    if parser.has_section(section):
        params = parser.items(section)

        for param in params:
            config[param[0]] = param[1]
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))

    return config


def agg_news_artictles(data_news_companies_map):
    collected_data = []

    for source in data_news_companies_map:
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
                "text_for_embedding": f"{data.get('title', entry.title)}. {text[:800]}"
            })

    with open('articles.jsonl', 'a', encoding='utf-8') as f:
        for article in collected_data:
            f.write(json.dumps(article, ensure_ascii=False) + '\n')

    print(f"\nSukces! Zapisano łącznie {len(collected_data)} artykułów do pliku 'articles.jsonl'.")


# agg_news_artictles(SOURCES)

db_config = get_db_config()
connect(db_config)