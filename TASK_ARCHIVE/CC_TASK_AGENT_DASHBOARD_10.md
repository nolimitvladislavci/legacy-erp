# CC_TASK: AGENT DASHBOARD 10/10 — /moji-klijenti/
# Datum: 04.04.2026. | Rok: 05.04.2026. | Prioritet: P0
# Korisnici: Marija Brtan, Kruljac Ivica
# BLOKIRA: Mariju da vodi 71 klijenta

PRAVILO: READ models.py PRIJE svakog WRITE.
PRAVILO: base.html, .env NE DIRAS.
PRAVILO: python manage.py check 2>&1 | tail -3 nakon svake izmjene.

---

## CILJ

Marija otvori /moji-klijenti/ i vidi:
- Sve firme koje je uvela (71+ ghostova + aktivnih)
- Zarada po klijentu (15% komisija)
- One-click invite link + QR kod za printanje
- Status svakog klijenta (ghost/aktivan/suspendiran)
- Bulk invite za sve ghost firme odjednom

---

## KORAK 1: Provjeri što postoji

```bash
sed -n '1045,1090p' registration/views.py
cat templates/registration/agent_dashboard.html | wc -l
grep -n "SalesLead\|agent\|commission" registration/models.py | head -20
grep -n "agent.dashboard\|moji.klijenti" core/urls.py registration/urls.py 2>/dev/null
# Provjeri ghost firme (Company bez korisnika)
python venv/bin/python manage.py shell -c "
import django,os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; django.setup()
from companies.models import Company
ghost = Company.objects.filter(users__isnull=True, is_active=True).count()
print('Ghost firme:', ghost)
total = Company.objects.filter(is_active=True).count()
print('Ukupno firme:', total)
" 2>/dev/null
```

## KORAK 2: View upgrade — agent_dashboard

READ: `registration/views.py` (cijeli `agent_dashboard` view, linija ~1045-1090)
READ: `registration/models.py` (SalesLead, UmbrellaInviteCode, CompanyClaimRequest)
READ: `companies/models.py` (Company fields)

ZAMIJENI cijeli `agent_dashboard` view s ovim:

```python
@login_required
def agent_dashboard(request):
    """
    Agent referral dashboard — 10/10 verzija.
    Prikazuje klijente, komisiju, invite linkove, QR, bulk invite.
    """
    from registration.models import SalesLead, UmbrellaInviteCode
    from companies.models import Company
    from decimal import Decimal
    import qrcode, io, base64

    # --- Veza agenta s klijentima ---
    leads = SalesLead.objects.filter(agent=request.user).select_related('company').order_by('-created_at')

    # Ghost firme dodijeljene ovom agentu (ako postoji field agent na Company)
    # Provjeri: ima li Company.agent FK? Ako ne, koristi samo SalesLead
    ghost_companies = Company.objects.filter(
        users__isnull=True,
        is_active=True
    ).order_by('name')[:50]

    # Komisija
    plan_prices = {'micro': 8, 'starter': 18, 'professional': 58, 'enterprise': 158}
    active_leads = leads.filter(status='active')
    monthly_revenue = sum(plan_prices.get(l.plan, 29) for l in active_leads)
    commission_rate = Decimal('0.15')
    monthly_commission = Decimal(str(monthly_revenue)) * commission_rate

    # Ref kod i invite URL
    ref_code = f'REF-{request.user.username.upper()[:8]}'
    invite_url = request.build_absolute_uri(f'/pocni/?ref={ref_code}')

    # QR kod (base64 PNG)
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(invite_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill='black', back_color='white')
    buffer = io.BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_b64 = base64.b64encode(buffer.getvalue()).decode()

    # Statistike
    stats = {
        'total': leads.count(),
        'active': active_leads.count(),
        'ghost': ghost_companies.count(),
        'signed': leads.filter(status='signed').count(),
        'monthly_revenue': monthly_revenue,
        'monthly_commission': float(monthly_commission),
        'yearly_commission': float(monthly_commission * 12),
    }

    # Bulk invite poruka
    bulk_msg = (
        f"Pozdrav! Pozivam vas na LIMIT Connect — ERP koji koristim za upravljanje vašim knjigovodstvom. "
        f"Potpuno besplatno 14 dana. Registrirajte se ovdje: {invite_url}"
    )

    return render(request, 'registration/agent_dashboard_v2.html', {
        'leads': leads[:30],
        'ghost_companies': ghost_companies,
        'stats': stats,
        'ref_code': ref_code,
        'invite_url': invite_url,
        'qr_b64': qr_b64,
        'bulk_msg': bulk_msg,
        'page_title': 'Moji klijenti',
    })
```

