from urllib import response

import pytest
import requests
import feedparser

from sources_config import SOURCES

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s["id"])
def test_source_is_reachable(source):

    if source['type'] != "rss":
        pytest.skip("Implement it later")


    try:
        response = requests.get(source['url'], headers=headers, timeout=10)

    except requests.exceptions.RequestException as e:
        pytest.fail(f"Błąd połączenia z {source['name']} kod błędu ")

    assert response.status_code == 200, f"Serwer {source['name']} zwrócił kod błędu: {response.status_code}"

@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s['id'])
def test_source_has_articles(source):
    if source['type'] != "rss":
        pytest.skip("Implement it later")

    try:
        response = requests.get(source['url'], headers=headers, timeout=10)
        if response.status_code != 200:
            pytest.fail(f"Nie można sprawdzić artykułów, bo serwer rzucił kod: {response.status_code}")
    except requests.exceptions.RequestException:
        pytest.fail("Błąd połączenia sieciowego w teście zawartości.")

    feed = feedparser.parse(response.content)

    assert len(feed.entries) > 0, f"Kanał RSS dla {source['name']} jest pusty (0 artykułów)!"