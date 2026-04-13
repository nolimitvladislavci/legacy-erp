"""
Hrvatski bruto-neto kalkulator za obracun placa.
Zakon o porezu na dohodak + Zakon o doprinosima (2025/2026).
"""
from decimal import ROUND_HALF_UP, Decimal

# Doprinosi iz bruto place (employee contributions) - UVIJEK 20% ukupno
DOPRINOS_MIO_1 = Decimal('0.20')        # I stup MIO - 20% (bez II stupa)
DOPRINOS_MIO_1_WITH_2ND = Decimal('0.15')  # I stup = 15% (s II stupom)
DOPRINOS_MIO_2_PILLAR = Decimal('0.05')    # II stup = 5%

# Doprinosi NA bruto (employer)
DOPRINOS_ZDRAVSTVO = Decimal('0.165')  # Zdravstveno - 16.5%

# Porez na dohodak - 2 razreda
POREZ_STOPA_1 = Decimal('0.20')  # 20% do 4200 EUR/mj
POREZ_STOPA_2 = Decimal('0.30')  # 30% iznad
POREZ_PRAG_MJESECNI = Decimal('4200.00')

# Prirez po gradovima
PRIREZ_RATES = {
    'zagreb': Decimal('0.18'),
    'split': Decimal('0.15'),
    'rijeka': Decimal('0.15'),
    'osijek': Decimal('0.13'),
    'zadar': Decimal('0.12'),
    'slavonski_brod': Decimal('0.12'),
    'pula': Decimal('0.15'),
    'karlovac': Decimal('0.12'),
    'sisak': Decimal('0.10'),
    'varazdin': Decimal('0.10'),
    'cepin': Decimal('0.10'),
    'beli_manastir': Decimal('0.06'),
    'vukovar': Decimal('0.00'),
    'default': Decimal('0.00'),
}

# Osobni odbitak
OSOBNI_ODBITAK_BASE = Decimal('560.00')
ODBITAK_KOEF = {
    'dijete_1': Decimal('0.7'),
    'dijete_2': Decimal('1.0'),
    'dijete_3': Decimal('1.4'),
    'dijete_4': Decimal('1.9'),
    'dijete_5': Decimal('2.5'),
    'suprug': Decimal('0.7'),
    'invalidnost_djelomicna': Decimal('0.4'),
    'invalidnost_potpuna': Decimal('1.5'),
}


def izracunaj_osobni_odbitak(uzdrzavani=None, invalidnost=False):
    """Izracunaj ukupni mjesecni osobni odbitak."""
    odbitak = OSOBNI_ODBITAK_BASE
    if uzdrzavani:
        for clan in uzdrzavani:
            koef = ODBITAK_KOEF.get(clan, Decimal('0'))
            odbitak += OSOBNI_ODBITAK_BASE * koef
    if invalidnost:
        odbitak += OSOBNI_ODBITAK_BASE * ODBITAK_KOEF['invalidnost_djelomicna']
    return odbitak.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def izracunaj_placu(bruto, osobni_odbitak=None, prirez_grad='default',
                     drugi_stup=False, uzdrzavani=None, invalidnost=False):
    """
    Kompletni obracun place: bruto -> neto.

    Returns dict with full breakdown.
    """
    bruto = Decimal(str(bruto))

    # 1. Doprinosi iz bruto (employee) - uvijek 20%
    if drugi_stup:
        mio_1_rate = DOPRINOS_MIO_1_WITH_2ND
        mio_2_rate = DOPRINOS_MIO_2_PILLAR
    else:
        mio_1_rate = DOPRINOS_MIO_1
        mio_2_rate = Decimal('0')

    mio_1 = (bruto * mio_1_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    mio_2 = (bruto * mio_2_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    ukupno_doprinosi_iz = mio_1 + mio_2

    # 2. Dohodak
    dohodak = bruto - ukupno_doprinosi_iz

    # 3. Osobni odbitak
    if osobni_odbitak is None:
        osobni_odbitak = izracunaj_osobni_odbitak(uzdrzavani, invalidnost)
    else:
        osobni_odbitak = Decimal(str(osobni_odbitak))

    # 4. Porezna osnovica
    porezna_osnovica = max(dohodak - osobni_odbitak, Decimal('0'))

    # 5. Porez na dohodak (2 razreda)
    if porezna_osnovica <= POREZ_PRAG_MJESECNI:
        porez = (porezna_osnovica * POREZ_STOPA_1).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        porez_nizzi = (POREZ_PRAG_MJESECNI * POREZ_STOPA_1).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        porez_vissi = ((porezna_osnovica - POREZ_PRAG_MJESECNI) * POREZ_STOPA_2).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        porez = porez_nizzi + porez_vissi

    # 6. Prirez
    prirez_rate = PRIREZ_RATES.get(prirez_grad, Decimal('0'))
    prirez = (porez * prirez_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # 7. Ukupno porez + prirez
    ukupno_porez = porez + prirez

    # 8. Neto
    neto = dohodak - ukupno_porez

    # 9. Doprinosi NA bruto (employer)
    zdravstvo = (bruto * DOPRINOS_ZDRAVSTVO).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # 10. Ukupni trosak poslodavca
    ukupni_trosak = bruto + zdravstvo

    return {
        'bruto': bruto,
        'mio_1_stup': mio_1,
        'mio_1_stopa': mio_1_rate,
        'mio_2_stup': mio_2,
        'mio_2_stopa': mio_2_rate,
        'ukupno_doprinosi_iz_bruto': ukupno_doprinosi_iz,
        'dohodak': dohodak,
        'osobni_odbitak': osobni_odbitak,
        'porezna_osnovica': porezna_osnovica,
        'porez': porez,
        'prirez_grad': prirez_grad,
        'prirez_stopa': prirez_rate,
        'prirez': prirez,
        'ukupno_porez_prirez': ukupno_porez,
        'neto': neto,
        'doprinos_zdravstvo': zdravstvo,
        'doprinos_zdravstvo_stopa': DOPRINOS_ZDRAVSTVO,
        'ukupni_trosak_poslodavca': ukupni_trosak,
    }


def izracunaj_neto_iz_bruto(bruto, **kwargs):
    """Shortcut: vrati samo neto iznos."""
    return izracunaj_placu(bruto, **kwargs)['neto']


def izracunaj_bruto_iz_neto(zeljeni_neto, **kwargs):
    """Reverse calc: koliki bruto za zeljeni neto (iterativno)."""
    zeljeni_neto = Decimal(str(zeljeni_neto))
    bruto_guess = zeljeni_neto * Decimal('1.5')

    for _ in range(50):
        result = izracunaj_placu(bruto_guess, **kwargs)
        diff = result['neto'] - zeljeni_neto
        if abs(diff) < Decimal('0.01'):
            return result
        bruto_guess = bruto_guess - diff

    return izracunaj_placu(bruto_guess, **kwargs)