## KORAK 3: URL — dodaj /moji-klijenti/ alias

READ: `core/urls.py` — pronađi blok gdje su korisnički URL-ovi (unutar i18n_patterns).

DODAJ:
```python
# Agent dashboard alias
path('moji-klijenti/', __import__('registration.views', fromlist=['agent_dashboard']).agent_dashboard, name='moji_klijenti'),
```

## KORAK 4: Template — templates/registration/agent_dashboard_v2.html

Design 10/10: dark surface, gold akcenti, KPI kartice na vrhu, klijent lista, QR sekcija.

```html
{% extends "base.html" %}
{% load i18n %}
{% block title %}Moji klijenti — LIMIT Connect{% endblock %}

{% block content %}
<div class="agent-dash">

  <!-- HEADER -->
  <div class="ad-header">
    <div>
      <h1 class="ad-title">Moji klijenti</h1>
      <p class="ad-sub">Ref kod: <code class="ad-code">{{ ref_code }}</code></p>
    </div>
    <button class="btn-gold" onclick="copyInviteUrl()">📋 Kopiraj invite link</button>
  </div>

  <!-- KPI KARTICE -->
  <div class="ad-kpi-grid">
    <div class="ad-kpi">
      <span class="kpi-val">{{ stats.active }}</span>
      <span class="kpi-lbl">Aktivnih klijenata</span>
    </div>
    <div class="ad-kpi">
      <span class="kpi-val">{{ stats.ghost }}</span>
      <span class="kpi-lbl">Ghost firme (neaktivirane)</span>
    </div>
    <div class="ad-kpi kpi-gold">
      <span class="kpi-val">{{ stats.monthly_commission|floatformat:0 }} EUR</span>
      <span class="kpi-lbl">Komisija ovaj mj.</span>
    </div>
    <div class="ad-kpi">
      <span class="kpi-val">{{ stats.yearly_commission|floatformat:0 }} EUR</span>
      <span class="kpi-lbl">Godišnja projekcija</span>
    </div>
  </div>

  <!-- INVITE SEKCIJA -->
  <div class="ad-invite-box">
    <div class="ad-invite-left">
      <h3>Vaš invite link</h3>
      <div class="ad-url-row">
        <input type="text" id="inviteUrl" value="{{ invite_url }}" readonly class="ad-url-input">
        <button class="btn-gold-sm" onclick="copyInviteUrl()">Kopiraj</button>
      </div>
      <p class="ad-micro">Svaki klijent koji se registrira ovim linkom automatski se veže uz vas.</p>

      <h3 style="margin-top:1.5rem;">Bulk poruka za slanje</h3>
      <textarea class="ad-bulk-msg" rows="4" id="bulkMsg">{{ bulk_msg }}</textarea>
      <button class="btn-ghost-sm" onclick="copyBulkMsg()">📋 Kopiraj poruku</button>
    </div>
    <div class="ad-invite-right">
      <p class="ad-qr-lbl">QR za print</p>
      <img src="data:image/png;base64,{{ qr_b64 }}" alt="QR kod" class="ad-qr">
      <button class="btn-ghost-sm" onclick="printQR()">🖨️ Ispiši QR</button>
    </div>
  </div>

  <!-- GHOST FIRME -->
  {% if ghost_companies %}
  <div class="ad-section">
    <h2 class="ad-section-title">
      Ghost firme — čekaju aktivaciju
      <span class="badge-warn">{{ stats.ghost }}</span>
    </h2>
    <p class="ad-section-sub">Firme koje su u sustavu ali vlasnik još nije aktivirao račun.</p>
    <div class="ad-firm-table">
      <table>
        <thead>
          <tr><th>Firma</th><th>OIB</th><th>Akcija</th></tr>
        </thead>
        <tbody>
          {% for c in ghost_companies %}
          <tr>
            <td>{{ c.name }}</td>
            <td><code>{{ c.oib }}</code></td>
            <td>
              <a href="/firma/preuzmi/{{ c.id }}/" class="btn-table-sm" target="_blank">
                Pošalji invite →
              </a>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
  {% endif %}

  <!-- AKTIVNI KLIJENTI -->
  {% if leads %}
  <div class="ad-section">
    <h2 class="ad-section-title">Aktivni klijenti <span class="badge-ok">{{ stats.active }}</span></h2>
    <div class="ad-firm-table">
      <table>
        <thead>
          <tr><th>Firma</th><th>Plan</th><th>Status</th><th>Komisija/mj</th></tr>
        </thead>
        <tbody>
          {% for l in leads %}
          <tr>
            <td>{% if l.company %}{{ l.company.name }}{% else %}{{ l.company_name|default:"—" }}{% endif %}</td>
            <td><span class="badge-plan">{{ l.plan|upper }}</span></td>
            <td>
              {% if l.status == 'active' %}<span class="badge-ok">Aktivan</span>
              {% elif l.status == 'signed' %}<span class="badge-warn">Potpisano</span>
              {% else %}<span class="badge-muted">{{ l.status }}</span>{% endif %}
            </td>
            <td class="gold">
              {% if l.status == 'active' %}
                {% if l.plan == 'starter' %}1.35{% elif l.plan == 'professional' %}4.35{% elif l.plan == 'enterprise' %}11.85{% else %}4.35{% endif %} EUR
              {% else %}—{% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
  {% endif %}

</div>

<style>
.agent-dash { max-width: 1100px; margin: 0 auto; padding: 2rem 1rem; }
.ad-header { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:1rem; margin-bottom:2rem; }
.ad-title { font-size:1.75rem; font-weight:800; color:var(--text-primary); margin:0; }
.ad-sub { color:var(--text-secondary); margin:.25rem 0 0; }
.ad-code { background:var(--surface-elevated); padding:.2rem .6rem; border-radius:6px; font-size:.9rem; color:var(--gold); }

.ad-kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:1rem; margin-bottom:2rem; }
.ad-kpi { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.5rem; text-align:center; }
.ad-kpi.kpi-gold { border-color:rgba(201,168,76,.4); background:rgba(201,168,76,.06); }
.kpi-val { display:block; font-size:2rem; font-weight:800; color:var(--text-primary); }
.kpi-gold .kpi-val { color:var(--gold); }
.kpi-lbl { font-size:.8rem; color:var(--text-secondary); }

.ad-invite-box { display:grid; grid-template-columns:1fr auto; gap:2rem; background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:2rem; margin-bottom:2rem; }
.ad-invite-left h3 { font-size:1rem; font-weight:700; margin-bottom:.75rem; color:var(--text-primary); }
.ad-url-row { display:flex; gap:.5rem; margin-bottom:.5rem; }
.ad-url-input { flex:1; background:var(--surface-elevated); border:1px solid var(--border); border-radius:8px; padding:.6rem .875rem; color:var(--text-primary); font-size:.85rem; }
.ad-micro { font-size:.8rem; color:var(--text-secondary); }
.ad-bulk-msg { width:100%; background:var(--surface-elevated); border:1px solid var(--border); border-radius:8px; padding:.75rem; color:var(--text-primary); font-size:.85rem; resize:vertical; margin-bottom:.5rem; }
.ad-qr-lbl { font-size:.8rem; color:var(--text-secondary); text-align:center; margin-bottom:.5rem; }
.ad-qr { display:block; width:140px; height:140px; border-radius:8px; border:1px solid var(--border); margin:0 auto .75rem; }

.ad-section { margin-bottom:2rem; }
.ad-section-title { font-size:1.25rem; font-weight:700; margin-bottom:.5rem; display:flex; align-items:center; gap:.75rem; }
.ad-section-sub { font-size:.85rem; color:var(--text-secondary); margin-bottom:1rem; }

.ad-firm-table { overflow-x:auto; }
.ad-firm-table table { width:100%; border-collapse:collapse; font-size:.9rem; }
.ad-firm-table th { text-align:left; padding:.75rem 1rem; font-size:.75rem; text-transform:uppercase; letter-spacing:.05em; color:var(--text-secondary); border-bottom:1px solid var(--border); }
.ad-firm-table td { padding:.75rem 1rem; border-bottom:1px solid rgba(255,255,255,.04); color:var(--text-primary); }

.btn-gold { background:var(--gold); color:#000; font-weight:700; border:none; border-radius:8px; padding:.65rem 1.25rem; cursor:pointer; font-size:.9rem; }
.btn-gold:hover { opacity:.88; }
.btn-gold-sm { background:var(--gold); color:#000; font-weight:600; border:none; border-radius:6px; padding:.5rem 1rem; cursor:pointer; font-size:.85rem; white-space:nowrap; }
.btn-ghost-sm { background:transparent; border:1px solid var(--border); color:var(--text-secondary); border-radius:6px; padding:.5rem 1rem; cursor:pointer; font-size:.85rem; }
.btn-ghost-sm:hover { border-color:var(--gold); color:var(--text-primary); }
.btn-table-sm { background:rgba(201,168,76,.12); color:var(--gold); border:1px solid rgba(201,168,76,.25); border-radius:6px; padding:.35rem .75rem; font-size:.8rem; font-weight:600; }

.badge-ok { background:rgba(39,174,96,.15); color:#27ae60; border:1px solid rgba(39,174,96,.3); padding:.2rem .6rem; border-radius:99px; font-size:.75rem; font-weight:600; }
.badge-warn { background:rgba(241,196,15,.15); color:#f1c40f; border:1px solid rgba(241,196,15,.3); padding:.2rem .6rem; border-radius:99px; font-size:.75rem; font-weight:600; }
.badge-muted { color:var(--text-secondary); font-size:.85rem; }
.badge-plan { background:rgba(201,168,76,.1); color:var(--gold); padding:.15rem .5rem; border-radius:4px; font-size:.75rem; font-weight:700; }
.gold { color:var(--gold); font-weight:600; }

@media(max-width:640px) {
  .ad-invite-box { grid-template-columns:1fr; }
  .ad-invite-right { text-align:center; }
  .ad-kpi-grid { grid-template-columns:1fr 1fr; }
}
</style>

<script>
function copyInviteUrl() {
  navigator.clipboard.writeText('{{ invite_url }}').then(() => {
    showToast('✅ Invite link kopiran!');
  });
}
function copyBulkMsg() {
  navigator.clipboard.writeText(document.getElementById('bulkMsg').value).then(() => {
    showToast('✅ Poruka kopirana!');
  });
}
function printQR() {
  const win = window.open('', '_blank');
  win.document.write('<html><body style="text-align:center;padding:2rem;">'
    + '<h2 style="font-family:sans-serif;">LIMIT Connect — ' + '{{ ref_code }}' + '</h2>'
    + '<img src="data:image/png;base64,{{ qr_b64 }}" style="width:300px;height:300px;">'
    + '<p style="font-family:sans-serif;font-size:.9rem;margin-top:1rem;">{{ invite_url }}</p>'
    + '</body></html>');
  win.document.close();
  win.print();
}
function showToast(msg) {
  const t = document.createElement('div');
  t.textContent = msg;
  t.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;background:var(--gold);color:#000;padding:.75rem 1.25rem;border-radius:8px;font-weight:700;z-index:9999;';
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2500);
}
</script>
{% endblock %}
```

## KORAK 5: qrcode dependency

```bash
cd /var/www/fina-connect
source venv/bin/activate 2>/dev/null || true
pip install qrcode[pil] --break-system-packages -q
python -c "import qrcode; print('qrcode OK')"
```

## KORAK 6: Verifikacija

```bash
python venv/bin/python manage.py check 2>&1 | tail -3
systemctl restart gunicorn-fina
# Testiraj kao agent korisnik
curl -s -o /dev/null -w "%{http_code}" -b "sessionid=TEST" http://localhost:8000/hr/moji-klijenti/
# Očekivano: 302 (redirect na login) — OK
```

## DONE kriteriji:
- [ ] /hr/moji-klijenti/ URL postoji (302 za nelogiranog)
- [ ] agent_dashboard_v2.html postoji i renderira se
- [ ] KPI kartice: broj aktivnih, ghost, komisija prikazani
- [ ] Ghost firme tablica prikazana s "Pošalji invite" linkom
- [ ] QR kod se generira kao base64 PNG
- [ ] Kopiraj invite URL radi (clipboard)
- [ ] Printaj QR otvara print dialog
- [ ] Bulk message textarea popunjena
- [ ] qrcode lib instaliran
