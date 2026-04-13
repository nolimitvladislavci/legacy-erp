"""
OIB / VAT ID validator za HR, DE, AT i generičke EU formate.
"""

import re


def validate_oib_hr(oib: str) -> bool:
    """ISO 7064 MOD 11,10 validacija hrvatskog OIB-a (11 znamenki)."""
    if len(oib) != 11 or not oib.isdigit():
        return False
    total = 10
    for digit in oib[:-1]:
        total = (total + int(digit)) % 10
        if total == 0:
            total = 10
        total = (total * 2) % 11
    kontrolni = (11 - total) % 10
    return kontrolni == int(oib[-1])


def validate_vat_id(vat_id: str, country: str = "HR") -> bool:
    """Validacija VAT ID-a prema državi."""
    vat_id = vat_id.strip()
    if not vat_id:
        return False

    if country == "HR":
        # HR OIB: 11 znamenki
        return validate_oib_hr(vat_id)
    elif country == "DE":
        # DE USt-IdNr: DE + 9 znamenki
        return vat_id.upper().startswith("DE") and len(vat_id) == 11 and vat_id[2:].isdigit()
    elif country == "AT":
        # AT UID: ATU + 8 znamenki
        return vat_id.upper().startswith("ATU") and len(vat_id) == 11
    elif country == "SI":
        # SI DDV: SI + 8 znamenki
        return vat_id.upper().startswith("SI") and len(vat_id) == 10 and vat_id[2:].isdigit()
    elif country == "IT":
        # IT IVA: IT + 11 znamenki
        return vat_id.upper().startswith("IT") and len(vat_id) == 13 and vat_id[2:].isdigit()
    else:
        # Generic EU VAT: 2-letter prefix + min 5 chars
        return bool(re.match(r"^[A-Z]{2}[A-Z0-9]{5,}$", vat_id.upper()))


def normalize_oib(oib: str, country: str = "HR") -> str:
    """Normalizira OIB/VAT — ukloni razmake, pretvori DE/AT prefix u uppercase."""
    oib = oib.strip()
    if country != "HR":
        # Strip prefix za internu pohranu (VIES prima bez prefiksa za HR)
        prefix_map = {"DE": "DE", "AT": "AT", "SI": "SI"}
        prefix = prefix_map.get(country, "")
        if prefix and oib.upper().startswith(prefix):
            return oib.upper()
    return oib


def format_oib_display(oib: str, country: str = "HR") -> str:
    """Formatiraj OIB/VAT za prikaz."""
    if country == "HR":
        return f"OIB: {oib}"
    elif country == "DE":
        return f"USt-IdNr: {oib}"
    elif country == "AT":
        return f"UID: {oib}"
    elif country == "SI":
        return f"DDV: {oib}"
    return f"VAT: {oib}"


def strip_vat_prefix(vat_id: str, country: str = "HR") -> str:
    """
    Ukloni prefix države iz VAT ID-a za VIES upite.
    VIES prima: country_code='HR', vat_number='12345678901' (bez HR/DE prefiksa).
    """
    vat_id = vat_id.strip().upper()
    prefix_map = {
        "DE": "DE",
        "AT": "AT",
        "SI": "SI",
        "IT": "IT",
        "FR": "FR",
        "NL": "NL",
    }
    prefix = prefix_map.get(country, country)
    if vat_id.startswith(prefix):
        return vat_id[len(prefix) :]
    return vat_id


# ── IBAN + MBS validacija (dodano 03.04.2026.) ─────────────────────────────


def validate_iban(iban: str) -> bool:
    """ISO 13616 MOD 97 IBAN validacija."""
    iban = iban.strip().replace(" ", "").upper()
    if len(iban) < 15 or len(iban) > 34:
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = ""
    for ch in rearranged:
        if ch.isdigit():
            numeric += ch
        elif ch.isalpha():
            numeric += str(ord(ch) - ord("A") + 10)
        else:
            return False
    return int(numeric) % 97 == 1


def validate_hr_iban(iban: str) -> bool:
    """HR IBAN: HR + 2 kontrolne + 7 bankovnih + 10 računa = 21 znak."""
    iban = iban.strip().replace(" ", "").upper()
    if not iban.startswith("HR") or len(iban) != 21:
        return False
    return validate_iban(iban)


def validate_mbs(mbs: str) -> bool:
    """MBS: točno 8 znamenki."""
    mbs = mbs.strip()
    return bool(mbs and len(mbs) == 8 and mbs.isdigit())


# ═══════════════════════════════════════════════════════════════════════════
# LIVESTOCK IDENTIFIKACIJA — JIBG, JZB, UELN, Tetovir
# ═══════════════════════════════════════════════════════════════════════════


