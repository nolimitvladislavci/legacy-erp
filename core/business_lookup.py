"""
core/business_lookup.py
═══════════════════════════════════════════════════════════════════════
Centralni servis za lookup poslovnih subjekata po poreznom broju.

Podržane države i izvori:
  HR:  1) EU VIES (PDV obveznici)
       2) FINA Info.BIZ (svi subjekti, token po firmi)
  DE:  1) EU VIES (USt-IdNr — PDV obveznici, format DE + 9 znamenki)
       2) Unternehmensregister.de (scraping, javno)
  AT:  1) EU VIES (UID)
  SI:  1) EU VIES (SI DDV)
  EU:  1) EU VIES (generički za sve EU države)

Globalna upotreba — pozivati iz svih modula:

    from core.business_lookup import lookup_business, BusinessLookupResult

    result = lookup_business(oib='92922919857', country='HR', company=request_company)
    if result.found:
        print(result.name, result.address, result.nkd)

═══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from xml.etree import ElementTree as ET

import requests
from django.db import DatabaseError

logger = logging.getLogger(__name__)

# ─── VIES ────────────────────────────────────────────────────────────────────
VIES_URL = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"

# ─── FINA Info.BIZ ───────────────────────────────────────────────────────────
FINA_API_BASE = "https://infobiz.fina.hr/api/v1"
FINA_REGISTER_URL = "https://infobiz.fina.hr/Registration"

# ─── NKD/WZ-Lookup (in-memory za brze upite bez DB hita) ─────────────────────
_NKD_CACHE: dict[str, str] = {}  # {code: name_hr}
_WZ_CACHE: dict[str, str] = {}   # {code: name_de}


# ══════════════════════════════════════════════════════════════════════════════
# RESULT DATACLASS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BusinessLookupResult:
    """Standardizirani rezultat lookup-a — isti format za sve države i izvore."""

    found: bool = False
    source: str = ""          # "vies" | "fina_infobiz" | "unternehmensregister" | "database"
    country: str = ""

    # Osnovni podaci
    name: str = ""
    tax_id: str = ""          # OIB (HR) / USt-IdNr (DE) / UID (AT) / DDV (SI)
    vat_id: str = ""          # EU PDV broj s prefiksom (HR12345.. / DE123..)
    mb: str = ""              # Matični broj (HR) / HRB-Nummer (DE)
    address: str = ""
    city: str = ""
    zip_code: str = ""

    # Prošireni podaci
    nkd: str = ""             # HR NKD šifra  (npr. "46.90")
    nkd_name: str = ""        # Naziv djelatnosti
    wz_code: str = ""         # DE WZ 2008 šifra
    wz_name: str = ""         # Naziv WZ djelatnosti
    status: str = ""          # "Aktivan" / "aktiv" / ...
    size: str = ""            # "Mikro" / "Klein" / ...
    founding_year: str = ""

    # Meta
    not_vat_registered: bool = False
    oib_valid: bool = True
    error: Optional[str] = None
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serijalizacija za JSON response u views.py."""
        return {
            "found": self.found,
            "source": self.source,
            "country": self.country,
            "name": self.name,
            "oib": self.tax_id,
            "tax_id": self.tax_id,
            "vat_id": self.vat_id,
            "mb": self.mb,
            "address": self.address,
            "city": self.city,
            "zip_code": self.zip_code,
            "nkd": self.nkd,
            "nkd_name": self.nkd_name,
            "wz_code": self.wz_code,
            "wz_name": self.wz_name,
            "status": self.status,
            "size": self.size,
            "founding_year": self.founding_year,
            "not_vat_registered": self.not_vat_registered,
            "oib_valid": self.oib_valid,
            "error": self.error,
        }


# ══════════════════════════════════════════════════════════════════════════════
# GLAVNA FUNKCIJA — jedina koju trebate importati
# ══════════════════════════════════════════════════════════════════════════════

