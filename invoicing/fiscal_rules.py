"""
invoicing/fiscal_rules.py
Zakonski parametri za HR + DE — zabetonirani
Izvor: LEGAL_PARAMS_MASTER.md (2026-03-27)
JEDINA ISTINA o propisima u kodu.
"""
from datetime import date
from typing import Tuple, Optional


# ═══════════════════════════════════════
# HR PDV STOPE — po datumu i kategoriji
# ═══════════════════════════════════════

def get_hr_pdv_rate(invoice_date, category: str = 'standard') -> float:
    """
    Vraća ispravnu HR PDV stopu za dati datum i kategoriju.
    Koristi za validaciju — je li stopa na dokumentu ispravna?
    """
    if isinstance(invoice_date, str):
        from datetime import datetime
        invoice_date = datetime.strptime(invoice_date[:10], '%Y-%m-%d').date()
    
    y = invoice_date.year
    m = invoice_date.month
    d_val = invoice_date.day
    
    cat = category.lower()
    
    # RESTORANI / UGOSTITELJSTVO
    if cat in ('restaurant', 'ugostiteljstvo', 'catering'):
        if invoice_date < date(2020, 1, 1):
            return 25.0
        elif invoice_date < date(2022, 4, 1):
            return 13.0   # NN 121/19
        elif invoice_date < date(2024, 1, 1):
            return 5.0    # NN 39/22 COVID rasterecenje
        else:
            return 13.0   # NN 114/23 povratak
    
    # HRANA (osnovna: kruh, mlijeko, meso, voce, povrce, riba...)
    if cat in ('food', 'hrana', 'food_basic', 'food_processed', 'meso', 'voce', 'povrce'):
        if invoice_date < date(2022, 4, 1):
            # Kruh/mlijeko 5%, ostalo moze biti 25% — defaultamo na 5% za "hrana" kategoriju
            return 5.0
        else:
            return 5.0    # NN 39/22 prosireno na meso, voce, povrce...
    
    # PLIN / GRIJANJE
    if cat in ('gas', 'plin', 'grijanje', 'heating'):
        if invoice_date < date(2022, 4, 1):
            return 25.0
        elif invoice_date < date(2023, 4, 1):
            return 5.0    # Privremeno NN 39/22
        elif invoice_date < date(2025, 4, 1):
            return 13.0   # Produljeno NN 113/22 -> NN 35/24
        else:
            return 25.0   # Isteklo
    
    # SOLARNE PLOCE
    if cat in ('solar', 'solarne ploce', 'pv'):
        if invoice_date >= date(2022, 10, 1):
            return 0.0    # NN 113/22
        return 25.0
    
    # KULTURA / SPORT / KONCERTI
    if cat in ('culture', 'sport', 'concert', 'kultura', 'kazaliste'):
        if invoice_date < date(2022, 4, 1):
            return 13.0
        else:
            return 5.0    # NN 39/22
    
    # KNJIGE / NOVINE / CASOPISI
    if cat in ('books', 'knjige', 'novine', 'press'):
        return 5.0   # Uvijek 5% od 2013
    
    # STANDARDNA STOPA (default)
    return 25.0


# ═══════════════════════════════════════
# HR FISKALIZACIJA
# ═══════════════════════════════════════

def get_fiscal_version(invoice_date) -> Tuple[Optional[str], str]:
    """Vraca verziju fiskalizacije aktivnu na dati datum."""
    if isinstance(invoice_date, str):
        from datetime import datetime
        invoice_date = datetime.strptime(invoice_date[:10], '%Y-%m-%d').date()
    
    if invoice_date < date(2013, 1, 1):
        return None, 'Pre-fiskalizacija — nije bilo obaveze'
    elif invoice_date < date(2013, 7, 1):
        return '1.0', 'NN 133/12 — 1. krug obveznika'
    elif invoice_date < date(2020, 4, 1):
        return '1.0', 'NN 133/12 (izmjene) — ZKI + JIR'
    elif invoice_date < date(2021, 1, 1):
        return '1.1', 'NN 138/20 — + QR kod (od 01.04.2020.)'
    elif invoice_date < date(2024, 1, 1):
        return '1.2', 'NN 138/20 (puni) — ZKI + JIR + QR'
    elif invoice_date < date(2025, 9, 1):
        return '1.3', 'NN 114/23 — + napojnice (od 01.01.2024.)'
    elif invoice_date < date(2026, 1, 1):
        return '2.0', 'NN 89/25 — NOVI ZAKON (01.09.2025.), gotovinski'
    else:
        return '2.0+', 'NN 89/25 — + bezgotovinski + eRacun B2B (01.01.2026.)'


def requires_zki_jir(invoice_date) -> bool:
    """ZKI/JIR obavezni za gotovinske racune od 01.01.2013."""
    if isinstance(invoice_date, str):
        from datetime import datetime
        invoice_date = datetime.strptime(invoice_date[:10], '%Y-%m-%d').date()
    return invoice_date >= date(2013, 1, 1)


def requires_qr_code(invoice_date) -> bool:
    """QR kod obavezan od 01.04.2020."""
    if isinstance(invoice_date, str):
        from datetime import datetime
        invoice_date = datetime.strptime(invoice_date[:10], '%Y-%m-%d').date()
    return invoice_date >= date(2020, 4, 1)


# ═══════════════════════════════════════
# SHOULD_FISCALIZE — centralna odluka
# ═══════════════════════════════════════

NON_FISCAL_DOCTYPES = frozenset({'PO', 'P', 'OTP', 'ZR', 'NAR', 'URA'})
FISCAL_DOCTYPES_HR = frozenset({'R', 'R1', 'R2', 'RN', 'A', 'S', 'FA'})


