import requests
import json
from typing import List, Dict

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

SPARQL_QUERY = """
SELECT ?person ?personLabel ?personDescription ?aliases ?sitelinks WHERE {
  ?person wdt:P31 wd:Q5 ;                    # człowiek
          wdt:P106 wd:Q82955 ;               # zawód: polityk
          wdt:P27 wd:Q36 ;                   # obywatelstwo: Polska
          wikibase:sitelinks ?sitelinks .    # liczba artykułów na Wikipedii

  # Tylko żyjący politycy
  FILTER NOT EXISTS { ?person wdt:P570 ?death }

  # Pobierz polskie etykiety i opisy
  SERVICE wikibase:label { 
    bd:serviceParam wikibase:language "pl,en". 
    ?person rdfs:label ?personLabel .
    ?person schema:description ?personDescription .
    ?person skos:altLabel ?aliases .
  }
}
ORDER BY DESC(?sitelinks)
LIMIT 100
"""


def fetch_top_politicians() -> List[Dict]:
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "PolishGroundNewsBot/1.0 (kontakt@twojadomena.pl)"
    }

    response = requests.get(
        SPARQL_ENDPOINT,
        params={"query": SPARQL_QUERY, "format": "json"},
        headers=headers,
        timeout=30
    )
    response.raise_for_status()

    data = response.json()
    bindings = data["results"]["bindings"]

    politicians = []
    for item in bindings:
        wikidata_id = item["person"]["value"].split("/")[-1]
        name = item.get("personLabel", {}).get("value", "")
        description = item.get("personDescription", {}).get("value", "Polski polityk")
        sitelinks = int(item.get("sitelinks", {}).get("value", 0))

        raw_aliases = item.get("aliases", {}).get("value", "")
        aliases = [a.strip() for a in raw_aliases.split(",") if a.strip()] if raw_aliases else []

        politicians.append({
            "wikidata_id": wikidata_id,
            "canonical_name": name,
            "bio_context": description,
            "aliases": aliases,
            "sitelinks": sitelinks
        })

    return politicians


if __name__ == "__main__":
    top_100 = fetch_top_politicians()
    print(f"Pobrano {len(top_100)} polityków.\n")

    for p in top_100[:3]:
        print(f"[{p['wikidata_id']}] {p['canonical_name']} (popularność: {p['sitelinks']})")
        print(f"  Opis: {p['bio_context']}")
        print(f"  Aliasy: {p['aliases']}\n")