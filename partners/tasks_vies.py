"""
VIES Batch Lookup — async provjera PDV statusa za B2B/udruga partnere.

Strategija:
  1. Dohvati sve JEDINSTVENE OIB-ove koji su b2b_novat ili udruga_novat
  2. Za svaki OIB pozovi VIES jednom (ne za svaku firmu!)
  3. Ako je valid=True → ažuriraj SVE partnere s tim OIB-om:
     - b2b_novat → b2b_vat + is_vat_registered=True + vat_id=HR{oib}
     - udruga_novat → udruga_vat + is_vat_registered=True
  4. Rate limit: 1 req / 1.5 sec (VIES preporuka)
  5. Retry na timeout/error

Pokretanje:
  from partners.tasks_vies import vies_batch_lookup
  vies_batch_lookup.delay()                    # svi (async)
  vies_batch_lookup.delay(limit=100)           # prvih 100 (test)
  vies_batch_lookup.apply(kwargs={'dry_run': True})  # sync dry-run
"""

import logging
import time

from celery import shared_task
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger('partners.vies')


@shared_task(bind=True, max_retries=0, time_limit=7200, soft_time_limit=7000)
def vies_batch_lookup(self, limit=0, dry_run=False):
    """
    Batch VIES provjera za sve b2b_novat i udruga_novat partnere.
    """
    from partners.models import Partner
    from partners.hr_registry import VIESLookup

    vies = VIESLookup(timeout=15)
    now = timezone.now()

    # Jedinstveni OIB-ovi za provjeru, najčešći prvi
    oibs_qs = (
        Partner.objects
        .filter(buyer_type__in=['b2b_novat', 'udruga_novat'])
        .filter(oib__regex=r'^\d{11}$')
        .values('oib')
        .annotate(partner_count=Count('id'))
        .order_by('-partner_count')
    )

    if limit:
        oibs_qs = oibs_qs[:limit]

    oib_list = list(oibs_qs)
    total = len(oib_list)

    logger.info('[VIES-BATCH] Start: %d unique OIBs (dry_run=%s)', total, dry_run)

    stats = {
        'total': total,
        'vat_valid': 0,
        'vat_invalid': 0,
        'errors': 0,
        'partners_upgraded': 0,
        'skipped': 0,
    }

    for i, row in enumerate(oib_list, 1):
        oib = row['oib']
        partner_count = row['partner_count']

        # Skip ako već provjereno u prethodnom runu
        if Partner.objects.filter(oib=oib, notes__contains='[VIES-CHECK').exists():
            stats['skipped'] += 1
            continue

        # VIES poziv
        try:
            result = vies.check_vat('HR', oib)
        except Exception as exc:
            logger.warning('[VIES-BATCH] %d/%d OIB %s — error: %s', i, total, oib, exc)
            stats['errors'] += 1
            time.sleep(2)
            continue

        # Retry na timeout
        if result.get('error') and ('timeout' in str(result['error']).lower() or 'veze' in str(result['error']).lower()):
            time.sleep(5)
            try:
                result = vies.check_vat('HR', oib)
            except Exception:
                stats['errors'] += 1
                continue

        if result.get('error'):
            stats['errors'] += 1
            time.sleep(1.5)
            continue

        is_vat = result.get('valid', False)
        vies_name = result.get('name', '')

        if is_vat:
            stats['vat_valid'] += 1
            vies_address = result.get('address', '')
            vies_city = result.get('city', '')

            if not dry_run:
                with transaction.atomic():
                    for p in Partner.objects.filter(oib=oib, buyer_type__in=['b2b_novat', 'udruga_novat']):
                        old_type = p.buyer_type
                        p.buyer_type = 'b2b_vat' if old_type == 'b2b_novat' else 'udruga_vat'
                        p.is_vat_registered = True
                        p.vat_id = f'HR{oib}'

                        if not p.address and vies_address:
                            p.address = vies_address
                        if not p.city and vies_city:
                            p.city = vies_city

                        p.notes = (p.notes or '') + f'\n[VIES-CHECK {now:%Y-%m-%d}] valid=True | {old_type} -> {p.buyer_type} | "{vies_name}"'
                        p.save(update_fields=[
                            'buyer_type', 'is_vat_registered', 'vat_id',
                            'address', 'city', 'notes', 'updated_at',
                        ])
                        stats['partners_upgraded'] += 1

            logger.info('[VIES-BATCH] %d/%d OIB %s — VAT VALID (%d partners) — %s', i, total, oib, partner_count, vies_name)
        else:
            stats['vat_invalid'] += 1

            if not dry_run:
                for p in Partner.objects.filter(oib=oib, buyer_type__in=['b2b_novat', 'udruga_novat']):
                    if '[VIES-CHECK' not in (p.notes or ''):
                        p.notes = (p.notes or '') + f'\n[VIES-CHECK {now:%Y-%m-%d}] valid=False | ostaje {p.buyer_type}'
                        p.save(update_fields=['notes', 'updated_at'])

        time.sleep(1.5)

        if i % 100 == 0:
            logger.info(
                '[VIES-BATCH] Progress: %d/%d | valid=%d invalid=%d errors=%d upgraded=%d',
                i, total, stats['vat_valid'], stats['vat_invalid'],
                stats['errors'], stats['partners_upgraded'],
            )

    logger.info('[VIES-BATCH] DONE: %s', stats)
    return stats
