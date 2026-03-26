"""
invoicing/fiscal_rules.py
Centralni engine za odluku o fiskalizaciji.
Korisnik NIKAD ne mora ručno odlučivati.

Pozivaju:
- Invoice.save() — auto-check
- POS checkout — skip fiscalization za exempt
- DocumentValidator — compliance check
"""
from typing import Tuple


# Doctypes koji NIKAD ne idu na fiskalizaciju
NON_FISCAL_DOCTYPES = frozenset({
    'PO',   # Ponuda
    'P',    # Predračun
    'OTP',  # Otpremnica
    'ZR',   # Zbirni račun
    'NAR',  # Narudžbenica
    'URA',  # Ulazni račun
    'GS',   # Gutschrift (DE)
})

# Doctypes koji UVIJEK idu na fiskalizaciju (HR)
FISCAL_DOCTYPES_HR = frozenset({
    'R', 'RN', 'A', 'S',
})


def should_fiscalize(invoice) -> Tuple[bool, str]:
    """
    Centralna odluka: ide li račun na HR fiskalizaciju?

    Vraća: (True/False, razlog_string)
    Korisnik vidi samo razlog ako je False — ne mora birati.
    """
    company = invoice.company if hasattr(invoice, 'company') and invoice.company_id else None

    # 1. DE račun — ne HR fiskalizacija
    country = getattr(invoice, 'country', 'HR') or 'HR'
    if country == 'DE':
        return False, 'DE račun — DSFinV-K, ne HR fiskalizacija'

    # 2. Firma je generalno exempt
    if company and getattr(company, 'fiscal_exempt', False):
        return False, 'Firma nije obveznik fiskalizacije'

    # 3. Doctype koji nikad ne ide
    doctype = getattr(invoice, 'doctype', '')
    if doctype in NON_FISCAL_DOCTYPES:
        return False, f'Vrsta dokumenta {doctype} ne fiskalizira se'

    # 4. Udruga s nonprofit artiklima
    if company and getattr(company, 'business_type', '') in ('udruga', 'ustanova'):
        try:
            items = invoice.items.all()
            if items.exists():
                all_nonprofit = all(
                    getattr(getattr(i, 'inventory_item', None), 'is_nonprofit_activity', False)
                    for i in items
                    if getattr(i, 'inventory_item_id', None)
                )
                if all_nonprofit:
                    return False, 'Svi artikli su nonprofit aktivnost udruge'
        except Exception:
            pass

    # 5. Iznos 0 — ne fiskalizira se
    total = getattr(invoice, 'total', 0)
    if total is not None and float(total) == 0:
        return False, 'Nulti iznos — fiskalizacija nije potrebna'

    # 6. HR gotovinski/bezgotovinski — ide
    if doctype in FISCAL_DOCTYPES_HR:
        return True, 'HR fiskalizacija obvezna'

    # 7. FA (B2B) — ide ako je HR
    if doctype == 'FA' and country == 'HR':
        return True, 'HR B2B fiskalizacija obvezna'

    return False, 'Nije prepoznat slučaj za fiskalizaciju'


def get_pdv_rate_for_item(item, company) -> Tuple[float, str]:
    """
    AI provjera PDV stope — je li stopa ispravna za NKD?
    Vraća: (stopa, upozorenje_ili_None)
    """
    nkd = getattr(company, 'nkd_code', None)
    nkd_code = getattr(nkd, 'code', '') if nkd else ''

    item_rate = float(getattr(item, 'tax_rate', 25) or 25)

    # Prehrambeni sektor: NKD 10.x, 47.2x, 56.x, 01.x → PDV 5% (HR, od 2024)
    food_nkds = ('10.', '47.2', '56.', '01.')
    if any(nkd_code.startswith(x) for x in food_nkds):
        if item_rate == 25:
            return 5.0, f'NKD {nkd_code} → prehrambeni sektor, PDV bi trebao biti 5% (ne 25%)'

    return item_rate, None
