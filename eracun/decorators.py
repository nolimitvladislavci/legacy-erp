"""
eRačun decorators — zaštita institucijske komunikacije.

GDPR osnova: čl. 6(b) — ugovorni odnos kao pravna osnova.
Bez potpisanih T&C sustav tehnički ne može komunicirati s
FINA-om, Poreznom upravom ili bilo kojim državnim API-jem.

Ova zaštita nije opcijska — ona je arhitektonski zahtjev (Gemini, 2026-03-24).
"""
import logging
from functools import wraps

from django.core.exceptions import PermissionDenied

logger = logging.getLogger('eracun.security')


def requires_tc_consent(func):
    """
    Dekorator koji blokira svaku institucijsku komunikaciju
    za firme koje nisu potpisale T&C.

    Primjenjuje se na:
    - Sve Celery taskove koji komuniciraju s FINA / Poreznom upravom
    - Sve servise koji dohvaćaju ili šalju podatke u ime klijenta
    - Knowledge Graph enrichment koji koristi vanjske izvore

    Korištenje:
        @requires_tc_consent
        def submit_eizvjestavanje(company, period_month, period_year):
            ...

        @shared_task
        def celery_task(company_id):
            company = Company.objects.get(id=company_id)
            return submit_eizvjestavanje(company, ...)

    NAPOMENA: Dekorator prima `company` kao PRVI pozicijski argument.
    Za Celery taskove koji primaju company_id, dohvati company objekt
    PRIJE poziva dekoriranog servisa.
    """
    @wraps(func)
    def wrapper(company, *args, **kwargs):
        if not getattr(company, 'has_signed_tc_consent', False):
            msg = (
                f'GDPR BLOKADA: Firma "{company.name}" (OIB: {company.oib}) '
                f'nema potpisane T&C (has_signed_tc_consent=False). '
                f'Institucijska komunikacija je tehnički onemogućena. '
                f'Admin akcija: nakon potpisivanja T&C, postaviti '
                f'Company.has_signed_tc_consent=True i '
                f'Company.tc_consent_signed_at=timezone.now().'
            )
            logger.warning(msg)
            raise PermissionDenied(msg)
        return func(company, *args, **kwargs)
    return wrapper


def requires_tc_consent_celery(func):
    """
    Varijanta za Celery taskove koji primaju company_id umjesto company objekta.

    Korištenje:
        @shared_task
        @requires_tc_consent_celery
        def submit_eizvjestavanje(company_id, period_month, period_year):
            ...
    """
    @wraps(func)
    def wrapper(company_id, *args, **kwargs):
        from companies.models import Company
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            logger.error('requires_tc_consent_celery: Company %s ne postoji', company_id)
            return {'ok': False, 'error': 'company_not_found'}

        if not getattr(company, 'has_signed_tc_consent', False):
            logger.warning(
                'GDPR BLOKADA: %s (OIB: %s) — has_signed_tc_consent=False',
                company.name, company.oib,
            )
            return {'ok': False, 'error': 'no_tc_consent', 'company': company.name}

        return func(company_id, *args, **kwargs)
    return wrapper
