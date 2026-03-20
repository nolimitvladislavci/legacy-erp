"""
invoicing/tax_logic.py

Centralna PDV/USt logika za HR i DE fakturiranje.
Podrška: HR (PDV 25%/13%/5%), DE (MwSt 19%/7%), Reverse Charge, Kleinunternehmer §19.
"""
from decimal import Decimal, ROUND_HALF_UP

# ─── Tax Profiles ────────────────────────────────────────────────────────────

TAX_PROFILES = {
    'HR': {
        'standard':    Decimal('25'),
        'reduced':     Decimal('13'),
        'reduced2':    Decimal('5'),
        'zero':        Decimal('0'),
        'currency':    'EUR',
        'law':         'Zakon o PDV-u',
        'authority':   'Porezna uprava RH',
    },
    'DE': {
        'standard':    Decimal('19'),
        'reduced':     Decimal('7'),
        'zero':        Decimal('0'),
        'currency':    'EUR',
        'law':         'Umsatzsteuergesetz (UStG)',
        'authority':   'Bundeszentralamt fuer Steuern',
    },
    'EU': {
        'standard':    Decimal('0'),   # Reverse Charge default
        'zero':        Decimal('0'),
        'currency':    'EUR',
    },
}

TAX_STATUS_CHOICES = [
    ('standard',          'Standardna stopa'),
    ('reduced',           'Snizena stopa'),
    ('zero',              'Nulta stopa'),
    ('reverse_charge',    'Prijenos porezne obveze (Reverse Charge)'),
    ('exempt',            'Oslobodeno PDV-a'),
    ('pausalac',          'Pausalni obrtnik - nije u sustavu PDV-a'),
    ('kleinunternehmer',  'Kleinunternehmer - §19 UStG'),
]

# ─── Core calculation ─────────────────────────────────────────────────────────

