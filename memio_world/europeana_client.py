"""
Europeana API Client — PLAY.EU
================================
REST API wrapper za pristup Europeana kulturnoj baštini.
55M+ objekata, 20M pod CC0.

API dokumentacija: https://pro.europeana.eu/page/search
Rate limit: Project key — do 10 req/s
IIIF: https://iiif.europeana.eu (ne treba API key)

Korištenje:
    from memio_world.europeana_client import EuropeanaClient
    client = EuropeanaClient()
    results = client.search_children_content("alphabet", category="alphabet", limit=20)
"""

import hashlib
import json
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("europeana")

EUROPEANA_SEARCH_URL = "https://api.europeana.eu/record/v2/search.json"
EUROPEANA_RECORD_URL = "https://api.europeana.eu/record/v2"

# Mapiranje Europeana rights URI-ja na naše kategorije
RIGHTS_COMMERCIAL_OK = {
    "http://creativecommons.org/publicdomain/zero/1.0/",
    "http://creativecommons.org/licenses/by/4.0/",
    "http://creativecommons.org/licenses/by/3.0/",
    "http://creativecommons.org/licenses/by/2.0/",
    "http://creativecommons.org/publicdomain/mark/1.0/",
}

RIGHTS_SHARE_ALIKE = {
    "http://creativecommons.org/licenses/by-sa/4.0/",
    "http://creativecommons.org/licenses/by-sa/3.0/",
}

RIGHTS_NON_COMMERCIAL = {
    "http://creativecommons.org/licenses/by-nc/4.0/",
    "http://creativecommons.org/licenses/by-nc-sa/4.0/",
    "http://creativecommons.org/licenses/by-nc-nd/4.0/",
}

# Preddefinirani upiti za dječji sadržaj
CHILDREN_QUERIES = {
    "alphabet": 'what:"alphabet" OR what:"abecedaire" OR what:"Fibel" OR what:"slovarica" OR what:"primer"',
    "counting": 'what:"counting rhyme" OR what:"comptine" OR what:"Abzählreim" OR what:"brojalica"',
    "story": 'what:"fairy tale" OR what:"conte de fées" OR what:"Märchen" OR what:"bajka" OR what:"children story"',
    "song": 'what:"children song" OR what:"nursery rhyme" OR what:"chanson enfantine" OR what:"Kinderlied"',
    "bestiary": 'what:"bestiary" OR what:"bestiaire" OR what:"Bestiarium"',
    "game": 'what:"children game" OR what:"jeu enfant" OR what:"Kinderspiel"',
    "illustration": 'what:"children book illustration" OR what:"picture book"',
    "map": 'what:"illustrated map" OR what:"historical map" AND what:"children"',
    "manuscript": 'what:"illuminated manuscript" OR what:"enluminure"',
}

CACHE_TTL = 86400  # 24h


