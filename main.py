"""Główny punkt wejścia projektu Perspektywy.

Uruchamia pełny pipeline:
1. Fetch RSS feeds → articles.jsonl (data_scraper)
2. Load → Embed → Cluster → Print (analytics_engine)
"""

import sys
import os

# Dodaj root projektu do sys.path, żeby importy między pakietami działały
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from data_scraper.load_database import agg_news_artictles
from analytics_engine.sources_config import SOURCES
from analytics_engine.create_embeddings import (
    load_and_deduplicate_articles,
    prepare_texts_for_embedding,
    generate_embeddings,
    cluster_news_agglomerative,
    map_labels_to_articles,
    deduplicate_cluster_sources,
    print_clusters,
)


def main():
    print("=" * 60)
    print("PERSPEKTYWY — News Embedding & Clustering Pipeline")
    print("=" * 60)

    # Krok 1: Fetch RSS feeds i zapisz do articles.jsonl
    print("\n[KROK 1] Fetchowanie RSS feedów...")
    agg_news_artictles(SOURCES)

    # Krok 2: Embed + Cluster
    print("\n[KROK 2] Generowanie embeddingów i klasteryzacja...")
    filepath = os.path.join(PROJECT_ROOT, "data_scraper", "articles.jsonl")

    articles = load_and_deduplicate_articles(filepath)
    if len(articles) < 15:
        print(
            f"Błąd: Za mało artykułów ({len(articles)}) "
            "do klasteryzacji (minimum 15)."
        )
        return

    texts_to_embed = prepare_texts_for_embedding(articles)
    embeddings = generate_embeddings(texts_to_embed)

    cluster_labels = cluster_news_agglomerative(embeddings, distance_threshold=0.30)

    raw_clusters = map_labels_to_articles(articles, cluster_labels)

    processed_clusters = deduplicate_cluster_sources(raw_clusters)

    print_clusters(processed_clusters)

    print("\n" + "=" * 60)
    print("Pipeline zakończony.")
    print("=" * 60)


if __name__ == "__main__":
    main()