def calculate_tax(base_amount, tax_rate=None, tax_status=None, country='HR'):
    """
    Izracunaj iznos PDV-a i ukupni iznos.

    Args:
        base_amount (Decimal|float|str): Iznos bez PDV-a
        tax_rate    (Decimal|float|None): Eksplicitna stopa; ako None, izvodi se iz tax_status + country
        tax_status  (str|None): 'standard', 'reduced', 'zero', 'reverse_charge', 'exempt',
                                'pausalac', 'kleinunternehmer'
        country     (str): 'HR', 'DE', itd.

    Returns:
        dict: {
            'base':       Decimal,
            'tax_rate':   Decimal,
            'tax_amount': Decimal,
            'total':      Decimal,
            'tax_status': str,
        }
    """
    base = Decimal(str(base_amount))

    # Determiniraj stopu
    if tax_rate is not None:
        rate = Decimal(str(tax_rate))
        status = tax_status or 'standard'
    elif tax_status in ('pausalac', 'kleinunternehmer', 'exempt', 'reverse_charge', 'zero'):
        rate = Decimal('0')
        status = tax_status
    elif tax_status == 'reduced':
        profile = TAX_PROFILES.get(country, TAX_PROFILES['HR'])
        rate = profile.get('reduced', Decimal('0'))
        status = 'reduced'
    elif tax_status == 'reduced2':
        profile = TAX_PROFILES.get(country, TAX_PROFILES['HR'])
        rate = profile.get('reduced2', Decimal('0'))
        status = 'reduced2'
    else:
        profile = TAX_PROFILES.get(country, TAX_PROFILES['HR'])
        rate = profile.get('standard', Decimal('25'))
        status = 'standard'

    tax_amount = (base * rate / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total = base + tax_amount

    return {
        'base':       base,
        'tax_rate':   rate,
        'tax_amount': tax_amount,
        'total':      total,
        'tax_status': status,
    }


def calculate_items(items, country='HR'):
    """
    Izracunaj PDV za listu stavki.

    Args:
        items: lista dict-ova s kljucevima:
               'qty', 'price', 'tax_rate' (opt), 'tax_status' (opt)
        country: 'HR', 'DE'

    Returns:
        dict: {
            'items':     [enriched item dicts],
            'subtotal':  Decimal,
            'tax_total': Decimal,
            'total':     Decimal,
        }
    """
    enriched = []
    subtotal = Decimal('0')
    tax_total = Decimal('0')

    for item in items:
        qty   = Decimal(str(item.get('qty', 1)))
        price = Decimal(str(item.get('price', 0)))
        base  = qty * price
        calc  = calculate_tax(
            base_amount=base,
            tax_rate=item.get('tax_rate'),
            tax_status=item.get('tax_status'),
            country=country,
        )
        subtotal  += calc['base']
        tax_total += calc['tax_amount']
        enriched.append({**item, **calc, 'qty': qty, 'price': price, 'base': base})

    return {
        'items':     enriched,
        'subtotal':  subtotal,
        'tax_total': tax_total,
        'total':     subtotal + tax_total,
    }


# ─── Reverse Charge ───────────────────────────────────────────────────────────

def is_reverse_charge(company, client_vat_id, client_country_code):
    """
    Provjeri primjenjuje li se EU B2B Reverse Charge.

    Uvjeti:
    - Tvrtka ima VAT ID (EU porezni obveznik)
    - Klijent ima VAT ID
    - Klijent nije iz iste drzave

    Returns: bool
    """
    if not company:
        return False
    company_vat = getattr(company, 'vat_id', None) or getattr(company, 'oib', None)
    if not company_vat:
        return False
    if not client_vat_id or not str(client_vat_id).strip():
        return False
    company_country = (getattr(company, 'country', None) or 'HR').upper()
    client_cc = (client_country_code or '').upper()
    if not client_cc or client_cc == company_country:
        return False
    return True


# ─── Kleinunternehmer ────────────────────────────────────────────────────────

def check_kleinunternehmer_eligibility(company, prev_year_revenue, current_year_revenue_estimate=None):
    """
    Provjeri pravo na Kleinunternehmer status (DE §19 UStG).

    Limit 2024+: prethodna godina <= 22.000 EUR i tekuca procjena <= 50.000 EUR.

    Returns:
        dict: {
            'eligible':  bool,
            'reason':    str,
            'prev_year': Decimal,
            'limit':     Decimal,
        }
    """
    PREV_YEAR_LIMIT    = Decimal('22000')
    CURRENT_YEAR_LIMIT = Decimal('50000')

    prev = Decimal(str(prev_year_revenue))
    reason = ''
    eligible = True

    if prev > PREV_YEAR_LIMIT:
        eligible = False
        reason = f'Prihod prethodne godine {prev:.2f} EUR prelazi limit od {PREV_YEAR_LIMIT} EUR'

    if eligible and current_year_revenue_estimate is not None:
        curr = Decimal(str(current_year_revenue_estimate))
        if curr > CURRENT_YEAR_LIMIT:
            eligible = False
            reason = f'Procijenjen prihod tekuce godine {curr:.2f} EUR prelazi limit od {CURRENT_YEAR_LIMIT} EUR'

    if eligible and not reason:
        reason = 'Ispunjeni uvjeti za Kleinunternehmer status'

    return {
        'eligible':  eligible,
        'reason':    reason,
        'prev_year': prev,
        'limit':     PREV_YEAR_LIMIT,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_tax_rates(country='HR'):
    """
    Vrati listu dict-ova s poreznim stopama za danu drzavu.

    Returns:
        list[dict]: [{'rate': Decimal, 'label': str, 'status': str}]
    """
    profile = TAX_PROFILES.get(country.upper(), TAX_PROFILES['HR'])
    rates = []
    for key in ('standard', 'reduced', 'reduced2', 'zero'):
        if key in profile:
            label_map = {
                'standard':  'Standardna stopa',
                'reduced':   'Snizena stopa',
                'reduced2':  'Snizena stopa 2',
                'zero':      'Nulta stopa',
            }
            rates.append({
                'rate':   profile[key],
                'label':  label_map.get(key, key),
                'status': key,
            })
    return rates


def get_tax_statuses():
    """Vrati TAX_STATUS_CHOICES kao listu dict-ova."""
    return [{'value': v, 'label': l} for v, l in TAX_STATUS_CHOICES]


def get_applicable_rate(company, invoice_country='HR', reverse_charge=False):
    """
    Vrati preporucenu stopu (Decimal) i opis za fakturu.

    Returns: (rate: Decimal, note: str)
    """
    if reverse_charge:
        return Decimal('0'), 'reverse_charge'

    if not company:
        profile = TAX_PROFILES.get(invoice_country, TAX_PROFILES['HR'])
        return profile.get('standard', Decimal('25')), 'standard'

    status  = getattr(company, 'pdv_status', 'none')
    country = getattr(company, 'country', invoice_country) or invoice_country

    if status in ('pausalac', 'kleinunternehmer'):
        return Decimal('0'), status

    profile = TAX_PROFILES.get(country.upper(), TAX_PROFILES['HR'])
    return profile.get('standard', Decimal('25')), 'standard'


def get_pdv_footer_note(company, reverse_charge=False, lang='hr'):
    """Vrati zakonski tekst za footer fakture."""
    if reverse_charge:
        if lang == 'de':
            return ('Steuerschuldnerschaft des Leistungsempfaengers '
                    '(Reverse Charge, Art. 196 MwStSystRL)')
        return ('Porezna obveza prelazi na primatelja usluge '
                '(Reverse Charge, cl. 196 Direktive 2006/112/EZ)')

    if not company:
        return ''

    status = getattr(company, 'pdv_status', 'none')
    if status == 'pausalac':
        return 'Pausalni obrtnik - nije u sustavu PDV-a (cl. 90. st. 2. Zakona o PDV-u).'
    if status == 'kleinunternehmer':
        return 'Gemass §19 UStG wird keine Umsatzsteuer berechnet.'
    return ''