def should_fiscalize(invoice) -> Tuple[bool, str]:
    """
    Centralna odluka: ide li racun na HR fiskalizaciju?
    Korisnik ne mora nista znati.
    """
    company = invoice.company
    country = getattr(invoice, 'country', 'HR') or 'HR'
    
    if country == 'DE':
        return False, 'DE racun — DSFinV-K, ne HR fiskalizacija'
    
    if getattr(company, 'fiscal_exempt', False):
        return False, 'Firma nije obveznik fiskalizacije'
    
    if invoice.doctype in NON_FISCAL_DOCTYPES:
        return False, f'Vrsta dokumenta {invoice.doctype} ne fiskalizira se'
    
    if company.business_type in ('udruga', 'ustanova'):
        try:
            items = invoice.items.all()
            if items.exists():
                all_nonprofit = all(
                    getattr(getattr(i, 'inventory_item', None), 'is_nonprofit_activity', False)
                    for i in items if getattr(i, 'inventory_item_id', None)
                )
                if all_nonprofit:
                    return False, 'Svi artikli su nonprofit aktivnost udruge'
        except Exception:
            pass
    
    total = getattr(invoice, 'total', 0) or 0
    if total == 0:
        return False, 'Nulti iznos — fiskalizacija nije potrebna'
    
    if invoice.doctype in FISCAL_DOCTYPES_HR:
        return True, 'HR fiskalizacija obavezna'
    
    return False, 'Nije prepoznat slucaj za fiskalizaciju'


# ═══════════════════════════════════════
# DE MwSt PROVJERA
# ═══════════════════════════════════════

def get_de_mwst_rate(invoice_date, category: str = 'standard') -> Tuple[float, Optional[str]]:
    """
    Vraca ispravnu DE MwSt stopu za dati datum.
    Ukljucuje COVID iznimku 07-12.2020.
    """
    if isinstance(invoice_date, str):
        from datetime import datetime
        invoice_date = datetime.strptime(invoice_date[:10], '%Y-%m-%d').date()
    
    covid_period = date(2020, 7, 1) <= invoice_date <= date(2020, 12, 31)
    
    cat = category.lower()
    
    # GASTRONOMIJA
    if cat in ('restaurant', 'gastronomie', 'speisen'):
        if invoice_date < date(2020, 7, 1):
            return 19.0, None
        elif covid_period:
            return 5.0, 'COVID period — 5% za gastronomiju'
        elif invoice_date <= date(2023, 12, 31):
            return 7.0, 'COVID rasterecenje produljeno do 31.12.2023.'
        else:
            return 19.0, 'Od 01.01.2024. gastronomija opet 19%'
    
    # OPCA STOPA
    if cat == 'standard':
        if covid_period:
            return 16.0, 'COVID period 07-12.2020. — 16% je LEGALNO'
        return 19.0, None
    
    # SNIZENA STOPA
    if cat in ('reduced', 'ermassigt', 'food', 'hrana', 'books', 'knjige'):
        if covid_period:
            return 5.0, 'COVID period — 5% snizena'
        return 7.0, None
    
    # SOLARNE PLOCE
    if cat in ('solar', 'pv'):
        if invoice_date >= date(2023, 1, 1):
            return 0.0, 'Nullsteuersatz od 01.01.2023. za PV sustave'
        return 19.0, None
    
    # Defaultno
    if covid_period:
        return 16.0, 'COVID period — provjeri tocnu kategoriju'
    return 19.0, None


# ═══════════════════════════════════════
# PDV STOPA PROVJERA ZA ARTIKL
# ═══════════════════════════════════════

def validate_item_pdv_rate(item, company, invoice_date) -> Tuple[float, Optional[str]]:
    """
    Za dani artikl i datum provjeri je li PDV stopa ispravna.
    Vraca (ocekivana_stopa, upozorenje_ili_None)
    """
    country = getattr(company, 'country', 'HR') or 'HR'
    nkd = getattr(company, 'nkd_code', None)
    nkd_code = getattr(nkd, 'code', '') if nkd else ''
    
    current_rate = getattr(item, 'tax_rate', None) or getattr(item, 'tax_percent', 25)
    
    if country == 'DE':
        expected, note = get_de_mwst_rate(invoice_date)
        return expected, note
    
    # HR — provjeri NKD
    food_nkds = ('10.', '47.2', '56.', '01.')
    restaurant_nkds = ('56.',)
    
    if any(nkd_code.startswith(x) for x in restaurant_nkds):
        expected = get_hr_pdv_rate(invoice_date, 'restaurant')
        if abs(float(current_rate) - expected) > 0.01:
            return expected, f'NKD {nkd_code} (ugostiteljstvo): ocekivana PDV {expected}%, postavljeno {current_rate}%'
    
    elif any(nkd_code.startswith(x) for x in food_nkds):
        expected = get_hr_pdv_rate(invoice_date, 'food')
        if abs(float(current_rate) - expected) > 0.01:
            return expected, f'NKD {nkd_code} (prehrambeni): ocekivana PDV {expected}%, postavljeno {current_rate}%'
    
    return float(current_rate), None


# ═══════════════════════════════════════
# PRODUKCIJSKI FILTER
# ═══════════════════════════════════════

def is_production_document(invoice) -> bool:
    """True = pravi produkcijski dokument koji treba compliance provjeru."""
    if getattr(invoice, 'synesis_id', None):
        return False
    issued = getattr(invoice, 'date_issued', None)
    if issued:
        year = issued.year if hasattr(issued, 'year') else 2000
        if year < 2026:
            return False
    return True
