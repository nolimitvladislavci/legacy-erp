"""
Fiscal Health template tag — dohvaća status fiskalizacije za trenutnu firmu.
{% load fiscal_health_tags %}
{% fiscal_health_status as fh %}
{{ fh.healthy }} {{ fh.cert_subject }} {{ fh.cert_days }}
"""
from django import template
from django.core.cache import cache

register = template.Library()


@register.simple_tag(takes_context=True)
def fiscal_health_status(context):
    """Vraća dict s health statusom fiskalizacije za korisnikovu firmu."""
    request = context.get('request')
    if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
        return {'configured': False}

    # Cache po user-u (60s)
    cache_key = f'fiscal_health_{request.user.pk}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = {
        'configured': False,
        'healthy': False,
        'cert_valid': False,
        'cert_expired': False,
        'cert_subject': '',
        'cert_days': 0,
        'last_jir': '',
        'last_jir_date': '',
    }

    try:
        from core.company_utils import get_user_company
        # Simuliraj request ako nema session
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

        # Certifikat check
        import os
        cert_path = config.cert_path if hasattr(config, 'cert_path') else ''
        if cert_path and os.path.exists(cert_path):
            try:
                from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
                password = config.get_password().encode() if isinstance(config.get_password(), str) else config.get_password()
                with open(cert_path, 'rb') as f:
                    p12_data = f.read()
                key, cert, chain = load_key_and_certificates(p12_data, password)
                
                import datetime
                now = datetime.datetime.now(datetime.timezone.utc)
                days_left = (cert.not_valid_after_utc - now).days
                
                result['cert_valid'] = days_left > 0
                result['cert_expired'] = days_left <= 0
                result['cert_subject'] = cert.subject.rfc4514_string()[:60]
                result['cert_days'] = days_left
            except Exception:
                result['cert_valid'] = False

        # Zadnji JIR
        try:
            from invoicing.models import Invoice
            last_fiscal = Invoice.objects.filter(
                company=company, is_fiscalized=True
            ).exclude(jir__isnull=True).exclude(jir='').order_by('-fiscal_datetime').first()
            if last_fiscal:
                result['last_jir'] = last_fiscal.jir[:12]
                result['last_jir_date'] = last_fiscal.fiscal_datetime.strftime('%d.%m. %H:%M') if last_fiscal.fiscal_datetime else ''
        except Exception:
            pass

        # POS receipts s JIR
        try:
            from pos.models import POSReceipt
            last_pos = POSReceipt.objects.exclude(jir__isnull=True).exclude(jir='').order_by('-fiscal_datetime').first()
            if last_pos and not result['last_jir']:
                result['last_jir'] = last_pos.jir[:12]
                result['last_jir_date'] = last_pos.fiscal_datetime.strftime('%d.%m. %H:%M') if last_pos.fiscal_datetime else ''
        except Exception:
            pass

        # Healthy = cert valid + (has JIR or config active)
        result['healthy'] = result['cert_valid'] and (bool(result['last_jir']) or config.is_active)

    except Exception:
        pass

    cache.set(cache_key, result, 60)
    return result
