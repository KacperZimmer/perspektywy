import json
import numpy as np
import ollama
from sklearn.metrics.pairwise import cosine_similarity

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

pairs = []
num_articles = len(article_list)

for i in range(num_articles):
    for j in range(i + 1, num_articles):
        score = similarity_matrix[i][j]
        pairs.append({
            "title_a": article_list[i].get('title', 'Brak tytułu'),
            "source_a": article_list[i].get('source_name', 'Nieznane źródło'),
            "title_b": article_list[j].get('title', 'Brak tytułu'),
            "source_b": article_list[j].get('source_name', 'Nieznane źródło'),
            "similarity": float(score)
        })

pairs.sort(key=lambda x: x['similarity'], reverse=True)

print("\n=== TOP 10 NAJBARDZIEJ PODOBNE UNIKALNE ARTYKUŁY ===")
for pair in pairs[:10]:
    print(f"Podobieństwo: {pair['similarity']:.4f}")
    print(f"  • Artykuł A: [{pair['source_a']}] {pair['title_a']}")
    print(f"  • Artykuł B: [{pair['source_b']}] {pair['title_b']}")
    print("-" * 40)