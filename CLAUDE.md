# Project: Perspektywy — News Embedding & Clustering

## Overview

Polish-language news aggregation pipeline that:
1. Fetches RSS feeds from ~18 Polish news sources (center, right, left bias)
2. Extracts article text via Trafilatura
3. Generates embeddings using `bge-m3` via local Ollama
4. Clusters articles with AgglomerativeClustering (cosine metric, average linkage)
5. Deduplicates within clusters via keyword overlap (Entity Guard)
6. (Planned) Persists results into PostgreSQL (`kontekst_db`)

Repo: `git@github.com:KacperZimmer/perspektywy.git`

## Directory structure

```
engine/
  sources_config.py    # SOURCES list: id, name, RSS URL, bias (center/right/left)
  test_sources.py      # Pytest: parametrize over SOURCES — reachability + non-empty feed
  create_embeddings.py # Core pipeline: load → embed → cluster → deduplicate → print
  load_database.py     # Fetcher: RSS → trafilatura → articles.jsonl (append mode)
  database.ini         # PostgreSQL creds [postgresql]: host, database, user, password
  articles.jsonl       # Raw collected articles (gitignored)
```

## Key files

- **`engine/sources_config.py`** — Single source of truth for all news sources. Each entry has `id`, `name`, `url`, `type` (always `"rss"`), `bias` (`"center"`, `"right"`, `"left"`).
- **`engine/create_embeddings.py`** — Main pipeline. Functions:
  - `load_and_deduplicate_articles()` — loads JSONL, deduplicates by title
  - `prepare_texts_for_embedding()` — strips title from text, shortens to 1000 chars, reassembles `"{title}. {text}"`
  - `generate_embeddings()` — calls `ollama.embeddings(model="bge-m3", prompt=text)`
  - `cluster_news_agglomerative()` — `AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average", distance_threshold=0.24)`
  - `extract_keywords()` — 4+ char words minus Polish stop words
  - `map_labels_to_articles()` — groups articles by cluster label, then splits via keyword overlap
  - `deduplicate_cluster_sources()` — keeps one article per source per cluster; singletons go to cluster `-1` (noise)
  - `print_clusters()` — formatted output: 🟢 multi-source topics, 🟡 blindspots (1 source), ⚫ noise
- **`engine/load_database.py`** — Fetches RSS feeds via `feedparser`, extracts text via `trafilatura`, appends to `articles.jsonl`. Currently calls `agg_news_artictles(SOURCES)` at module level. DB connection code is commented out.
- **`engine/test_sources.py`** — Pytest suite: `test_source_is_reachable` (HTTP 200) and `test_source_has_articles` (feed entries > 0).
- **`engine/database.ini`** — PostgreSQL config: `host=localhost`, `database=kontekst_db`, `user=newuser`, `password=password`.

## Running the project

```bash
cd "engine/"
python create_embeddings.py   # Run full pipeline (embed + cluster)
python -m pytest test_sources.py -v  # Test RSS source reachability
```

Embeddings require a local Ollama instance with `bge-m3` pulled.

## Coding conventions

- Polish comments and docstrings throughout
- Snake_case for functions/variables
- Type hints on function signatures
- f-strings for formatting
- No logging module — uses `print()` for all output
- JSONL for data persistence (no ORM)
- Cluster threshold default: `0.24` (tunable per run)

## Git notes

- Default branch: `main`
- DB config (`database.ini`) and articles data (`articles.jsonl`) are gitignored
- Recent work: improved clustering, added sources, DB connection scaffolding
