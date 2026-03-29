"""
3 Drona na Fiscal Health Widget:
1. "Certifikat aktivan" umjesto "Fiskalizacija RADI" 
2. Narančasti upozorenje za neposlane račune (48h zakon)
3. cert_expires_at u bazu (ne čitaj P12 s diska svaku minutu)
"""
import os
BASE = '/var/www/fina-connect'

# ══════════════════════════════════════════════════════════════════════
# DRON #3: cert_expires_at u FiscalConfig model
# ══════════════════════════════════════════════════════════════════════

path = os.path.join(BASE, 'fiskalizacija/models.py')
with open(path) as f:
    c = f.read()

if 'cert_expires_at' not in c:
    old = '    is_active = models.BooleanField'
    new = """    cert_expires_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Certifikat istječe',
        help_text='Automatski izvučeno iz P12 pri uploadu — widget čita ovo, ne disk',
    )
    cert_subject = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Certifikat Subject',
        help_text='CN iz P12 certifikata — cached u bazi',
    )
    is_active = models.BooleanField"""
    c = c.replace(old, new)
    with open(path, 'w') as f:
        f.write(c)
    print("[OK] fiskalizacija/models.py — cert_expires_at + cert_subject polja")


# ══════════════════════════════════════════════════════════════════════
# DRON #3b: Extract cert info pri uploadu (signal/save override)
# ══════════════════════════════════════════════════════════════════════

if 'def extract_cert_metadata' not in c:
    with open(path) as f:
        c = f.read()
    
    # Dodaj metodu na FiscalConfig
    old_meta = '    class Meta:'
    new_meta = """    def extract_cert_metadata(self):
        \"\"\"Izvuci expiry date i subject iz P12 — pozovi jednom pri uploadu.\"\"\"
        import os
        cert_path = self.cert_path if hasattr(self, 'cert_path') else ''
        if not cert_path or not os.path.exists(cert_path):
            return
        try:
            from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
            password = self.get_password()
            if isinstance(password, str):
                password = password.encode()
            with open(cert_path, 'rb') as f:
                p12_data = f.read()
            key, cert, chain = load_key_and_certificates(p12_data, password)
            from django.utils import timezone
            self.cert_expires_at = cert.not_valid_after_utc
            self.cert_subject = cert.subject.rfc4514_string()[:200]
            self.save(update_fields=['cert_expires_at', 'cert_subject'])
        except Exception:
            pass

    class Meta:"""
    c = c.replace(old_meta, new_meta, 1)
    with open(path, 'w') as f:
        f.write(c)
    print("[OK] fiskalizacija/models.py — extract_cert_metadata() metoda")


# ══════════════════════════════════════════════════════════════════════
# SVA 3 DRONA: Template tag — kompletni rewrite
# ══════════════════════════════════════════════════════════════════════

tag_code = '''"""
Fiscal Health template tag v2 — 3 drona neutralizirana:
1. "Certifikat aktivan" ne "Fiskalizacija RADI" (ne garantiramo FINA CIS)
2. Narančasti alarm za neposlane račune (ZKI bez JIR, >24h)
3. Čita cert_expires_at iz baze, NE s diska
"""
from django import template
from django.core.cache import cache
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
        from datetime import timedelta
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
        except Exception:
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
        except Exception:
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
        except Exception:
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

    except Exception:
        pass

    cache.set(cache_key, result, 60)
    return result
'''

tag_path = os.path.join(BASE, 'fiskalizacija/templatetags/fiscal_health_tags.py')
with open(tag_path, 'w') as f:
    f.write(tag_code)
print("[OK] fiscal_health_tags.py — v2 (sva 3 drona)")


# ══════════════════════════════════════════════════════════════════════
# WIDGET TEMPLATE — v2 s 3 statusa (green/orange/red)
# ══════════════════════════════════════════════════════════════════════

