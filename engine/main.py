import feedparser
import trafilatura
from dataclasses import dataclass
import json

SOURCES_CONFIG = [
    {
        "name": "TVN24",
        "url": "https://tvn24.pl/sitemap_news.xml",
        "type": "sitemap_news"
    },
    {
        "name": "Onet",
        "url": "https://wiadomosci.onet.pl/.feed",
        "type": "rss"
    },
    {
        "name": "wPolityce",
        "url": "https://wpolityce.pl/feed",
        "type": "rss"
    },
    {
        "name": "OKO.press",
        "url": "https://oko.press/sitemap.xml",
        "type": "sitemap_standard"
    }
]

import feedparser
import requests
from bs4 import BeautifulSoup

def get_urls_from_rss(rss_url, max_urls=5):
    feed = feedparser.parse(rss_url)
    return [entry.link for entry in feed.entries[:max_urls]]

def get_urls_from_sitemap(sitemap_url, max_urls=5):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(sitemap_url, headers=headers)
    if response.status_code != 200:
        return []
    soup = BeautifulSoup(response.content, 'xml')
    return [loc.text for loc in soup.find_all('loc')][:max_urls]

# Dyspozytor
def collect_urls_for_source(source):
    print(f"Szukam linków dla: {source['name']} ({source['type']})")
    if "sitemap" in source['type']:
        return get_urls_from_sitemap(source['url'])
    elif source['type'] == "rss":
        return get_urls_from_rss(source['url'])
    else:
        return []

