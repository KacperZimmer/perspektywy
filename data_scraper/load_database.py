from collections import defaultdict
from contextlib import contextmanager
import feedparser
import numpy as np
import psycopg2
import requests
import re

from analytics_engine.create_embeddings import (
    prepare_texts_for_embedding,
    generate_embeddings,
)
from analytics_engine.llm import News_LLM
from analytics_engine.sources_config import SOURCES

llm_news = News_LLM('qwen3.6:35b')
POLITE_HEADERS = {'User-Agent': 'KontekstBot/1.0 (+http://horyzonty.pl)'}





class ManageConnection:
    def __init__(self, host : str, database : str, user : str, password : str):
        self.host = host
        self.user = user
        self.database = database
        self.password = password

    @contextmanager
    def get_db_connection(self):

        conn = None

        try:
            conn = psycopg2.connect(host=self.host, database=self.database, user=self.user, password=self.password)
            with conn:
                with conn.cursor() as cur:
                    yield cur

        except psycopg2.Error as e:
            print(f"Błąd bazy danych podczas podsumowywania: {e}")
            raise
        finally:
            if conn:
                conn.close()
db_manager = ManageConnection(host='localhost', database='kontekst_db', user='newuser', password='password')

def generate_missing_summaries_for_large_clusters():

        with db_manager.get_db_connection() as cur:


            find_clusters_query = """
           SELECT 
            c.id AS cluster_id,
            json_agg(e.article_description) AS descriptions
            FROM clusters c
            JOIN embedded_articles e ON c.id = e.cluster_id
            WHERE c.ai_summary IS NULL
            GROUP BY c.id
            HAVING COUNT(e.id) >= 5;
            """
            cur.execute(find_clusters_query)
            clusters_to_process = cur.fetchall()

            if not clusters_to_process:
                print("🟢 Brak nowych klastrów wymagających wygenerowania podsumowania.")
                return

            print(f"\n🔍 Znaleziono {len(clusters_to_process)} klastrów do podsumowania przez AI.")

            for cluster_row in clusters_to_process:
                cluster_id = cluster_row[0]

                cur.execute(
                    'SELECT article_description FROM embedded_articles WHERE cluster_id = %s AND article_description IS NOT NULL',
                    (cluster_id,)
                )

                descriptions_result = cur.fetchall()
                descriptions = [row[0] for row in descriptions_result if str(row[0]).strip()]

                if not descriptions:
                    print(f"⚠️ Klaster {cluster_id} nie ma żadnych sensownych opisów. Pomijam.")
                    continue

                print(f"⏳ Generuję podsumowanie dla klastra ID: {cluster_id}...")

                ai_response = llm_news.generate_summary(descriptions)

                summary_text = ai_response.get('response', '') if isinstance(ai_response, dict) else ai_response

                update_query = "UPDATE clusters SET ai_summary = %s WHERE id = %s"
                cur.execute(update_query, (summary_text, cluster_id))

                print(f"✅ Podsumowanie dla klastra {cluster_id} pomyślnie zapisane.")

def populate_cluster_titles():

    clusters = []
    find_clusters_missing_titles = """
        SELECT c.id,                                                                                                                                                                                                   
         array_agg(a.article_description ORDER BY a.id) as article_descriptions,                                                                                                                                 
         count(a.cluster_id) as num_of_articles                                                                                                                                                                  
          FROM embedded_articles a                                                                                                                                                                                       
          JOIN clusters c ON a.cluster_id = c.id                                                                                                                                                                         
          WHERE c.title IS NULL                                                                                                                                                                                          
          GROUP BY c.id                                                                                                                                                                                                  
          HAVING count(a.cluster_id) >= 5;  
    """
    result = []
    with db_manager.get_db_connection() as cur:
        cur.execute(find_clusters_missing_titles)
        result = cur.fetchall()

    values_to_update = []

    for cluster_id, cluster_content, _ in result:
        response_ai = llm_news.generate_title(cluster_content)
        values_to_update.append((response_ai, cluster_id))

    update_clusters_query = "UPDATE clusters SET title = %s WHERE id = %s;"

    with db_manager.get_db_connection() as cur:
        cur.executemany(update_clusters_query, values_to_update)


