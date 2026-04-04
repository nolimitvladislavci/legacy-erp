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


def validate_vat_id(vat_id: str, country: str = 'HR') -> bool:
    """Validacija VAT ID-a prema državi."""
    vat_id = vat_id.strip()
    if not vat_id:
        return False

    if country == 'HR':
        # HR OIB: 11 znamenki
        return validate_oib_hr(vat_id)
    elif country == 'DE':
        # DE USt-IdNr: DE + 9 znamenki
        return (vat_id.upper().startswith('DE')
                and len(vat_id) == 11
                and vat_id[2:].isdigit())
    elif country == 'AT':
        # AT UID: ATU + 8 znamenki
        return (vat_id.upper().startswith('ATU')
                and len(vat_id) == 11)
    elif country == 'SI':
        # SI DDV: SI + 8 znamenki
        return (vat_id.upper().startswith('SI')
                and len(vat_id) == 10
                and vat_id[2:].isdigit())
    elif country == 'IT':
        # IT IVA: IT + 11 znamenki
        return (vat_id.upper().startswith('IT')
                and len(vat_id) == 13
                and vat_id[2:].isdigit())
    else:
        # Generic EU VAT: 2-letter prefix + min 5 chars
        return bool(re.match(r'^[A-Z]{2}[A-Z0-9]{5,}$', vat_id.upper()))


def normalize_oib(oib: str, country: str = 'HR') -> str:
    """Normalizira OIB/VAT — ukloni razmake, pretvori DE/AT prefix u uppercase."""
    oib = oib.strip()
    if country != 'HR':
        # Strip prefix za internu pohranu (VIES prima bez prefiksa za HR)
        prefix_map = {'DE': 'DE', 'AT': 'AT', 'SI': 'SI'}
        prefix = prefix_map.get(country, '')
        if prefix and oib.upper().startswith(prefix):
            return oib.upper()
    return oib


def format_oib_display(oib: str, country: str = 'HR') -> str:
    """Formatiraj OIB/VAT za prikaz."""
    if country == 'HR':
        return f"OIB: {oib}"
    elif country == 'DE':
        return f"USt-IdNr: {oib}"
    elif country == 'AT':
        return f"UID: {oib}"
    elif country == 'SI':
        return f"DDV: {oib}"
    return f"VAT: {oib}"


def strip_vat_prefix(vat_id: str, country: str = 'HR') -> str:
    """
    Ukloni prefix države iz VAT ID-a za VIES upite.
    VIES prima: country_code='HR', vat_number='12345678901' (bez HR/DE prefiksa).
    """
    vat_id = vat_id.strip().upper()
    prefix_map = {
        'DE': 'DE',
        'AT': 'AT',
        'SI': 'SI',
        'IT': 'IT',
        'FR': 'FR',
        'NL': 'NL',
    }
    prefix = prefix_map.get(country, country)
    if vat_id.startswith(prefix):
        return vat_id[len(prefix):]
    return vat_id


# ── IBAN + MBS validacija (dodano 03.04.2026.) ─────────────────────────────

def validate_iban(iban: str) -> bool:
    """ISO 13616 MOD 97 IBAN validacija."""
    iban = iban.strip().replace(' ', '').upper()
    if len(iban) < 15 or len(iban) > 34:
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = ''
    for ch in rearranged:
        if ch.isdigit():
            numeric += ch
        elif ch.isalpha():
            numeric += str(ord(ch) - ord('A') + 10)
        else:
            return False
    return int(numeric) % 97 == 1


def validate_hr_iban(iban: str) -> bool:
    """HR IBAN: HR + 2 kontrolne + 7 bankovnih + 10 računa = 21 znak."""
    iban = iban.strip().replace(' ', '').upper()
    if not iban.startswith('HR') or len(iban) != 21:
        return False
    return validate_iban(iban)


def validate_mbs(mbs: str) -> bool:
    """MBS: točno 8 znamenki."""
    mbs = mbs.strip()
    return bool(mbs and len(mbs) == 8 and mbs.isdigit())
