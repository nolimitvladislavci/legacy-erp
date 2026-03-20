"""
fina_infobiz.py
───────────────
FINA Info.BIZ OIB lookup za firme koje nisu PDV obveznici (nisu u EU VIES).

Svaka firma unosi vlastiti API token dobiven registracijom na:
  https://infobiz.fina.hr/Registration

Token se sprema u Company.settings["fina_infobiz_token"] i koristi se
isključivo za tu firmu — u skladu s FINA uvjetima korištenja.
"""

import logging
import requests

logger = logging.getLogger(__name__)

FINA_API_BASE = "https://infobiz.fina.hr/api/v1"
FINA_REGISTER_URL = "https://infobiz.fina.hr/Registration"
FINA_DOCS_URL = "https://www.fina.hr/info.biz"


def lookup_oib_fina(oib: str, api_token: str) -> dict:
    """
    Dohvati podatke firme po OIB-u iz FINA Info.BIZ API-ja.

    Args:
        oib:       11-znamenkasti hrvatski OIB
        api_token: FINA Info.BIZ API token firme

    Returns:
        {
          "found": True/False,
          "source": "fina_infobiz",
          "name": "...",
          "address": "...",
          "city": "...",
          "zip_code": "...",
          "mb": "...",         # matični broj
          "nkd": "...",        # djelatnost
          "status": "...",     # Aktivan / Neaktivan
          "size": "...",       # Mikro / Mali / Srednji / Veliki
          "error": None
        }
    """
    if not api_token or not oib:
        return {"found": False, "error": "Nedostaje API token ili OIB"}

    headers = {
        "Authorization": "Bearer " + api_token,
        "Accept": "application/json",
        "User-Agent": "LIMIT Connect/1.0",
    }

    # Poznati endpointi Info.BIZ API-ja
    endpoints = [
        f"{FINA_API_BASE}/subjekti/oib/{oib}",
        f"{FINA_API_BASE}/search?oib={oib}",
        f"{FINA_API_BASE}/subjects/oib/{oib}",
    ]

    for url in endpoints:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                return _parse_fina_response(data, oib)
            elif r.status_code == 401:
                return {"found": False, "error": "Neispravan FINA API token. Provjerite token u Postavkama."}
            elif r.status_code == 403:
                return {"found": False, "error": "Pristup odbijen. API token nema dozvolu za ovaj upit."}
            elif r.status_code == 404:
                continue  # Pokušaj sljedeći endpoint
        except requests.Timeout:
            return {"found": False, "error": "FINA API nije odgovorio (timeout). Pokušajte ponovo."}
        except Exception as ex:
            logger.warning("FINA Info.BIZ lookup error for OIB %s: %s", oib, ex)
            continue

    # Ako nijedan endpoint nije vratio 200, firma nije pronađena
    return {
        "found": False,
        "source": "fina_infobiz",
        "error": "Firma nije pronađena u FINA Info.BIZ bazi.",
    }


def _parse_fina_response(data: dict, oib: str) -> dict:
    """Parsiraj FINA API odgovor u standardni format."""
    # FINA može vratiti listu ili direktni objekt
    if isinstance(data, list):
        data = data[0] if data else {}

    if not data:
        return {"found": False, "source": "fina_infobiz", "error": "Prazni podaci"}

    # Normaliziraj adresu
    address_parts = []
    for key in ("ulica", "adresa", "address", "street"):
        val = data.get(key, "")
        if val:
            address_parts.append(val.strip().title())
            break

    city = ""
    for key in ("mjesto", "grad", "city"):
        val = data.get(key, "")
        if val:
            city = val.strip().title()
            break

    zip_code = ""
    for key in ("pbr", "postanski_broj", "zip_code", "postal_code"):
        val = data.get(key, "")
        if val:
            zip_code = str(val).strip()
            break

    name = ""
    for key in ("naziv", "name", "tvrtka", "company_name"):
        val = data.get(key, "")
        if val:
            name = val.strip()
            break

    return {
        "found": bool(name),
        "source": "fina_infobiz",
        "name": name,
        "oib": oib,
        "mb": str(data.get("mb", data.get("maticni_broj", ""))).strip(),
        "address": ", ".join(address_parts),
        "city": city,
        "zip_code": zip_code,
        "nkd": str(data.get("nkd", data.get("djelatnost", ""))).strip(),
        "status": data.get("status", data.get("statusSubjekta", "")),
        "size": data.get("velicina", data.get("velicinaPoduzeca", "")),
        "error": None,
    }


def get_fina_token_for_company(company) -> str:
    """Dohvati FINA token iz Company.settings."""
    if not company:
        return ""
    settings = getattr(company, "settings", None) or {}
    return settings.get("fina_infobiz_token", "").strip()


def mask_token(token: str) -> str:
    """Maskiraj token za prikaz (prvih 8 + *** + zadnja 4)."""
    if not token or len(token) < 12:
        return "***"
    return token[:8] + "***" + token[-4:]