def lookup_business(
    tax_id: str,
    country: str = "HR",
    company=None,         # Company model instanca — za FINA token
    fina_token: str = "", # Ili direktno token
    timeout: int = 8,
) -> BusinessLookupResult:
    """
    Globalni lookup poslovnog subjekta po poreznom broju.

    Primjeri:
        # HR OIB (PDV i ne-PDV obveznici):
        result = lookup_business("92922919857", "HR", company=request.user.profile.company)

        # DE USt-IdNr:
        result = lookup_business("DE119948368", "DE")

        # U views.py:
        return JsonResponse(result.to_dict())
    """
    tax_id = (tax_id or "").strip()
    country = (country or "HR").strip().upper()[:2]

    if not tax_id:
        return BusinessLookupResult(found=False, error="Porezni broj je obavezan", oib_valid=False)

    # Normalizacija: ukloni prefix ako korisnik unese HR12345... / DE12345...
    clean_id = _strip_country_prefix(tax_id, country)

    # 1. Provjeri lokalnu bazu (Partner model)
    db_result = _lookup_in_database(clean_id, country, company)
    if db_result and db_result.found:
        return db_result

    # 2. Dispatch po državi
    if country == "HR":
        return _lookup_hr(clean_id, company, fina_token, timeout)
    elif country == "DE":
        return _lookup_de(tax_id, clean_id, timeout)
    elif country in ("AT", "SI", "IT", "FR", "NL", "BE", "PL", "CZ", "HU"):
        return _lookup_vies(country, clean_id, timeout)
    else:
        return BusinessLookupResult(
            found=False,
            country=country,
            error="Automatski lookup nije podržan za ovu državu. Unesite podatke ručno.",
        )


# ══════════════════════════════════════════════════════════════════════════════
# HR LOOKUP
# ══════════════════════════════════════════════════════════════════════════════