widget_v2 = '''{% comment %}
Fiscal Health Widget v2 — 3 statusa:
  green:  "Certifikat aktivan — spremno za fiskalizaciju" 
  orange: "X neprijavljenih računa!" ili "Cert istječe za N dana"
  red:    "Certifikat istekao"
{% endcomment %}
{% load fiscal_health_tags %}
{% fiscal_health_status as fh %}
{% if fh.configured %}
<div style="background:var(--surface,var(--bg-card));border:1px solid {% if fh.status == 'green' %}rgba(34,197,94,.3){% elif fh.status == 'orange' %}rgba(245,158,11,.3){% else %}rgba(239,68,68,.3){% endif %};border-radius:12px;padding:1rem 1.25rem;margin-bottom:1rem;display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
  <div style="width:44px;height:44px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0;{% if fh.status == 'green' %}background:rgba(34,197,94,.15);color:#22c55e{% elif fh.status == 'orange' %}background:rgba(245,158,11,.15);color:#f59e0b{% else %}background:rgba(239,68,68,.15);color:#ef4444{% endif %}">
    <i class="fas fa-{% if fh.status == 'green' %}check-circle{% elif fh.status == 'orange' %}exclamation-triangle{% else %}times-circle{% endif %}"></i>
  </div>
  <div style="flex:1">
    <div style="font-weight:700;font-size:.9rem;color:{% if fh.status == 'green' %}#22c55e{% elif fh.status == 'orange' %}#f59e0b{% else %}#ef4444{% endif %}">
      {{ fh.headline }}
    </div>
    <div style="font-size:.78rem;color:var(--text-dim,var(--text-muted))">{{ fh.detail }}</div>
  </div>
  {% if fh.status == 'green' %}
  <span style="font-size:.7rem;padding:3px 10px;border-radius:20px;background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);color:#22c55e;font-weight:600">● SPREMNO</span>
  {% elif fh.status == 'orange' %}
  <a href="{% url 'eracun:sukladnost_dashboard' %}" style="font-size:.75rem;padding:4px 12px;border-radius:8px;background:#f59e0b22;border:1px solid #f59e0b44;color:#f59e0b;text-decoration:none;font-weight:600">Provjeri →</a>
  {% else %}
  <a href="{% url 'eracun:sukladnost_dashboard' %}" style="font-size:.75rem;padding:4px 12px;border-radius:8px;background:#ef444422;border:1px solid #ef444444;color:#ef4444;text-decoration:none;font-weight:600">Dijagnostika →</a>
  {% endif %}
</div>
{% endif %}
'''

with open(os.path.join(BASE, 'templates/components/_fiscal_health.html'), 'w') as f:
    f.write(widget_v2)
print("[OK] _fiscal_health.html — v2 (green/orange/red)")


# ══════════════════════════════════════════════════════════════════════
# SEED cert_expires_at za postojeće configs
# ══════════════════════════════════════════════════════════════════════

seed_code = '''
# One-time: extract cert metadata za sve postojeće FiscalConfig-e
from fiskalizacija.models import FiscalConfig
for fc in FiscalConfig.objects.filter(cert_expires_at__isnull=True):
    fc.extract_cert_metadata()
    if fc.cert_expires_at:
        print(f'  Extracted: {fc.company.name} → expires {fc.cert_expires_at}, subject={fc.cert_subject[:40]}')
    else:
        print(f'  Skip: {fc.company.name} — no cert or error')
'''

with open(os.path.join(BASE, 'tmp/seed_cert_metadata.py'), 'w') as f:
    f.write(seed_code)
print("[OK] tmp/seed_cert_metadata.py — one-time seed script")


print("\\n═══════════════════════════════════════════")
print("3 FISCAL DRONA NEUTRALIZIRANA")
print("  Dron #1: 'Certifikat aktivan' ne 'Fiskalizacija RADI'")
print("  Dron #2: Narančasti alarm za neposlane račune")  
print("  Dron #3: cert_expires_at u bazi, ne disk I/O")
print("═══════════════════════════════════════════")
