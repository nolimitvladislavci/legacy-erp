"""
Fiscal Health template tag v2 — 3 drona neutralizirana:
1. "Certifikat aktivan" ne "Fiskalizacija RADI" (ne garantiramo FINA CIS)
2. Narančasti alarm za neposlane račune (ZKI bez JIR, >24h)
3. Čita cert_expires_at iz baze, NE s diska
"""
from django import template
from django.core.cache import cache
from django.db import DatabaseError
from django.utils import timezone

register = template.Library()


@register.simple_tag(takes_context=True)
def fiscal_health_status(context):
    request = context.get('request')
    if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
        return {'configured': False}

    cache_key = f'fiscal_health_v2_{request.user.pk}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = {
        'configured': False,
        'status': 'none',       # none, green, orange, red
        'headline': '',
        'detail': '',
        'cert_valid': False,
        'cert_subject': '',
        'cert_days': 0,
        'pending_count': 0,     # ZKI bez JIR
        'pending_hours': 0,     # najstariji neposlani
        'last_jir': '',
        'last_jir_date': '',
    }

    try:
        from core.company_utils import get_user_company
        company = get_user_company(request)
        if not company:
            cache.set(cache_key, result, 60)
            return result

        from fiskalizacija.models import FiscalConfig
        config = FiscalConfig.objects.filter(company=company, is_active=True).first()
        if not config:
            cache.set(cache_key, result, 60)
            return result

        result['configured'] = True
        now = timezone.now()

        # ── DRON #3: Čitaj iz baze, ne s diska ──
        if config.cert_expires_at:
            days_left = (config.cert_expires_at - now).days
            result['cert_valid'] = days_left > 0
            result['cert_days'] = days_left
            result['cert_subject'] = config.cert_subject or ''
        else:
            # Fallback: prvi put, izvuci iz P12 i spremi u bazu
            config.extract_cert_metadata()
            if config.cert_expires_at:
                days_left = (config.cert_expires_at - now).days
                result['cert_valid'] = days_left > 0
                result['cert_days'] = days_left
                result['cert_subject'] = config.cert_subject or ''

        # ── DRON #2: Neposlani računi (ZKI bez JIR) ──
        try:
            from pos.models import POSReceipt
            pending_pos = POSReceipt.objects.filter(
                zki__isnull=False,
            ).exclude(zki='').filter(
                jir__isnull=True,
            ) | POSReceipt.objects.filter(
                zki__isnull=False,
            ).exclude(zki='').filter(jir='')

            pending_count = pending_pos.count()

            # Najstariji neposlani
            oldest = pending_pos.order_by('fiscal_datetime').first()
            if oldest and oldest.fiscal_datetime:
                hours_old = (now - oldest.fiscal_datetime).total_seconds() / 3600
            else:
                hours_old = 0
        except DatabaseError:
            pending_count = 0
            hours_old = 0

        # Invoice pending
        try:
            from invoicing.models import Invoice
            pending_inv = Invoice.objects.filter(
                company=company, zki__isnull=False,
            ).exclude(zki='').filter(jir__isnull=True).count()
            pending_inv += Invoice.objects.filter(
                company=company, zki__isnull=False,
            ).exclude(zki='').filter(jir='').count()
            pending_count += pending_inv
        except DatabaseError:
            pass

        result['pending_count'] = pending_count
        result['pending_hours'] = int(hours_old)

        # Zadnji JIR
        try:
            from invoicing.models import Invoice
            last = Invoice.objects.filter(
                company=company, is_fiscalized=True
            ).exclude(jir__isnull=True).exclude(jir='').order_by('-fiscal_datetime').first()
            if last:
                result['last_jir'] = last.jir[:12]
                result['last_jir_date'] = last.fiscal_datetime.strftime('%d.%m. %H:%M') if last.fiscal_datetime else ''
        except DatabaseError:
            pass

        # ── DRON #1: Status logika (ne garantiramo FINA CIS!) ──
        if not result['cert_valid']:
            result['status'] = 'red'
            result['headline'] = 'Certifikat istekao'
            result['detail'] = 'Fiskalizacija nije moguća dok se certifikat ne obnovi.'
        elif pending_count > 0 and hours_old > 24:
            result['status'] = 'orange'
            result['headline'] = f'UPOZORENJE: {pending_count} neprijavljenih računa'
            result['detail'] = f'Najstariji čeka {int(hours_old)}h. Zakonski rok: 48h! Pokrenite naknadnu fiskalizaciju.'
        elif pending_count > 0:
            result['status'] = 'orange'
            result['headline'] = f'{pending_count} račun(a) čeka fiskalizaciju'
            result['detail'] = f'Čeka {int(hours_old)}h. Automatski retry u tijeku.'
        elif result['cert_days'] < 30:
            result['status'] = 'orange'
            result['headline'] = f'Certifikat istječe za {result["cert_days"]} dana'
            result['detail'] = 'Obnovite certifikat kod FINA-e prije isteka.'
        else:
            result['status'] = 'green'
            result['headline'] = 'Certifikat aktivan — spremno za fiskalizaciju'
            result['detail'] = f'{result["cert_subject"][:40]} ({result["cert_days"]} dana)'
            if result['last_jir']:
                result['detail'] += f' | Zadnji JIR: {result["last_jir_date"]}'

    except (ValueError, TypeError):
        pass

    cache.set(cache_key, result, 60)
    return result
