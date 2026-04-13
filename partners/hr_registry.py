"""
HR poslovni registar lookup putem EU VIES sustava.
Besplatan, sluzbeni EU sustav za provjeru VAT/OIB brojeva.
"""

import logging
import re
from xml.etree import ElementTree as ET

try:
    import requests as _requests

    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

logger = logging.getLogger(__name__)

VIES_URL = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"


def _build_soap(country_code, vat_number):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<soapenv:Envelope"
        ' xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:urn="urn:ec.europa.eu:taxud:vies:services:checkVat:types">'
        "<soapenv:Body>"
        "<urn:checkVat>"
        "<urn:countryCode>" + country_code.upper() + "</urn:countryCode>"
        "<urn:vatNumber>" + vat_number.strip() + "</urn:vatNumber>"
        "</urn:checkVat>"
        "</soapenv:Body>"
        "</soapenv:Envelope>"
    )


def _vies_text(el, tag):
    ns = "urn:ec.europa.eu:taxud:vies:services:checkVat:types"
    child = el.find("{" + ns + "}" + tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def _parse_address(raw):
    """
    Parsira VIES adresu u komponente.

    VIES HR comma format: "ULICA 10, ZAGREB, 10000 Zagreb"
    Fallback newline:     "ULICA 10\n10000 ZAGREB\nHRVATSKA"
    """
    result = {"address": "", "city": "", "zip_code": ""}
    if not raw or raw.strip() in ("---", ""):
        return result

    raw = raw.strip()

    # Comma-separated (dominant VIES HR format)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) >= 2:
        last = parts[-1]
        m = re.match(r"^(\d{4,5})\s+(.+)$", last)
        if m:
            result["zip_code"] = m.group(1)
            result["city"] = m.group(2).title()
            remaining = parts[:-1]
            # Drop the redundant ALL-CAPS city token if it matches
            if remaining:
                city_base = result["city"].split("-")[0].strip().lower()
                if remaining[-1].strip().lower() == city_base:
                    remaining = remaining[:-1]
            result["address"] = ", ".join(p.title() for p in remaining)
            return result
        # No ZIP in last part
        result["city"] = parts[-1].title()
        result["address"] = ", ".join(p.title() for p in parts[:-1])
        return result

    # Newline-separated fallback
    lines = [l.strip() for l in raw.replace("\r", "").split("\n") if l.strip()]
    if not lines:
        return result
    if len(lines) >= 3 and not any(c.isdigit() for c in lines[-1]):
        lines = lines[:-1]
    city_line = lines[-1] if lines else ""
    m = re.match(r"^(\d{4,5})\s+(.+)$", city_line)
    if m:
        result["zip_code"] = m.group(1)
        result["city"] = m.group(2).title()
        lines = lines[:-1]
    else:
        result["city"] = city_line.title()
        lines = lines[:-1]
    result["address"] = ", ".join(l.title() for l in lines)
    return result


class VIESLookup:
    def __init__(self, timeout=10):
        self.timeout = timeout

    def check_vat(self, country_code, vat_number):
        if not _HAS_REQUESTS:
            return {"valid": False, "error": "requests nije instaliran"}
        payload = _build_soap(country_code, vat_number)
        try:
            resp = _requests.post(
                VIES_URL,
                data=payload.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return self._parse(resp.text, country_code)
        except _requests.exceptions.Timeout:
            logger.warning("VIES timeout %s%s", country_code, vat_number)
            return {"valid": False, "error": "VIES ne odgovara (timeout)"}
        except _requests.exceptions.ConnectionError:
            return {"valid": False, "error": "Nema veze s VIES servisom"}
        except requests.RequestException as exc:
            logger.exception("VIES error %s%s", country_code, vat_number)
            return {"valid": False, "error": str(exc)}

    def _parse(self, xml_text, country_code):
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            return {"valid": False, "error": "XML parse greska: " + str(exc)}

        fault = root.find(".//faultstring")
        if fault is not None and fault.text:
            err = fault.text.strip()
            if "INVALID" in err.upper():
                return {"valid": False, "error": "OIB/VAT nije pronaden u registru"}
            return {"valid": False, "error": "VIES: " + err}

        ns = "urn:ec.europa.eu:taxud:vies:services:checkVat:types"
        cvr = root.find(".//{" + ns + "}checkVatResponse")
        if cvr is None:
            return {"valid": False, "error": "Nema odgovora iz VIES-a"}

        is_valid = _vies_text(cvr, "valid").lower() == "true"
        name = _vies_text(cvr, "name")
        address_raw = _vies_text(cvr, "address")

        if name in ("---", ""):
            name = ""
        if address_raw in ("---", ""):
            address_raw = ""

        parsed = _parse_address(address_raw)
        return {
            "valid": is_valid,
            "name": name.title() if name else "",
            "address_raw": address_raw,
            "address": parsed["address"],
            "city": parsed["city"],
            "zip_code": parsed["zip_code"],
            "country_code": country_code.upper(),
            "error": None,
        }


class PartnerAutoCreator:
    def __init__(self):
        self.vies = VIESLookup()

    def lookup_oib(self, oib, country="HR"):
        from core.oib_validator import strip_vat_prefix

        vat_number = strip_vat_prefix(oib, country)
        result = self.vies.check_vat(country, vat_number)
        result["source"] = "vies"
        return result

    def create_from_oib(self, oib, company, country="HR"):
        from partners.models import Partner

        existing = Partner.objects.filter(company=company, oib=oib).first()
        if existing:
            return existing, False, "Partner vec postoji"
        result = self.lookup_oib(oib, country)
        partner = Partner.objects.create(
            company=company,
            name=result.get("name") or ("Partner " + oib),
            oib=oib,
            address=result.get("address", ""),
            city=result.get("city", ""),
            country=country,
            partner_type="client",
            is_active=True,
        )
        msg = "Kreiran iz VIES registra" if result.get("valid") else "Kreiran (VIES podataka nije bilo)"
        return partner, True, msg
