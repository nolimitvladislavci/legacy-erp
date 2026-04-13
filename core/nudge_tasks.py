"""
Global AI Nudge — ključne poruke korisnicima koji su zapeli.
Pokreće se svakih 4h. Samo bitne poruke, nikad spam.

Pravila:
1. Max 1 nudge po korisniku po danu
2. Samo WhatsApp (ne email — WhatsApp ima 95% open rate)
3. Samo ključni momenti (ne "hey how are you")
4. Svaki nudge nosi "Powered by LIMIT Connect" branding
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

logger = logging.getLogger('nudge')

# Ključni nudge scenariji
NUDGE_SCENARIOS = [
    'onboarding_stuck',       # Registriran 24h, 0 artikala
    'pos_inactive',           # POS aktivan, 0 bonova 3 dana
    'fiscal_warning',         # Račun nije fiskaliziran 24h+
    'first_sale_congrats',    # Prva prodaja ikad — čestitka
    'weekly_summary',         # Nedjeljna metrika (ako ima promet)
]


@shared_task(bind=True, max_retries=1, soft_time_limit=300)
def user_nudge_patrol(self):
    """Globalni nudge patrol — svakih 4h."""
    from django.core.cache import cache

    from companies.models import Company

    results = {'checked': 0, 'nudged': 0, 'skipped': 0}
    now = timezone.now()

    companies = Company.objects.filter(is_active=True)

    for company in companies:
        results['checked'] += 1

        # Nađi vlasnika/admina s brojem telefona
        owner = _get_owner_phone(company)
        if not owner:
            continue

        phone, name = owner

        # Max 1 nudge dnevno po firmi
        cache_key = f'nudge:{company.pk}:{now.date()}'
        if cache.get(cache_key):
            results['skipped'] += 1
            continue

        nudge = _evaluate_nudges(company, now)
        if nudge:
            _send_nudge(phone, name, company, nudge)
            cache.set(cache_key, True, 86400)  # 24h
            results['nudged'] += 1
            logger.info(f"Nudge sent: {company.name} → {nudge['type']}")

    logger.info(f"Nudge patrol: {results}")
    return results


def _get_owner_phone(company):
    """Nađi telefon vlasnika firme."""
    from accounts.models import CompanyMembership

    memberships = CompanyMembership.objects.filter(
        company=company, role__in=['owner', 'company_admin'], is_active=True
    ).select_related('user')

    for m in memberships:
        phone = getattr(m.user, 'phone', '') or ''
        if not phone:
            try:
                phone = m.user.profile.phone or ''
            except AttributeError:
                logger.exception("Profile access failed")
        if phone and len(phone) >= 8:
            return (phone, m.user.get_full_name() or m.user.username)

    # Fallback: company phone
    phone = company.phone or getattr(company, 'mobile', '') or ''
    if phone and len(phone) >= 8:
        return (phone, company.name)

    return None


def _evaluate_nudges(company, now):
    """Evaluiraj koji nudge (ako ikoji) treba poslati."""

    # 1. ONBOARDING STUCK — registriran 24h+, 0 artikala
    if company.created_at and (now - company.created_at) > timedelta(hours=24):
        from inventory.models import InventoryItem
        items = InventoryItem.objects.filter(company=company, sku__startswith='DEMO').count()
        real_items = InventoryItem.objects.filter(company=company).exclude(sku__startswith='DEMO').count()
        if real_items == 0 and (now - company.created_at) < timedelta(days=3):
            return {
                'type': 'onboarding_stuck',
                'message': (
                    'Pozdrav! Primijetili smo da još nemate artikala u sustavu.\n\n'
                    'Najbrži start:\n'
                    '1. Otvorite POS → kliknite + za novi artikl\n'
                    '2. Upišite ime i cijenu — AI popuni ostalo\n'
                    '3. Spremni ste za prodaju!\n\n'
                    'Trebate pomoć? Javite se ovdje.\n\n'
                    'LIMIT Connect · limit-connect.com'
                )
            }

    # 2. FISCAL WARNING — plaćen račun bez JIR 24h+
    from pos.models import POSReceipt
    unfiscalized = POSReceipt.objects.filter(
        session__terminal__company=company,
        status='paid',
        jir__isnull=True,
        created_at__lt=now - timedelta(hours=24),
        created_at__gt=now - timedelta(hours=48),
    ).count()
    if unfiscalized > 0:
        return {
            'type': 'fiscal_warning',
            'message': (
                f'Upozorenje: {unfiscalized} račun(a) nije fiskalizirano više od 24h.\n\n'
                'Zakonski rok je 48h. Sustav automatski pokušava, '
                'ali provjerite internet vezu i certifikat.\n\n'
                'LIMIT Connect · limit-connect.com'
            )
        }

    # 3. FIRST SALE CONGRATS — prva prodaja ikad (unutar zadnja 4h)
    first_receipt = POSReceipt.objects.filter(
        session__terminal__company=company,
        status='paid',
    ).order_by('created_at').first()

    if first_receipt and (now - first_receipt.created_at) < timedelta(hours=4):
        total_receipts = POSReceipt.objects.filter(
            session__terminal__company=company, status='paid'
        ).count()
        if total_receipts <= 3:
            return {
                'type': 'first_sale_congrats',
                'message': (
                    f'Prva prodaja! Račun #{first_receipt.receipt_number} — '
                    f'€{first_receipt.total:.2f}\n\n'
                    'Sustav radi. Fiskalizacija, arhiva, sve automatski.\n\n'
                    'Savjet: Kliknite "Podijeli" za slanje računa kupcu '
                    'putem WhatsApp-a ili QR koda.\n\n'
                    'LIMIT Connect · limit-connect.com'
                )
            }

    # 4. POS INACTIVE — ima terminale ali 0 prodaja 3 dana
    from pos.models import POSTerminal
    terminals = POSTerminal.objects.filter(company=company, is_active=True).count()
    if terminals > 0:
        recent = POSReceipt.objects.filter(
            session__terminal__company=company,
            status='paid',
            created_at__gt=now - timedelta(days=3),
        ).count()
        if recent == 0:
            # Ali da nije nova firma koja nikad nije prodala
            total_ever = POSReceipt.objects.filter(
                session__terminal__company=company, status='paid'
            ).count()
            if total_ever > 0:
                return {
                    'type': 'pos_inactive',
                    'message': (
                        'Nema prodaje zadnja 3 dana.\n\n'
                        'Ako imate problema s POS-om, javite se — '
                        'pomoći ćemo.\n\n'
                        'LIMIT Connect · limit-connect.com'
                    )
                }

    return None


def _send_nudge(phone, name, company, nudge):
    """Pošalji nudge poruku putem WhatsApp-a."""
    from core.whatsapp import normalize_phone, send_text

    intl = normalize_phone(phone)
    if not intl:
        logger.warning(f"Nudge skip — invalid phone for {company.name}: {phone}")
        return

    greeting = f'Pozdrav{", " + name.split()[0] if name else ""}!'
    msg = f'{greeting}\n\n{nudge["message"]}'

    result = send_text(intl, msg)
    if result.get('success'):
        logger.info(f"Nudge delivered: {company.name} ({nudge['type']})")
    else:
        logger.warning(f"Nudge failed: {company.name} — {result.get('error')}")