def seed_publishers():
    publishers_data = [
        (1, 'Onet', 0.35, 'onet.pl', ''),
        (2, 'TVN24', 0.3, 'tvn24.pl', ''),
        (3, 'Polsat News', 0.5, 'polsatnews.pl', ''),
        (4, 'Wirtualna Polska', 0.45, 'wp.pl', ''),
        (5, 'RMF24', 0.5, 'rmf24.pl', ''),
        (6, 'Wprost', 0.6, 'wprost.pl', ''),
        (7, 'Rzeczpospolita', 0.65, 'rp.pl', ''),
        (8, 'Nowy Obywatel', 0.15, 'nowyobywatel.pl', ''),
        (9, 'Fakt', 0.5, 'fakt.pl', ''),
        (10, 'Money.pl', 0.5, 'money.pl', ''),
        (11, 'Bankier.pl', 0.55, 'bankier.pl', ''),
        (12, 'Business Insider Polska', 0.45, 'businessinsider.com.pl', ''),
        (13, 'Puls Biznesu', 0.55, 'pb.pl', ''),
        (14, 'Energetyka24', 0.5, 'energetyka24.com', ''),
        (15, 'DoRzeczy.pl', 0.85, 'dorzeczy.pl', ''),
        (16, 'Niezalezna.pl', 0.9, 'niezalezna.pl', ''),
        (17, 'Radio Maryja', 0.95, 'radiomaryja.pl', ''),
        (18, 'Kresy.pl', 0.95, 'kresy.pl', ''),
        (19, 'OKO.press', 0.2, 'oko.press', ''),
        (20, 'Najwyższy Czas!', 0.95, 'nczas.info', ''),
        (21, 'Magna Polonia', 1.0, 'magnapolonia.org', ''),
        (22, 'Krytyka Polityczna', 0.1, 'krytykapolityczna.pl', ''),
        (23, 'Strajk.eu', 0.05, 'strajk.eu', ''),
        (24, 'Tygodnik Powszechny', 0.4, 'tygodnikpowszechny.pl', ''),
        (25, 'Tygodnik Przegląd', 0.15, 'tygodnikprzeglad.pl', ''),
        (26, 'Więź', 0.45, 'wiez.pl', '')
    ]

    with db_manager.get_db_connection() as cur:

            cur.execute("ALTER TABLE stories_publisher ADD COLUMN IF NOT EXISTS domain VARCHAR(255);")
            insert_query = """
                INSERT INTO stories_publisher (id, name, bias, domain, logo)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    bias = EXCLUDED.bias,
                    domain = EXCLUDED.domain,
                    logo = EXCLUDED.logo;
            """

            for pub in publishers_data:
                cur.execute(insert_query, pub)

            cur.execute(
                "SELECT setval(pg_get_serial_sequence('stories_publisher', 'id'), coalesce(max(id), 1), max(id) IS NOT null) FROM stories_publisher;")

            print("✅ Pomyślnie odtworzono i zaktualizowano 26 wydawców w tabeli 'stories_publisher'!")


def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return " ".join(cleantext.split())


def get_publisher_map() -> dict:

    with db_manager.get_db_connection() as cur:
        cur.execute("SELECT name, id FROM stories_publisher")
        result = cur.fetchall()

        publisher_map = {publisher[0]: publisher[1] for publisher in result}
        return publisher_map


def print_db_clusters() -> None:

        with db_manager.get_db_connection() as cur:

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
            print(" AKTUALNY STAN KLASTRÓW W BAZIE (HORYZONT)")
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




