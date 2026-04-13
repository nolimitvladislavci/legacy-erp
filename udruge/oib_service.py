"""OIB validacija i lookup."""
import logging
from django.core.cache import cache

logger = logging.getLogger('udruge')


def validate_oib(oib):
    """ISO 7064 MOD 11,10 checksum provjera."""
    if not oib or len(oib) != 11 or not oib.isdigit():
        return False
    a = 10
    for digit in oib[:10]:
        a = (a + int(digit)) % 10
        if a == 0:
            a = 10
        a = (a * 2) % 11
    check = 11 - a
    if check == 10:
        check = 0
    return check == int(oib[10])


def lookup_oib(oib):
    """Lookup OIB — validacija + cache."""
    result = {'oib': oib, 'valid': validate_oib(oib)}

    if not result['valid']:
        result['error'] = 'Neispravan OIB (checksum)'
        return result

    cache_key = 'oib_lookup_%s' % oib
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Za sada samo validacija — Sudreg API zahtijeva registraciju
    result['note'] = 'OIB validan. Sudski registar lookup zahtijeva API pristup.'
    result['found'] = False

    cache.set(cache_key, result, 86400)
    return result
