"""
BORG FENIX — FinaBonitetService
Procjena rizika dobavljača putem OIB provjere.

Redis Shield: cache.get(f"fina_risk_{oib}") — 24h TTL.
Koristi postojeći core.oib_validator za validaciju.
"""
import logging

from django.core.cache import cache
from django.db import DatabaseError, IntegrityError
from django.utils import timezone

logger = logging.getLogger('fiskalizacija.bonitet')

CACHE_TTL = 86400  # 24 sata

RISK_LEVELS = {
    'LOW': 'Nizak rizik',
    'MEDIUM': 'Srednji rizik',
    'HIGH': 'Visok rizik',
    'CRITICAL': 'Kritičan rizik',
    'UNKNOWN': 'Nepoznat',
}


def get_supplier_risk(oib, company_id=None):
    """
    Procijeni rizik dobavljača po OIB-u.

    1. Redis cache check (24h TTL)
    2. OIB validacija (ISO 7064)
    3. VIES lookup (EU VAT provjera)
    4. Izračun rizika
    5. Spremi u cache + bazu (ako rizik > LOW)

    Returns:
        dict: {oib, risk_level, risk_label, details, cached, checked_at}
    """
    # ── Redis Shield — provjeri cache ────────────────────────────────
    cache_key = f"fina_risk_{oib}"
    cached = cache.get(cache_key)
    if cached is not None:
        cached['cached'] = True
        return cached

    # ── OIB validacija ───────────────────────────────────────────────
    from core.oib_validator import validate_oib_hr

    details = {
        'oib_valid': False,
        'vies_valid': None,
        'vies_name': '',
        'vies_address': '',
        'company_active': None,
    }

    if not oib or len(oib) < 8:
        result = _build_result(oib, 'CRITICAL', details, 'OIB prekratak ili prazan')
        cache.set(cache_key, result, CACHE_TTL)
        return result

    # HR OIB check
    is_hr_oib = len(oib) == 11 and oib.isdigit()
    if is_hr_oib:
        details['oib_valid'] = validate_oib_hr(oib)
        if not details['oib_valid']:
            result = _build_result(oib, 'HIGH', details, 'OIB ne prolazi ISO 7064 kontrolu')
            cache.set(cache_key, result, CACHE_TTL)
            _save_alert(oib, company_id, result)
            return result

    # ── VIES Lookup (EU VAT) ─────────────────────────────────────────
    try:
        from partners.hr_registry import VIESLookup
        vies = VIESLookup()

        if is_hr_oib:
            vies_result = vies.lookup('HR', oib)
        elif oib.upper().startswith('DE'):
            vies_result = vies.lookup('DE', oib[2:])
        elif oib.upper().startswith('AT'):
            vies_result = vies.lookup('AT', oib[2:])
        else:
            vies_result = None

        if vies_result:
            details['vies_valid'] = vies_result.get('valid', False)
            details['vies_name'] = vies_result.get('name', '')
            details['vies_address'] = vies_result.get('address', '')
            details['company_active'] = vies_result.get('valid', None)
    except ImportError as e:
        logger.debug('VIES lookup failed for %s: %s', oib, e)
        details['vies_valid'] = None

    # ── Izračun rizika ───────────────────────────────────────────────
    risk_level = _calculate_risk(details)

    result = _build_result(oib, risk_level, details)
    cache.set(cache_key, result, CACHE_TTL)

    if risk_level not in ('LOW',):
        _save_alert(oib, company_id, result)

    logger.info('[BONITET] OIB=%s rizik=%s cached=24h', oib, risk_level)
    return result


def _calculate_risk(details):
    """Izračunaj razinu rizika na temelju svih provjera."""
    if not details.get('oib_valid') and details.get('oib_valid') is not None:
        return 'HIGH'

    if details.get('vies_valid') is False:
        return 'HIGH'

    if details.get('company_active') is False:
        return 'CRITICAL'

    if details.get('vies_valid') is True:
        return 'LOW'

    if details.get('oib_valid'):
        return 'LOW'

    return 'UNKNOWN'


def _build_result(oib, risk_level, details, note=''):
    """Gradi standardni response dict."""
    return {
        'oib': oib,
        'risk_level': risk_level,
        'risk_label': RISK_LEVELS.get(risk_level, 'Nepoznat'),
        'details': details,
        'note': note,
        'cached': False,
        'checked_at': timezone.now().isoformat(),
    }


def _save_alert(oib, company_id, result):
    """Spremi SupplierRiskAlert u bazu ako rizik > LOW."""
    try:
        from limit_connect_ai.models_knowledge_graph import SupplierRiskAlert

        if not company_id:
            logger.warning('[BONITET ALERT] OIB=%s rizik=%s — nema company_id, preskačem bazu', oib, result['risk_level'])
            return

        # Ne dupliciraj alerte za isti OIB u zadnjih 30 dana
        recent = SupplierRiskAlert.objects.filter(
            company_id=company_id,
            supplier_oib=oib,
            detected_at__gte=timezone.now() - timezone.timedelta(days=30),
        ).exists()
        if recent:
            logger.debug('[BONITET] Alert za OIB=%s već postoji (30d), preskačem', oib)
            return

        SupplierRiskAlert.objects.create(
            company_id=company_id,
            supplier_oib=oib,
            supplier_name=result.get('details', {}).get('vies_name', '') or f'OIB:{oib}',
            risk_level=result['risk_level'],
            risk_description=result.get('note', '') or f"Automatska provjera: {result.get('risk_label', '')}",
            source_data=result.get('details'),
        )
        logger.info('[BONITET ALERT] Kreiran SupplierRiskAlert: OIB=%s rizik=%s company=%s', oib, result['risk_level'], company_id)
    except (IntegrityError, DatabaseError):
        logger.warning('[BONITET ALERT] Greška pri spremanju alerta OIB=%s', oib, exc_info=True)


def invalidate_cache(oib):
    """Ručno poništi cache za OIB (npr. nakon ažuriranja podataka)."""
    cache.delete(f"fina_risk_{oib}")