def _lookup_hr(oib: str, company, fina_token: str, timeout: int) -> BusinessLookupResult:
    """HR: VIES → FINA Info.BIZ → not_vat_registered fallback."""

    from core.oib_validator import validate_oib_hr
    if not validate_oib_hr(oib):
        return BusinessLookupResult(
            found=False, country="HR", oib_valid=False,
            error="Neispravan OIB format (MOD 11,10 provjera nije prošla)."
        )

    # Korak 1: VIES
    vies = _lookup_vies("HR", oib, timeout)
    if vies.found:
        vies.country = "HR"
        vies.tax_id = oib
        # Enrichaj NKD naziv iz baze
        if vies.nkd:
            vies.nkd_name = _get_nkd_name(vies.nkd)
        return vies

    # Korak 2: FINA Info.BIZ (ako firma ima token)
    token = fina_token or _get_fina_token(company)
    if token:
        fina = _lookup_fina(oib, token, timeout)
        if fina.found:
            if fina.nkd:
                fina.nkd_name = _get_nkd_name(fina.nkd)
            return fina
        if fina.error and "token" in fina.error.lower():
            return fina  # Token greška — vrati odmah

    # Korak 3: OIB validan ali nije u registrima
    return BusinessLookupResult(
        found=False,
        source="vies",
        country="HR",
        tax_id=oib,
        oib_valid=True,
        not_vat_registered=True,
        error=(
            "OIB je formalno ispravan, ali firma nije pronađena u EU VIES registru "
            "(vjerojatno nije PDV obveznik — mikro poduzetnik, OPG, obrt). "
            "Unesite podatke ručno ili dodajte FINA Info.BIZ token u Postavkama."
            if not token else
            "Firma nije pronađena ni u VIES ni u FINA Info.BIZ registru. "
            "Unesite podatke ručno."
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# DE LOOKUP
# ══════════════════════════════════════════════════════════════════════════════

def _lookup_de(full_vat: str, clean_vat: str, timeout: int) -> BusinessLookupResult:
    """
    DE: VIES (USt-IdNr, samo PDV obveznici) → informativna poruka.

    NAPOMENA: Njemački Handelsregister (hrb-online.de) nije javno dostupan API.
    Unternehmensregister.de zahtijeva login.
    Za Kleinunternehmer (§19 UStG) — nema javnog API-ja, ručni unos.
    """
    # Normalizacija: DE + 9 znamenki
    vat_clean = clean_vat.lstrip("DE").lstrip("de").strip()

    # VIES validacija formata
    if not re.match(r"^\d{9}$", vat_clean):
        return BusinessLookupResult(
            found=False, country="DE", oib_valid=False,
            error="Neispravan format USt-IdNr. Očekivano: DE + 9 znamenki (npr. DE119948368)."
        )

    # VIES lookup
    vies = _lookup_vies("DE", vat_clean, timeout)
    if vies.found:
        vies.country = "DE"
        vies.tax_id = "DE" + vat_clean
        vies.vat_id = "DE" + vat_clean
        if vies.nkd:
            vies.wz_code = vies.nkd
            vies.wz_name = _get_wz_name(vies.nkd)
        return vies

    # VIES ne vraća podatke za DE Kleinunternehmer — jasna poruka
    return BusinessLookupResult(
        found=False,
        source="vies",
        country="DE",
        tax_id="DE" + vat_clean,
        oib_valid=True,
        not_vat_registered=True,
        error=(
            "Firma nije pronađena u EU VIES registru. Moguće: "
            "Kleinunternehmer (§19 UStG — oslobođen PDV-a), ili USt-IdNr nije aktivan. "
            "Unesite podatke ručno."
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# VIES (EU generički)
# ══════════════════════════════════════════════════════════════════════════════

def _lookup_vies(country_code: str, vat_number: str, timeout: int = 8) -> BusinessLookupResult:
    """SOAP poziv prema EU VIES servisu."""
    soap = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope'
        ' xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:urn="urn:ec.europa.eu:taxud:vies:services:checkVat:types">'
        "<soapenv:Body><urn:checkVat>"
        "<urn:countryCode>" + country_code.upper() + "</urn:countryCode>"
        "<urn:vatNumber>" + vat_number.strip() + "</urn:vatNumber>"
        "</urn:checkVat></soapenv:Body></soapenv:Envelope>"
    )
    try:
        r = requests.post(
            VIES_URL, data=soap,
            headers={"Content-Type": "text/xml"},
            timeout=timeout,
        )
    except requests.Timeout:
        return BusinessLookupResult(found=False, source="vies", error="VIES ne odgovara (timeout).")
    except requests.RequestException as exc:
        logger.warning("VIES error %s%s: %s", country_code, vat_number, exc)
        return BusinessLookupResult(found=False, source="vies", error="Greška pri spajanju na VIES.")

    if r.status_code != 200:
        return BusinessLookupResult(found=False, source="vies", error="VIES HTTP %d" % r.status_code)

    ns = "urn:ec.europa.eu:taxud:vies:services:checkVat:types"
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        return BusinessLookupResult(found=False, source="vies", error="Neispravan VIES odgovor.")

    def _t(tag):
        el = root.find(".//{%s}%s" % (ns, tag))
        return (el.text or "").strip() if el is not None else ""

    valid_str = _t("valid")
    if valid_str.lower() != "true":
        return BusinessLookupResult(found=False, source="vies", country=country_code)

    name = _t("name")
    raw_address = _t("address")
    parsed = _parse_vies_address(raw_address, country_code)

    return BusinessLookupResult(
        found=True,
        source="vies",
        country=country_code,
        name=name.title() if name and name != "---" else "",
        address=parsed.get("address", ""),
        city=parsed.get("city", ""),
        zip_code=parsed.get("zip_code", ""),
        raw={"vies_name": name, "vies_address": raw_address},
    )


def _parse_vies_address(raw: str, country: str = "HR") -> dict:
    """Parsira VIES adresu u komponente. Podržava HR i DE formate."""
    result = {"address": "", "city": "", "zip_code": ""}
    if not raw or raw.strip() in ("---", ""):
        return result
    raw = raw.strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]

    if country == "DE":
        # DE VIES format: "Straße 1, 12345 Stadt"
        if len(parts) >= 2:
            last = parts[-1]
            m = re.match(r"^(\d{5})\s+(.+)$", last)
            if m:
                result["zip_code"] = m.group(1)
                result["city"] = m.group(2).strip()
                result["address"] = ", ".join(parts[:-1])
                return result
        result["address"] = raw
        return result

    # HR/default format: "ULICA 10, ZAGREB, 10000 Zagreb"
    if len(parts) >= 2:
        last = parts[-1]
        m = re.match(r"^(\d{4,5})\s+(.+)$", last)
        if m:
            result["zip_code"] = m.group(1)
            result["city"] = m.group(2).title()
            remaining = parts[:-1]
            if remaining:
                city_base = result["city"].split("-")[0].strip().lower()
                if remaining[-1].strip().lower() == city_base:
                    remaining = remaining[:-1]
            result["address"] = ", ".join(p.title() for p in remaining)
            return result
        result["city"] = parts[-1].title()
        result["address"] = ", ".join(p.title() for p in parts[:-1])
    else:
        result["address"] = raw.title()
    return result


# ══════════════════════════════════════════════════════════════════════════════
# FINA Info.BIZ
# ══════════════════════════════════════════════════════════════════════════════

def _lookup_fina(oib: str, api_token: str, timeout: int = 8) -> BusinessLookupResult:
    """FINA Info.BIZ lookup — koristi se kad VIES ne vrati rezultat."""
    headers = {
        "Authorization": "Bearer " + api_token,
        "Accept": "application/json",
        "User-Agent": "LIMIT Connect/2.0",
    }
    endpoints = [
        "%s/subjekti/oib/%s" % (FINA_API_BASE, oib),
        "%s/search?oib=%s" % (FINA_API_BASE, oib),
        "%s/subjects/oib/%s" % (FINA_API_BASE, oib),
    ]
    for url in endpoints:
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return _parse_fina_response(r.json(), oib)
            elif r.status_code == 401:
                return BusinessLookupResult(
                    found=False, source="fina_infobiz",
                    error="Neispravan FINA Info.BIZ API token. Provjerite token u Postavkama → Integracije."
                )
            elif r.status_code == 403:
                return BusinessLookupResult(
                    found=False, source="fina_infobiz",
                    error="FINA API token nema dozvolu. Registrirajte se na %s" % FINA_REGISTER_URL
                )
        except requests.Timeout:
            return BusinessLookupResult(found=False, source="fina_infobiz", error="FINA API timeout.")
        except requests.RequestException as exc:
            logger.warning("FINA lookup error OIB %s: %s", oib, exc)

    return BusinessLookupResult(found=False, source="fina_infobiz",
                                error="Firma nije pronađena u FINA Info.BIZ.")


def _parse_fina_response(data: dict, oib: str) -> BusinessLookupResult:
    if isinstance(data, list):
        data = data[0] if data else {}
    if not data:
        return BusinessLookupResult(found=False, source="fina_infobiz")

    def _get(*keys):
        for k in keys:
            v = data.get(k, "")
            if v:
                return str(v).strip()
        return ""

    name = _get("naziv", "name", "tvrtka", "company_name")
    address = _get("ulica", "adresa", "address", "street")
    city = _get("mjesto", "grad", "city")
    zip_code = _get("pbr", "postanski_broj", "zip_code", "postal_code")
    mb = _get("mb", "maticni_broj", "matični_broj")
    nkd = _get("nkd", "nkd_kod", "djelatnost_kod")
    nkd_name = _get("djelatnost", "nkd_naziv", "activity_name")
    status = _get("status", "statusSubjekta")
    size = _get("velicina", "velicinaPoduzeca", "size")

    return BusinessLookupResult(
        found=bool(name),
        source="fina_infobiz",
        country="HR",
        name=name,
        tax_id=oib,
        mb=mb,
        address=address.title() if address else "",
        city=city.title() if city else "",
        zip_code=zip_code,
        nkd=nkd,
        nkd_name=nkd_name,
        status=status,
        size=size,
        raw=data,
    )


# ══════════════════════════════════════════════════════════════════════════════
# NKD / WZ ŠIFARNIK
# ══════════════════════════════════════════════════════════════════════════════

def _get_nkd_name(code: str) -> str:
    """Dohvati naziv HR NKD djelatnosti. Cache + DB fallback."""
    if not code:
        return ""
    code = code.strip()
    if code in _NKD_CACHE:
        return _NKD_CACHE[code]
    try:
        from companies.models import NKDCode
        obj = NKDCode.objects.filter(code=code).first()
        if obj:
            _NKD_CACHE[code] = obj.name_hr
            return obj.name_hr
        # Pokušaj bez točke (46900 → 46.90)
        normalized = _normalize_nkd(code)
        if normalized != code:
            obj = NKDCode.objects.filter(code=normalized).first()
            if obj:
                _NKD_CACHE[code] = obj.name_hr
                return obj.name_hr
    except DatabaseError as exc:
        logger.debug("NKD lookup error %s: %s", code, exc)
    return ""


def _get_wz_name(code: str) -> str:
    """Dohvati naziv DE WZ 2008 djelatnosti. Isti model kao NKD (NACE baza)."""
    if not code:
        return ""
    if code in _WZ_CACHE:
        return _WZ_CACHE[code]
    try:
        from companies.models import NKDCode
        obj = NKDCode.objects.filter(code=code).first()
        if obj:
            name = obj.name_en or obj.name_hr
            _WZ_CACHE[code] = name
            return name
    except DatabaseError:
        pass
    return ""


def _normalize_nkd(code: str) -> str:
    """46900 → 46.90, 4690 → 46.90, 469 → 46.9"""
    code = code.strip().replace(" ", "")
    # Već ima točku
    if "." in code:
        return code
    if len(code) == 5:
        return code[:2] + "." + code[2:]
    if len(code) == 4:
        return code[:2] + "." + code[2:]
    return code


def get_nkd_choices_for_select(query: str = "", limit: int = 20) -> list[dict]:
    """
    Za AJAX select2 dropdown — pretražuje NKD šifarnik.

    Poziva se iz:
      - invoicing/views.py (nova faktura — NKD kupca)
      - companies/views.py (profil tvrtke)
      - partners/views.py (partner forma)

    Vraća: [{"code": "46.90", "name": "Nespecijalizirana trgovina na veliko"}, ...]
    """
    try:
        from companies.models import NKDCode
        qs = NKDCode.objects.filter(is_active=True)
        if query:
            qs = qs.filter(
                models_Q_or_name(query)
            )
        return [
            {"code": obj.code, "name": obj.name_hr, "level": obj.level}
            for obj in qs[:limit]
        ]
    except DatabaseError as exc:
        logger.warning("NKD choices error: %s", exc)
        return []


def models_Q_or_name(query: str):
    """Pomoćna funkcija — izbjegava circular import."""
    from django.db.models import Q
    return Q(code__icontains=query) | Q(name_hr__icontains=query) | Q(name_en__icontains=query)


# ══════════════════════════════════════════════════════════════════════════════
# POMOĆNE FUNKCIJE
# ══════════════════════════════════════════════════════════════════════════════

def _strip_country_prefix(tax_id: str, country: str) -> str:
    """HR12345 → 12345, DE119948368 → 119948368"""
    prefix_map = {"HR": "HR", "DE": "DE", "AT": "AT", "SI": "SI", "IT": "IT"}
    prefix = prefix_map.get(country, "")
    if prefix and tax_id.upper().startswith(prefix):
        return tax_id[len(prefix):]
    return tax_id


def _get_fina_token(company) -> str:
    """Dohvati FINA token iz Company.settings."""
    if not company:
        return ""
    settings = getattr(company, "settings", None) or {}
    return settings.get("fina_infobiz_token", "").strip()


def _lookup_in_database(tax_id: str, country: str, company) -> Optional[BusinessLookupResult]:
    """Provjeri postoji li partner s ovim poreznim brojem u lokalnoj bazi."""
    if not company:
        return None
    try:
        from partners.models import Partner
        partner = Partner.objects.filter(company=company, oib=tax_id).first()
        if partner:
            return BusinessLookupResult(
                found=True,
                source="database",
                country=country,
                name=partner.name,
                tax_id=tax_id,
                address=partner.address or "",
                city=partner.city or "",
                zip_code=getattr(partner, "zip_code", ""),
                raw={"partner_id": partner.pk},
            )
    except DatabaseError:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE — direktna upotreba u views.py
# ══════════════════════════════════════════════════════════════════════════════

def lookup_business_json(tax_id: str, country: str = "HR", company=None) -> dict:
    """Shortcut koji odmah vraća dict za JsonResponse."""
    result = lookup_business(tax_id, country, company)
    return result.to_dict()
