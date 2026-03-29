"""
Globalni Fiskalizacija Health Check — widget na svakom dashboardu.
Svaka firma s certifikatom vidi: "Fiskalizacija RADI" ili "NE RADI".
Integrira se u BORG Hub + company dashboard + POS dashboard.
"""
import os
BASE = '/var/www/fina-connect'

# ══════════════════════════════════════════════════════════════════════
# 1. PARTIAL — _fiscal_health.html (include na bilo kojem dashboardu)
# ══════════════════════════════════════════════════════════════════════

widget = '''{% comment %}
Fiskalizacija Health Check Widget — globalni status.
Prikazuje se automatski za svaku firmu koja ima FiscalConfig.

Usage: {% include "components/_fiscal_health.html" %}
Koristi request.user za dohvat firme.
{% endcomment %}
{% load fiscal_health_tags %}
{% fiscal_health_status as fh %}
{% if fh.configured %}
<div style="background:var(--surface,var(--bg-card));border:1px solid {% if fh.healthy %}rgba(34,197,94,.3){% else %}rgba(239,68,68,.3){% endif %};border-radius:12px;padding:1rem 1.25rem;margin-bottom:1rem;display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
  <div style="width:44px;height:44px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0;{% if fh.healthy %}background:rgba(34,197,94,.15);color:#22c55e{% else %}background:rgba(239,68,68,.15);color:#ef4444{% endif %}">
    <i class="fas fa-{% if fh.healthy %}check-circle{% else %}exclamation-triangle{% endif %}"></i>
  </div>
  <div style="flex:1">
    <div style="font-weight:700;font-size:.9rem;color:{% if fh.healthy %}#22c55e{% else %}#ef4444{% endif %}">
      Fiskalizacija {% if fh.healthy %}RADI{% else %}NE RADI{% endif %}
    </div>
    <div style="font-size:.78rem;color:var(--text-dim,var(--text-muted))">
      {% if fh.cert_valid %}Certifikat: {{ fh.cert_subject }} ({{ fh.cert_days }} dana){% endif %}
      {% if fh.cert_expired %}<span style="color:#ef4444">CERTIFIKAT ISTEKAO!</span>{% endif %}
      {% if not fh.cert_valid and not fh.cert_expired %}Certifikat: nije konfiguriran{% endif %}
      {% if fh.last_jir %} | Zadnji JIR: {{ fh.last_jir_date }}{% endif %}
    </div>
  </div>
  {% if fh.healthy %}
  <span style="font-size:.7rem;padding:3px 10px;border-radius:20px;background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);color:#22c55e;font-weight:600">● LIVE</span>
  {% else %}
  <a href="{% url 'eracun:sukladnost_dashboard' %}" style="font-size:.75rem;padding:4px 12px;border-radius:8px;background:#ef444422;border:1px solid #ef444444;color:#ef4444;text-decoration:none;font-weight:600">Dijagnostika →</a>
  {% endif %}
</div>
{% endif %}
'''

os.makedirs(os.path.join(BASE, 'templates/components'), exist_ok=True)
with open(os.path.join(BASE, 'templates/components/_fiscal_health.html'), 'w') as f:
    f.write(widget)
print("[OK] templates/components/_fiscal_health.html")


# ══════════════════════════════════════════════════════════════════════
# 2. TEMPLATE TAG — fiscal_health_tags
# ══════════════════════════════════════════════════════════════════════

tag_dir = os.path.join(BASE, 'fiskalizacija/templatetags')
os.makedirs(tag_dir, exist_ok=True)
with open(os.path.join(tag_dir, '__init__.py'), 'w') as f:
    f.write('')

tag_code = '''"""
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
'''

with open(os.path.join(tag_dir, 'fiscal_health_tags.py'), 'w') as f:
    f.write(tag_code)
print("[OK] fiskalizacija/templatetags/fiscal_health_tags.py")


# ══════════════════════════════════════════════════════════════════════
# 3. INJECT u BORG Hub, company dashboard, POS dashboard
# ══════════════════════════════════════════════════════════════════════

# BORG Hub — dodaj na vrh content-a
borg_tpl = os.path.join(BASE, 'borg_ops/templates/borg_ops/operations_dashboard.html')
with open(borg_tpl) as f:
    bc = f.read()

if '_fiscal_health' not in bc:
    # Inject nakon stats-row
    old_stats_end = '<!-- SLA Alerts -->'
    new_stats_end = '{% include "components/_fiscal_health.html" %}\n\n<!-- SLA Alerts -->'
    bc = bc.replace(old_stats_end, new_stats_end, 1)
    # Dodaj load tag
    if '{% load fiscal_health_tags %}' not in bc:
        bc = bc.replace('{% load i18n %}', '{% load i18n %}\n{% load fiscal_health_tags %}')
    with open(borg_tpl, 'w') as f:
        f.write(bc)
    print("[OK] BORG Hub — fiscal health widget injected")

# Company dashboard — dodaj na vrh
dash_tpl = os.path.join(BASE, 'templates/dashboard.html')
with open(dash_tpl) as f:
    dc = f.read()

if '_fiscal_health' not in dc:
    if '{% block content %}' in dc:
        dc = dc.replace('{% block content %}', '{% load fiscal_health_tags %}\n{% block content %}\n{% include "components/_fiscal_health.html" %}')
        with open(dash_tpl, 'w') as f:
            f.write(dc)
        print("[OK] dashboard.html — fiscal health widget injected")

# POS dashboard
pos_tpl = os.path.join(BASE, 'templates/pos/dashboard.html')
with open(pos_tpl) as f:
    pc = f.read()

if '_fiscal_health' not in pc:
    if '{% block content %}' in pc:
        pc = pc.replace('{% block content %}', '{% load fiscal_health_tags %}\n{% block content %}\n{% include "components/_fiscal_health.html" %}')
        with open(pos_tpl, 'w') as f:
            f.write(pc)
        print("[OK] pos/dashboard.html — fiscal health widget injected")


print("\\n═══════════════════════════════════════════")
print("GLOBALNI FISCAL HEALTH CHECK")
print("  Widget: components/_fiscal_health.html")
print("  Tag: fiscal_health_tags.fiscal_health_status")
print("  Injectiran u: BORG Hub, Dashboard, POS")
print("  Cache: 60s per user (Redis)")
print("═══════════════════════════════════════════")
