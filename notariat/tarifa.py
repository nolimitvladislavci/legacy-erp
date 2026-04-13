"""
notariat/tarifa.py
Kalkulator biljeznicki pristojbi i dimnjacarski tarifa.
Zakon o javnobiljeznicki pristojbama (NN 115/12)
"""
from decimal import Decimal

TARIFE = {
    'punomoc': {
        'osnova': Decimal('10.00'),
        'pdv': True,
    },
    'osnivanje_jdoo': {
        'osnova': Decimal('50.00'),
        'pdv': True,
    },
    'osnivanje_doo': {
        'osnova': Decimal('100.00'),
        'pdv': True,
    },
    'kupoprodaja_nekretnine': {
        'razredi': [
            (Decimal('10000'),  Decimal('16.84')),
            (Decimal('50000'),  Decimal('33.63')),
            (Decimal('100000'), Decimal('67.26')),
            (Decimal('500000'), Decimal('134.52')),
            (None,              Decimal('201.78')),
        ],
        'pdv': True,
    },
    'zaduznica': {
        'postotak': Decimal('0.001'),
        'minimum':  Decimal('10.00'),
        'maximum':  Decimal('200.00'),
        'pdv': True,
    },
    'bjanko_zaduznica': {
        'postotak': Decimal('0.001'),
        'minimum':  Decimal('10.00'),
        'maximum':  Decimal('200.00'),
        'pdv': True,
    },
    'darovanje': {
        'osnova': Decimal('33.63'),
        'pdv': True,
    },
    'pregled_dimnjaka': {
        'osnova': Decimal('15.00'),
        'pdv': True,
    },
    'potvrda_dimnjaka': {
        'osnova': Decimal('5.00'),
        'pdv': True,
    },
}

PDV_STOPA = Decimal('0.25')


def izracunaj_tarifu(vrsta: str, vrijednost_eur: float = 0) -> dict:
    """
    Izracunaj tarifu za danu vrstu dokumenta.

    Returns:
        dict s kljucevima: nagrada, pristojba, pdv_iznos, ukupno (sve Decimal)
    """
    tarifa = TARIFE.get(vrsta)
    if not tarifa:
        return {
            'nagrada': Decimal('0'),
            'pristojba': Decimal('0'),
            'pdv_iznos': Decimal('0'),
            'ukupno': Decimal('0'),
            'greska': f'Nepoznata vrsta: {vrsta}',
        }

    vrijednost = Decimal(str(vrijednost_eur))

    # Izracun nagrade
    if 'osnova' in tarifa:
        nagrada = tarifa['osnova']

    elif 'razredi' in tarifa:
        nagrada = Decimal('0')
        for limit, iznos in tarifa['razredi']:
            if limit is None or vrijednost <= limit:
                nagrada = iznos
                break

    elif 'postotak' in tarifa:
        nagrada = vrijednost * tarifa['postotak']
        nagrada = max(nagrada, tarifa['minimum'])
        nagrada = min(nagrada, tarifa['maximum'])

    else:
        nagrada = Decimal('0')

    # Sudska pristojba (pausal — 50% nagrade, max 66.36 EUR)
    pristojba = min(nagrada * Decimal('0.5'), Decimal('66.36'))

    # PDV
    pdv_iznos = (nagrada + pristojba) * PDV_STOPA if tarifa.get('pdv') else Decimal('0')

    ukupno = nagrada + pristojba + pdv_iznos

    return {
        'nagrada':   nagrada.quantize(Decimal('0.01')),
        'pristojba': pristojba.quantize(Decimal('0.01')),
        'pdv_iznos': pdv_iznos.quantize(Decimal('0.01')),
        'ukupno':    ukupno.quantize(Decimal('0.01')),
    }
