import json
import re
import textwrap
from collections import defaultdict
import numpy as np
import ollama
from sklearn.cluster import AgglomerativeClustering


def load_and_deduplicate_articles(filepath: str) -> list:
    """Ładuje artykuły z pliku JSONL i usuwa dokładne duplikaty po tytule."""
    article_list = []
    seen_titles = set()

    with open(filepath, "r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            data = json.loads(line.strip())
            title = data.get("title", "")

            if title and title not in seen_titles:
                seen_titles.add(title)
                article_list.append(data)

    print(f"Załadowano {len(article_list)} unikalnych artykułów.")
    return article_list


def prepare_texts_for_embedding(article_list: list) -> list:
    """Przygotowuje tekst do embeddingu w sposób naturalny dla modelu bge-m3."""
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
    """Generuje wektory (embeddings) za pomocą lokalnego API Ollama."""
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
    """Klastruje wektory za pomocą AgglomerativeClustering ze średnim wiązaniem."""
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


def extract_keywords(title: str) -> set:
    """Wyciąga z tytułu unikalne słowa kluczowe o długości minimum 4 znaków."""
    words = re.findall(r"\b\w{4,}\b", title.lower())
    stop_words = {
        "ponad",
        "tylko",
        "będzie",
        "czego",
        "przez",
        "teraz",
        "bardzo",
        "oto",
        "dlaczego",
        "wraz",
        "oraz",
        "jednak",
        "mimo",
        "jednego",
        "przed",
        "będą",
    }
    return set(w for w in words if w not in stop_words)


def map_labels_to_articles(article_list: list, labels: np.ndarray) -> dict:
    """Mapuje artykuły do klastrów i stosuje Entity Guard do rozbicia sztucznych zbitek."""
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
            article_keywords = extract_keywords(article["title"])
            placed = False

            for sub_cluster in sub_clusters:
                if any(
                    article_keywords & extract_keywords(existing["title"])
                    for existing in sub_cluster
                ):
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
    """Usuwa duplikaty źródeł wewnątrz jednego klastra i klasyfikuje Szum/Ślepe punkty."""
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
    """Wyświetla sformatowane klastry w czytelny sposób."""
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


def main():
    filepath = "articles.jsonl"

    articles = load_and_deduplicate_articles(filepath)
    if len(articles) < 15:
        print(
            "Błąd: Za mało artykułów do przeprowadzenia klasteryzacji (minimum to 15)."
        )
        return

    texts_to_embed = prepare_texts_for_embedding(articles)
    embeddings = generate_embeddings(texts_to_embed)

    cluster_labels = cluster_news_agglomerative(embeddings, distance_threshold=0.30)

    raw_clusters = map_labels_to_articles(articles, cluster_labels)

    processed_clusters = deduplicate_cluster_sources(raw_clusters)

    print_clusters(processed_clusters)


if __name__ == "__main__":
    main()