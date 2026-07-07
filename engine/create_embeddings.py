import json
import numpy as np
import ollama
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
from sklearn.cluster import HDBSCAN
import umap

article_list = []
seen_titles = set()

with open("articles.jsonl", "r") as file:
    for line in file:
        data = json.loads(line.strip())
        title = data.get('title', '')

        if title not in seen_titles:
            seen_titles.add(title)
            article_list.append(data)

texts_to_embed = [
    f"passage: {article['source_name']} {article['title']} {article['text_for_embedding']}"
    for article in article_list
]

print(f"Załadowano {len(article_list)} unikalnych artykułów (kopie zostały usunięte).")
print(f"Generuję embeddingi przez Ollama...")

embeddings = []
for text in texts_to_embed:
    response = ollama.embeddings(
        model="jeffh/intfloat-multilingual-e5-large:Q8_0",
        prompt=text
    )
    embeddings.append(response['embedding'])

embeddings_matrix = np.array(embeddings)
similarity_matrix = cosine_similarity(embeddings_matrix)



print("\nRedukcja wymiarów embeddingów przy użyciu UMAP...")

dimension_reducer = umap.UMAP(
    n_components=5,
    n_neighbors=10,
    min_dist=0.0,
    metric='cosine',
    random_state=42
)

reduced_embeddings = dimension_reducer.fit_transform(embeddings_matrix)
print(f"Kształt po redukcji UMAP: {reduced_embeddings.shape}")


print("Grupowanie artykułów przy użyciu HDBSCAN...")

clusterer = HDBSCAN(
    min_cluster_size=3,
    min_samples=2,
)

cluster_labels = clusterer.fit_predict(reduced_embeddings)


clusters = defaultdict(list)

for idx, label in enumerate(cluster_labels):
    clusters[label].append({
        "title": article_list[idx]['title'],
        "source": article_list[idx]['source_name']
    })


deduplicated_clusters = {}

for cluster_id, articles_in_cluster in clusters.items():
    if cluster_id == -1:
        continue

    unique_source_articles = {}

    for article in articles_in_cluster:
        source = article['source']

        if source not in unique_source_articles:
            unique_source_articles[source] = article
        else:

            pass

    filtered_articles = list(unique_source_articles.values())


    if len(filtered_articles) >= 2:
        deduplicated_clusters[cluster_id] = filtered_articles


print("\n" + "=" * 50)
print("WYNIKI KLASTERYZACJI (BEZ DUPLIKATÓW Z TEGO SAMEGO ŹRÓDŁA)")
print("=" * 50)

for cluster_id, articles in deduplicated_clusters.items():
    print(f"\n🟢 TEMAT {cluster_id} [{len(articles)} różnych źródeł]:")
    for article in articles:
        print(f"  - [{article['source']}] {article['title']}")