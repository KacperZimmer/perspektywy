import requests
from typing import List, Dict

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"


def fetch_top_politicians(limit: int = 100) -> List[Dict]:
    query = f"""
    SELECT ?person ?personLabel ?personDescription ?aliases ?sitelinks ?image WHERE {{
      {{
        SELECT ?person ?sitelinks WHERE {{
          ?person wdt:P31 wd:Q5 ;                    # człowiek
                  wdt:P106 wd:Q82955 ;               # zawód: polityk
                  wdt:P27 wd:Q36 ;                   # obywatelstwo: Polska
                  wikibase:sitelinks ?sitelinks .    # popularność
          FILTER NOT EXISTS {{ ?person wdt:P570 ?death }} # tylko żyjący
        }}
        ORDER BY DESC(?sitelinks)
        LIMIT {limit}
      }}

      # Opcjonalne zdjęcie (nie każdy polityk musi je mieć)
      OPTIONAL {{ ?person wdt:P18 ?image . }}

      # Polskie etykiety, opisy i aliasy
      SERVICE wikibase:label {{ 
        bd:serviceParam wikibase:language "pl,en". 
        ?person rdfs:label ?personLabel .
        ?person schema:description ?personDescription .
        ?person skos:altLabel ?aliases .
      }}
    }}
    ORDER BY DESC(?sitelinks)
    """

    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "PolishGroundNewsBot/1.0 (kontakt@twojadomena.pl)"
    }

    response = requests.get(
        SPARQL_ENDPOINT,
        params={"query": query, "format": "json"},
        headers=headers,
        timeout=60
    )
    response.raise_for_status()

    data = response.json()
    bindings = data["results"]["bindings"]

    politicians_dict = {}

    for item in bindings:
        wikidata_id = item["person"]["value"].split("/")[-1]

        if wikidata_id not in politicians_dict:
            name = item.get("personLabel", {}).get("value", "")
            description = item.get("personDescription", {}).get("value", "Polski polityk")
            sitelinks = int(item.get("sitelinks", {}).get("value", 0))
            image_url = item.get("image", {}).get("value", None)

            politicians_dict[wikidata_id] = {
                "wikidata_id": wikidata_id,
                "name": name,
                "bio": description,
                "image_url": image_url,
                "popularity_score": sitelinks,
                "aliases": set()
            }

        raw_aliases = item.get("aliases", {}).get("value", "")
        if raw_aliases:
            for alias in raw_aliases.split(","):
                cleaned = alias.strip()
                if cleaned and cleaned.lower() != politicians_dict[wikidata_id]["name"].lower():
                    politicians_dict[wikidata_id]["aliases"].add(cleaned)

    result = list(politicians_dict.values())
    for p in result:
        p["aliases"] = list(p["aliases"])

    return result