def save_data_to_postgres(embeddings_array: np.ndarray, article_list: list) -> None:
    DISTANCE_THRESHOLD = 0.30

    with db_manager.get_db_connection() as cur:
        embeddings_array_as_list = embeddings_array.tolist()

        for idx, article in enumerate(article_list):
            title = article['title']
            url = article['url']
            article_rss_description = article['description']
            source_name = article['source_name']
            publisher_id = article['publisher_db_id']
            embedding = embeddings_array_as_list[idx]

            find_cluster_query = """
                SELECT id, (centroid <=> %s::vector) AS distance
                FROM clusters
                ORDER BY distance ASC
                LIMIT 1;
            """
            # find_associated_articles_with_cluster = """
            #     SELECT a.title
            #     FROM embedded_articles AS a
            #     INNER JOIN clusters AS c ON a.cluster_id = c.id
            #     WHERE c.id = %s
            # """

            cur.execute(find_cluster_query, (embedding,))
            nearest_cluster = cur.fetchone()

            if nearest_cluster and nearest_cluster[1] <= DISTANCE_THRESHOLD:
                cluster_id = nearest_cluster[0]
                cur.execute("UPDATE clusters SET updated_at = current_timestamp WHERE id = %s", (cluster_id,))

                # cur.execute(find_associated_articles_with_cluster, (cluster_id,))
                # associated_articles = cur.fetchall()

                # cur.execute("SELECT title FROM clusters WHERE id = %s", (cluster_id,))
                # row = cur.fetchone()
                # has_title = row and row[0] is not None
                #
                # if len(associated_articles) >= 5 and not has_title:
                #     pass
                #     # response = llm_news.generate_title(associated_articles[0:4])
                #     # title_resp = response.get('response', '') if isinstance(response, dict) else response
                #     # cur.execute("UPDATE clusters set title = %s where id = %s", (title_resp, cluster_id))

            else:
                insert_cluster_query = """
                    INSERT INTO clusters (centroid)
                    VALUES (%s::vector)
                    RETURNING id;
                """
                cur.execute(insert_cluster_query, (embedding,))
                cluster_id = cur.fetchone()[0]

            insert_article_query = """
                INSERT INTO embedded_articles (cluster_id, title, url, source, embedding, publisher_id, article_description) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING;
            """
            cur.execute(insert_article_query,
                        (cluster_id, title, url, source_name, embedding, publisher_id, article_rss_description))



def create_init_db():
    create_table_articles_command = """
          CREATE TABLE IF NOT EXISTS embedded_articles(
              id bigserial primary key,
              cluster_id bigint references clusters(id),
              title text,
              url text UNIQUE,
              source text,
              embedding vector(1024),
              created_at timestamp default current_timestamp,
              article_description text
          );
      """
    create_table_clusters_command = """
        CREATE TABLE IF NOT EXISTS clusters(
            id bigserial primary key, 
            centroid vector(1024),
            created_at timestamp default current_timestamp,
            updated_at timestamp default current_timestamp,
            title text,
            ai_summary text
        );    
    """
    with db_manager.get_db_connection() as cur:

            cur.execute(create_table_clusters_command)
            cur.execute(create_table_articles_command)

            print("✅ Tabele 'clusters' i 'embedded_articles' utworzone/zaktualizowane pomyślnie.")


def agg_news_artictles(data_news_companies_map, num_of_data_to_collect: int):
    collected_data = []
    publisher_map = get_publisher_map()

    for source in data_news_companies_map:
        if source.get('type') != 'rss':
            continue

        try:
            response = requests.get(source['url'], headers=POLITE_HEADERS, timeout=10)
            feed = feedparser.parse(response.content)
        except Exception as e:
            print(f"Błąd sieci dla {source['name']}: {e}")
            continue

        print(f"Przeszukuję: {source['name']}...")
        for entry in feed.entries:
            article_title = entry.get("title", "Brak tytułu")
            article_url = entry.get("link")
            article_description = entry.get('description', '')

            if not article_url:
                continue

            raw_summary = entry.get("summary", "")
            clean_summary = clean_html(raw_summary)

            if len(clean_summary) > 300:
                clean_summary = clean_summary[:300] + "..."

            text_for_embedding = f"{article_title}. {clean_summary}"

            publisher_id = publisher_map.get(source.get("name"))
            if not publisher_id:
                print(f"⚠️ Nie znaleziono wydawcy {source.get('name')} w bazie danych. Pomijam.")
                continue

            collected_data.append({
                "source_id": source.get("id"),
                "source_name": source.get("name"),
                "publisher_db_id": publisher_id,
                "bias": source.get("bias", "unknown"),
                "title": article_title,
                "url": article_url,
                "text_for_embedding": text_for_embedding,
                "description": clean_html(article_description)  # Czyścimy z HTML
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



def run_pipeline():
    print("==================================================")
    print(" 🚀 START DATA PIPELINE: HORYZONT NEWS SYSTEM")
    print("==================================================")

    print("\n[ETAP 1] Pobieranie artykułów i aktualizacja klastrów...")
    agg_news_artictles(SOURCES, 20)

    print("\n[ETAP 2] Uruchamianie agentów AI do analizy i tworzenia podsumowań...")
    generate_missing_summaries_for_large_clusters()

    print("\n[ETAP 3] Przegląd aktualnego stanu...")
    print_db_clusters()

    print("\n✅ Koniec procesu. System wykonał pełen cykl.")


# run_pipeline()

populate_cluster_titles()