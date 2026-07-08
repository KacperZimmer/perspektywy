import json
import numpy as np
import ollama
from collections import defaultdict
from sklearn.cluster import HDBSCAN
import umap


def load_and_deduplicate_articles(filepath: str) -> list:
    """
    Wczytuje artykuły z pliku JSONL i usuwa duplikaty na podstawie tytułu.
    """
    article_list = []
    seen_titles = set()

    with open(filepath, "r") as file:
        for line in file:
            data = json.loads(line.strip())
            title = data.get('title', '')

            if title and title not in seen_titles:
                seen_titles.add(title)
                article_list.append(data)

    print(f"Załadowano {len(article_list)} unikalnych artykułów.")
    return article_list


def prepare_texts_for_embedding(article_list: list) -> list:
    """
    Przygotowuje teksty do wektoryzacji. Omija źródło, by nie biasować modelu.
    """
    return [
        f"passage: {article['title']} {article['text_for_embedding']}"
        for article in article_list
    ]


def generate_embeddings(texts: list, model_name: str = "jeffh/intfloat-multilingual-e5-large:Q8_0") -> np.ndarray:
    """
    Generuje embeddingi za pomocą Ollamy dla listy tekstów.
    """
    print(f"Generuję embeddingi przez Ollama (model: {model_name})...")
    embedded_texts = []

    for text in texts:
        response = ollama.embeddings(model=model_name, prompt=text)
        embedded_texts.append(response['embedding'])

    embeddings_array = np.array(embedded_texts)
    print(f"Kształt embeddingów: {embeddings_array.shape}")
    return embeddings_array


def reduce_dimensions_umap(embeddings: np.ndarray, n_components: int = 5, n_neighbors: int = 10) -> np.ndarray:
    """
    Redukuje wymiarowość macierzy embeddingów używając UMAP.
    """
    print("\nRedukcja wymiarów embeddingów przy użyciu UMAP...")
    reducer = umap.UMAP(
        n_components=n_components,
        n_neighbors=n_neighbors,
        min_dist=0.0,
        metric='cosine',
        random_state=42
    )
    reduced = reducer.fit_transform(embeddings)
    print(f"Kształt po redukcji UMAP: {reduced.shape}")
    return reduced


def cluster_with_hdbscan(reduced_embeddings: np.ndarray, min_cluster_size: int = 3, min_samples: int = 2) -> np.ndarray:
    """
    Grupuje zredukowane embeddingi za pomocą algorytmu HDBSCAN.
    """
    print("Grupowanie artykułów przy użyciu HDBSCAN...")
    clusterer = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric='euclidean'
    )
    return clusterer.fit_predict(reduced_embeddings)


def map_labels_to_articles(article_list: list, labels: np.ndarray) -> dict:
    """
    Łączy oryginalne artykuły z wygenerowanymi etykietami klastrów.
    """
    clusters = defaultdict(list)
    for idx, label in enumerate(labels):
        clusters[label].append({
            "title": article_list[idx]['title'],
            "source": article_list[idx]['source_name']
        })
    return clusters


def deduplicate_cluster_sources(clusters: dict, min_unique_sources: int = 2) -> dict:
    """
    Przetwarza klastry: zostawia tylko po jednym artykule z danej redakcji (źródła).
    Odrzuca klastry, które mają mniej unikalnych źródeł niż zdefiniowane minimum.
    Szum (-1) zostaje nienaruszony.
    """
    deduplicated_clusters = {}

    for cluster_id, articles in clusters.items():
        if cluster_id == -1:
            deduplicated_clusters[cluster_id] = articles
            continue

        unique_source_articles = {}
        for article in articles:
            source = article['source']
            if source not in unique_source_articles:
                unique_source_articles[source] = article

        filtered_articles = list(unique_source_articles.values())

        if len(filtered_articles) >= min_unique_sources:
            deduplicated_clusters[cluster_id] = filtered_articles

    return deduplicated_clusters


def print_clusters(clusters: dict):
    """
    Wypisuje sformatowane wyniki klasteryzacji do konsoli.
    """
    print("\n" + "=" * 50)
    print("WYNIKI KLASTERYZACJI (BEZ DUPLIKATÓW Z TEGO SAMEGO ŹRÓDŁA)")
    print("=" * 50)

    sorted_clusters = sorted(clusters.items(), key=lambda item: item[0])

    for cluster_id, articles in sorted_clusters:
        if cluster_id == -1:
            print(f"\n⚫ SZUM (artykuły niepasujące do żadnej grupy) [{len(articles)}]:")
        else:
            print(f"\n🟢 TEMAT {cluster_id} [{len(articles)} różnych źródeł]:")

        for article in articles:
            print(f"  - [{article['source']}] {article['title']}")


def main():

    filepath = "articles.jsonl"
    articles = load_and_deduplicate_articles(filepath)
    texts_to_embed = prepare_texts_for_embedding(articles)

    embeddings = generate_embeddings(texts_to_embed)

    reduced_embeddings = reduce_dimensions_umap(embeddings, n_components=5, n_neighbors=10)
    cluster_labels = cluster_with_hdbscan(reduced_embeddings, min_cluster_size=3, min_samples=2)

    raw_clusters = map_labels_to_articles(articles, cluster_labels)
    final_clusters = deduplicate_cluster_sources(raw_clusters, min_unique_sources=2)

    print_clusters(final_clusters)


if __name__ == "__main__":
    main()