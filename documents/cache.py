"""Stub za documents cache — invalidacija arhiva cachea."""
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


def invalidate_arhiva_cache(company_id):
    """Invalidira cache za arhivu dokumenta po company_id."""
    if company_id:
        cache.delete(f'arhiva_docs_{company_id}')
        cache.delete(f'arhiva_stats_{company_id}')