class EuropeanaClient:
    """REST client za Europeana Search API."""

    def __init__(self, api_key=None):
        self.api_key = api_key or getattr(settings, "EUROPEANA_API_KEY", "")
        if not self.api_key:
            logger.warning("EUROPEANA_API_KEY nije postavljen u settings — koristim demo ključ")
            # Europeana pruža demo ključ za testiranje
            self.api_key = "api2demo"
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def search(
        self,
        query: str,
        *,
        reusability: str = "open",
        media_type: str = "",
        rows: int = 20,
        start: int = 1,
        country: str = "",
        language: str = "",
        sort: str = "score+desc",
    ) -> dict:
        """
        Pretraži Europeana kolekcije.

        Args:
            query: Tekstualni upit
            reusability: "open" (CC0/CC-BY), "restricted", "permission"
            media_type: "IMAGE", "SOUND", "TEXT", "VIDEO"
            rows: Broj rezultata (max 100)
            start: Offset za paginaciju
            country: ISO zemlja filter
            language: Jezik filter
            sort: Sortiranje

        Returns:
            dict s ključevima: items (list), totalResults (int), success (bool)
        """
        cache_key = self._cache_key(query, reusability, media_type, rows, start, country)
        cached = cache.get(cache_key)
        if cached:
            logger.debug("Europeana cache hit: %s", query[:50])
            return cached

        params = {
            "wskey": self.api_key,
            "query": query,
            "rows": min(rows, 100),
            "start": start,
            "sort": sort,
            "profile": "standard",
        }
        if reusability:
            params["reusability"] = reusability
        if media_type:
            params["qf"] = f"TYPE:{media_type}"
        if country:
            params["qf"] = params.get("qf", "") + f" COUNTRY:{country}"
        if language:
            params["qf"] = params.get("qf", "") + f" LANGUAGE:{language}"

        try:
            resp = self.session.get(EUROPEANA_SEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("Europeana API error: %s", e)
            return {"items": [], "totalResults": 0, "success": False, "error": str(e)}

        result = {
            "items": data.get("items", []),
            "totalResults": data.get("totalResults", 0),
            "success": data.get("success", False),
        }

        if result["success"]:
            cache.set(cache_key, result, CACHE_TTL)

        return result

    def search_children_content(
        self,
        query_key: str,
        *,
        category: str = "",
        limit: int = 20,
        country: str = "",
        media_type: str = "IMAGE",
    ) -> list:
        """
        Pretraži Europeana za dječji edukativni sadržaj.

        Args:
            query_key: Ključ iz CHILDREN_QUERIES ("alphabet", "bestiary", etc.)
            category: Kategorija za EuropeanaItem model
            limit: Max broj rezultata
            country: ISO zemlja filter
            media_type: Tip medija

        Returns:
            Lista dict-ova spremnih za EuropeanaItem.objects.create()
        """
        query = CHILDREN_QUERIES.get(query_key, query_key)
        data = self.search(query, reusability="open", media_type=media_type, rows=limit, country=country)

        if not data.get("success"):
            return []

        items = []
        for raw in data.get("items", []):
            item = self._parse_item(raw, category or query_key)
            if item:
                items.append(item)

        logger.info("Europeana: %d items za '%s' (od %d ukupno)", len(items), query_key, data["totalResults"])
        return items

    def get_record(self, europeana_id: str) -> dict | None:
        """Dohvati detalje jednog zapisa po Europeana ID-u."""
        cache_key = f"europeana:record:{europeana_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        url = f"{EUROPEANA_RECORD_URL}{europeana_id}.json"
        try:
            resp = self.session.get(url, params={"wskey": self.api_key}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                cache.set(cache_key, data.get("object"), CACHE_TTL)
                return data.get("object")
        except requests.RequestException as e:
            logger.error("Europeana record error for %s: %s", europeana_id, e)
        return None

    def _parse_item(self, raw: dict, category: str) -> dict | None:
        """Pretvori Europeana API odgovor u dict za EuropeanaItem."""
        europeana_id = raw.get("id", "")
        if not europeana_id:
            return None

        # Izvuci naslov (može biti dict po jezicima ili lista)
        title_data = raw.get("title", ["Bez naslova"])
        title = title_data[0] if isinstance(title_data, list) else str(title_data)

        # Višejezični naslovi iz dcTitleLangAware
        title_lang = raw.get("dcTitleLangAware", {})
        title_hr = self._first_val(title_lang.get("hr", title_lang.get("hrv", [])))
        title_de = self._first_val(title_lang.get("de", title_lang.get("deu", [])))
        title_en = self._first_val(title_lang.get("en", title_lang.get("eng", [])))
        title_fr = self._first_val(title_lang.get("fr", title_lang.get("fra", [])))
        title_it = self._first_val(title_lang.get("it", title_lang.get("ita", [])))

        # Opis
        desc_data = raw.get("dcDescription", [""])
        description = desc_data[0] if isinstance(desc_data, list) else str(desc_data)

        # Media
        thumbnail = raw.get("edmPreview", [""])[0] if raw.get("edmPreview") else ""
        media_type = raw.get("type", "IMAGE")

        # Rights
        rights_list = raw.get("rights", [])
        rights_uri = rights_list[0] if rights_list else ""
        is_commercial = rights_uri in RIGHTS_COMMERCIAL_OK

        # Provider
        provider = ""
        provider_data = raw.get("dataProvider", [])
        if provider_data:
            provider = provider_data[0] if isinstance(provider_data, list) else str(provider_data)

        country = raw.get("country", [""])[0] if raw.get("country") else ""

        # Godina
        year = raw.get("year", [""])[0] if raw.get("year") else ""
        year_int = None
        if year:
            try:
                year_int = int(str(year)[:4])
            except (ValueError, IndexError):
                pass

        # Jezik
        language = ""
        lang_data = raw.get("language", [])
        if lang_data:
            language = lang_data[0] if isinstance(lang_data, list) else str(lang_data)

        return {
            "europeana_id": europeana_id,
            "title": title[:500],
            "title_hr": (title_hr or "")[:500],
            "title_de": (title_de or "")[:500],
            "title_en": (title_en or "")[:500],
            "title_fr": (title_fr or "")[:500],
            "title_it": (title_it or "")[:500],
            "description": (description or "")[:5000],
            "provider": (provider or "")[:200],
            "country": (country or "")[:10],
            "thumbnail_url": thumbnail[:500],
            "media_type": media_type[:10],
            "rights": rights_uri[:200],
            "is_commercially_usable": is_commercial,
            "category": category[:20],
            "year_created": year_int,
            "original_language": (language or "")[:10],
        }

    @staticmethod
    def _first_val(lst):
        """Sigurno izvuci prvi element iz liste ili vrati prazan string."""
        if isinstance(lst, list) and lst:
            return lst[0]
        if isinstance(lst, str):
            return lst
        return ""

    @staticmethod
    def _cache_key(*args) -> str:
        raw = json.dumps(args, sort_keys=True, default=str)
        return f"europeana:search:{hashlib.md5(raw.encode()).hexdigest()}"
