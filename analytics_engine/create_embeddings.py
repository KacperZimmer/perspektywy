import textwrap
import psycopg2
from collections import defaultdict
import numpy as np
import pandas as pd
import ollama
from pgvector.psycopg2 import register_vector
from pandas import DataFrame
from sklearn.cluster import AgglomerativeClustering


def fetch_articles_from_database() -> DataFrame | None:
    conn = None

    try:
        conn = psycopg2.connect(
            host='localhost',
            user='newuser',
            password='password',
            database='kontekst_db'
        )

        register_vector(conn)

        cur = conn.cursor()
        query = 'SELECT id, title, url, source, embedding FROM embedded_articles;'
        cur.execute(query)
        result = cur.fetchall()

        df = pd.DataFrame(result, columns=['id', 'title', 'url', 'source', 'embedding'])

        return df

    except psycopg2.OperationalError as e:
        print(f"Błąd operacyjny: {e}")
    except psycopg2.ProgrammingError as e:
        print(f"Błąd programistyczny: {e}")
    except Exception as e:
        print(f"Błąd ogólny: {e}")
    finally:
        if conn:
            conn.close()


def prepare_texts_for_embedding(article_list: list) -> list:
    texts = []
    for article in article_list:
        title = article.get("title", "")
        raw_text = (
            article.get("text_for_embedding", "").replace(title, "").strip()
        )

        safe_text = textwrap.shorten(raw_text, width=1000, placeholder="...")

        full_text = f"{title}. {safe_text}"
        texts.append(full_text)

    return texts


def generate_embeddings(texts: list, model_name: str = "bge-m3") -> np.ndarray:
    print(f"Generuję embeddingi przez Ollama (model: {model_name})...")
    embedded_texts = []

    for text in texts:
        response = ollama.embeddings(model=model_name, prompt=text)
        embedded_texts.append(response["embedding"])

    embeddings_array = np.array(embedded_texts)
    print(f"Kształt embeddingów: {embeddings_array.shape}")
    return embeddings_array


def cluster_news_agglomerative(
        embeddings: np.ndarray, distance_threshold: float = 0.24
) -> np.ndarray:
    print(
        f"\nGrupowanie Agglomerative (linkage: average, próg: {distance_threshold})..."
    )
    clusterer = AgglomerativeClustering(
        n_clusters=None,
        metric="cosine",
        linkage="average",
        distance_threshold=distance_threshold,
    )
    return clusterer.fit_predict(embeddings)


def map_labels_to_articles(article_list: list, labels: np.ndarray) -> dict:
    initial_clusters = defaultdict(list)
    for idx, label in enumerate(labels):
        initial_clusters[label].append(
            {
                "title": article_list[idx].get("title", ""),
                "source": article_list[idx].get("source_name", "Nieznane źródło"),
                "index": idx,
            }
        )

    verified_clusters = {}
    new_cluster_counter = max(initial_clusters.keys()) + 1

    for cluster_id, articles in initial_clusters.items():
        if len(articles) <= 1:
            verified_clusters[cluster_id] = articles
            continue

        sub_clusters = []

        for article in articles:
            placed = False

            for sub_cluster in sub_clusters:
                sub_cluster.append(article)
                placed = True
                break

            if not placed:
                sub_clusters.append([article])

        for i, sub_cluster in enumerate(sub_clusters):
            if i == 0:
                verified_clusters[cluster_id] = sub_cluster
            else:
                verified_clusters[new_cluster_counter] = sub_cluster
                new_cluster_counter += 1

    return verified_clusters


def deduplicate_cluster_sources(clusters: dict) -> dict:
    processed_clusters = {}
    noise_articles = []

    for cluster_id, articles in clusters.items():
        if len(articles) == 1:
            noise_articles.extend(articles)
            continue

        unique_source_articles = {}
        for article in articles:
            source = article["source"]
            if source not in unique_source_articles:
                unique_source_articles[source] = article

        filtered_articles = list(unique_source_articles.values())
        processed_clusters[cluster_id] = filtered_articles

    if noise_articles:
        processed_clusters[-1] = noise_articles

    return processed_clusters


def print_clusters(clusters: dict):
    print("\n" + "=" * 50)
    print("WYNIKI KLASTERYZACJI (GROUND NEWS PL)")
    print("=" * 50)

    sorted_clusters = sorted(
        clusters.items(), key=lambda item: (item[0] == -1, -len(item[1]))
    )

    for cluster_id, articles in sorted_clusters:
        if not articles:
            continue

        if cluster_id == -1:
            print(
                f"\n⚫ SZUM / POJEDYNCZE NEWSY (Brak powiązań) [{len(articles)}]:"
            )
            for article in articles[:15]:
                print(f"  - [{article['source']}] {article['title']}")
            if len(articles) > 15:
                print(f"  - ... i {len(articles) - 15} innych pojedynczych doniesień.")
        else:
            if len(articles) == 1:
                print(
                    f"\n🟡 ŚLEPY PUNKT (Blindspot) - Temat zdominowany przez 1 źródło:"
                )
            else:
                print(f"\n🟢 TEMAT {cluster_id} [{len(articles)} różnych źródeł]:")

            for article in articles:
                print(f"  - [{article['source']}] {article['title']}")


if __name__ == "__main__":
    result = fetch_articles_from_database()

    if result is None or len(result) < 15:
        print("Błąd: Za mało artykułów do przeprowadzenia klasteryzacji (minimum to 15).")
    else:
        embeddings = np.stack(result['embedding'].apply(lambda v: v.to_numpy()))

        cluster_labels = cluster_news_agglomerative(embeddings, distance_threshold=0.30)

        articles = result.rename(columns={'source': 'source_name'}).to_dict('records')

        raw_clusters = map_labels_to_articles(articles, cluster_labels)

        processed_clusters = deduplicate_cluster_sources(raw_clusters)

        print_clusters(processed_clusters)