def validate_jibg(jibg: str) -> dict:
    """
    JIBG — Jedinstveni identifikacijski broj gospodarstva.
    Format: HR + 8 znamenki (npr. HR30157757).
    Pravilnik NN 96/2015.
    """
    j = jibg.strip().upper().replace(" ", "")
    if not j.startswith("HR"):
        return {"valid": False, "error": "JIBG mora poceti s HR", "value": j, "formatted": j}
    digits = j[2:]
    if not digits.isdigit():
        return {"valid": False, "error": "JIBG mora sadrzavati samo brojeve nakon HR", "value": j, "formatted": j}
    if len(digits) < 6 or len(digits) > 12:
        return {
            "valid": False,
            "error": f"JIBG ima {len(digits)} znamenki — ocekivano 6-12",
            "value": j,
            "formatted": j,
        }
    formatted = f"HR {digits}"
    return {"valid": True, "error": None, "value": j, "formatted": formatted}


def validate_jzb(jzb: str) -> dict:
    """
    JZB — Jedinstveni zivotinjski broj (goveda, ovce, koze).
    Format: HR + 10 znamenki (npr. HR0123456789).
    EU Regulation 1760/2000.
    """
    j = jzb.strip().upper().replace(" ", "")
    if not j.startswith("HR"):
        return {"valid": False, "error": "JZB mora poceti s HR", "value": j}
    digits = j[2:]
    if not digits.isdigit() or len(digits) != 10:
        return {"valid": False, "error": "JZB mora imati tocno 10 znamenki nakon HR", "value": j}
    formatted = f"HR {digits[:4]} {digits[4:]}"
    return {"valid": True, "error": None, "value": j, "formatted": formatted}


def validate_ueln(ueln: str) -> dict:
    """
    UELN — Universal Equine Life Number (konji, magarci).
    Format: 15 znakova (3 country + 3 database + 9 individual).
    ISO/TS 26740, EC 504/2008.
    """
    u = ueln.strip().upper().replace(" ", "").replace("-", "")
    if len(u) != 15:
        return {"valid": False, "error": f"UELN mora imati 15 znakova, ima {len(u)}", "value": u}
    if not u[:3].isalnum() or not u[3:6].isalnum():
        return {"valid": False, "error": "UELN: prvih 6 znakova mora biti alfanumericko", "value": u}
    formatted = f"{u[:3]} {u[3:6]} {u[6:]}"
    return {"valid": True, "error": None, "value": u, "formatted": formatted}


def validate_chip_iso(chip: str) -> dict:
    """
    Mikrocip/transponder — ISO 11784/11785.
    Format: 15 znamenki. Prva 3 = drzavni kod (191 = Hrvatska).
    134.2 kHz, FDX-B ili HDX.
    """
    c = chip.strip().replace(" ", "")
    if not c.isdigit():
        return {"valid": False, "error": "Chip mora sadrzavati samo brojeve", "value": c}
    if len(c) != 15:
        return {"valid": False, "error": f"ISO chip mora imati 15 znamenki, ima {len(c)}", "value": c}
    country_code = c[:3]
    country_names = {
        "191": "Hrvatska",
        "276": "Njemacka",
        "040": "Austrija",
        "705": "Slovenija",
        "070": "Bosna i Hercegovina",
        "380": "Italija",
        "826": "UK",
        "250": "Francuska",
    }
    country = country_names.get(country_code, f"Kod {country_code}")
    formatted = f"{c[:3]} {c[3:7]} {c[7:11]} {c[11:]}"
    return {
        "valid": True,
        "error": None,
        "value": c,
        "formatted": formatted,
        "country_code": country_code,
        "country": country,
    }


def validate_nkd(nkd: str) -> dict:
    """
    NKD — Nacionalna klasifikacija djelatnosti.
    Format: XX.XX (npr. 01.41 = goveda, 01.46 = svinje).
    """
    n = nkd.strip()
    import re

    if not re.match(r"^\d{2}\.\d{2}$", n):
        return {"valid": False, "error": "NKD format: XX.XX (npr. 01.41)", "value": n}
    nkd_names = {
        "01.11": "Uzgoj zitarica",
        "01.13": "Uzgoj povrca",
        "01.21": "Uzgoj grozdja",
        "01.24": "Uzgoj jezgr. voca",
        "01.41": "Uzgoj muznih krava",
        "01.42": "Uzgoj goveda za meso",
        "01.43": "Uzgoj konja",
        "01.45": "Uzgoj ovaca i koza",
        "01.46": "Uzgoj svinja",
        "01.47": "Uzgoj peradi",
        "01.49": "Uzgoj ostalih zivotinja (pcele, zecevi)",
        "56.10": "Restorani",
        "56.30": "Kafici i barovi",
        "10.11": "Prerada mesa",
        "10.51": "Mljekare",
        "47.11": "Maloprodaja",
        "86.21": "Opca med. praksa",
    }
    name = nkd_names.get(n, "")
    return {"valid": True, "error": None, "value": n, "name": name}
