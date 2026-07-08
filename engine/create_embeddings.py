import json
import numpy as np
import ollama
from collections import defaultdict
from sklearn.cluster import AgglomerativeClustering


def load_and_deduplicate_articles(filepath: str) -> list:
    article_list = []
    seen_titles = set()

    with open(filepath, "r", encoding="utf-8") as file:
        for line in file:
            data = json.loads(line.strip())
            title = data.get('title', '')

            if title and title not in seen_titles:
                seen_titles.add(title)
                article_list.append(data)

    print(f"Załadowano {len(article_list)} unikalnych artykułów.")
    return article_list


def prepare_texts_for_embedding(article_list: list) -> list:
    texts = []
    for article in article_list:
        title = article.get('title', '')
        text_body = article.get('text_for_embedding', '').replace(title, "").strip()[:400]

        full_text = f"Wydarzenie: {title}. Kontekst: {text_body}"
        texts.append(full_text)
    return texts


def generate_embeddings(texts: list, model_name: str = "bge-m3") -> np.ndarray:
    print(f"Generuję embeddingi przez Ollama (model: {model_name})...")
    embedded_texts = []

    for text in texts:
        response = ollama.embeddings(model=model_name, prompt=text)
        embedded_texts.append(response['embedding'])

    embeddings_array = np.array(embedded_texts)
    print(f"Kształt embeddingów: {embeddings_array.shape}")
    return embeddings_array


def cluster_news_agglomerative(embeddings: np.ndarray, distance_threshold: float = 0.20) -> np.ndarray:
    """
    Używamy Agglomerative Clustering na surowych wektorach.
    distance_threshold to najważniejszy parametr!
    0.20 oznacza, że teksty muszą być w ~80% podobne, aby uznać je za to samo wydarzenie.
    """
    print(f"\nGrupowanie Agglomerative (próg dystansu: {distance_threshold})...")
    clusterer = AgglomerativeClustering(
        n_clusters=None,
        metric='cosine',
        linkage='average',
        distance_threshold=distance_threshold
    )
    return clusterer.fit_predict(embeddings)


def map_labels_to_articles(article_list: list, labels: np.ndarray) -> dict:
    clusters = defaultdict(list)
    for idx, label in enumerate(labels):
        clusters[label].append({
            "title": article_list[idx].get('title', ''),
            "source": article_list[idx].get('source_name', 'Nieznane źródło'),
            "index": idx
        })
    return clusters


def deduplicate_cluster_sources(clusters: dict, min_unique_sources: int = 2) -> dict:
    deduplicated_clusters = {}
    noise_articles = []

    for cluster_id, articles in clusters.items():
        unique_source_articles = {}
        for article in articles:
            source = article['source']
            if source not in unique_source_articles:
                unique_source_articles[source] = article

        filtered_articles = list(unique_source_articles.values())

        if len(filtered_articles) >= min_unique_sources:
            deduplicated_clusters[cluster_id] = filtered_articles
        else:
            noise_articles.extend(filtered_articles)

    if noise_articles:
        deduplicated_clusters[-1] = noise_articles

    return deduplicated_clusters


def print_clusters(clusters: dict):
    print("\n" + "=" * 50)
    print("WYNIKI KLASTERYZACJI (BEZ DUPLIKATÓW Z TEGO SAMEGO ŹRÓDŁA)")
    print("=" * 50)

    # Sortujemy klastry od największego (najwięcej źródeł), a szum (-1) dajemy na sam dół
    sorted_clusters = sorted(
        clusters.items(),
        key=lambda item: (item[0] == -1, -len(item[1]))
    )

    for cluster_id, articles in sorted_clusters:
        if cluster_id == -1:
            print(f"\n⚫ SZUM (pojedyncze newsy, brak potwierdzenia z wielu źródeł) [{len(articles)}]:")
        else:
            print(f"\n🟢 TEMAT {cluster_id} [{len(articles)} różnych źródeł]:")

        for article in articles:
            print(f"  - [{article['source']}] {article['title']}")


def main():
    filepath = "articles.jsonl"
    articles = load_and_deduplicate_articles(filepath)

    if len(articles) < 15:
        print("Błąd: Za mało artykułów do przeprowadzenia klasteryzacji (minimum to 15). Sprawdź plik z danymi.")
        return

    texts_to_embed = prepare_texts_for_embedding(articles)

    embeddings = generate_embeddings(texts_to_embed)

    cluster_labels = cluster_news_agglomerative(embeddings, distance_threshold=0.35)

    raw_clusters = map_labels_to_articles(articles, cluster_labels)
    deduplicated_clusters = deduplicate_cluster_sources(raw_clusters, min_unique_sources=2)

    print_clusters(deduplicated_clusters)


if __name__ == "__main__":
    main()