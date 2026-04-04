# GEMINI TASK: Notariat + Odvjetnik + Dimnjačar — Sprint 0+1+2
**Datum:** 03.04.2026. | **Rok:** 10.04.2026.
**Izvršava:** Gemini autonomno | **Max koraka:** 25

---

## OBVEZNO — PROČITAJ PRVO (ne preskačaj)

READ: /var/www/fina-connect/CC_TASK_BLAGDANSKI_SPRINT_NOTARIAT.md

Zatim provjeri što postoji:
EXEC: cd /var/www/fina-connect && grep -n "class Appointment\|class ClientDossier" appointments/models.py 2>/dev/null | head -5
EXEC: cd /var/www/fina-connect && ls notariat/ 2>/dev/null || echo "notariat app ne postoji"
EXEC: cd /var/www/fina-connect && grep -n "notariat\|biljeznik\|dimnjac" core/settings.py | head -10

---

## SPRINT 0 — CroValidator API (nema migracije, deploy odmah)

### Korak 1: Pročitaj postojeći OIB validator
READ: /var/www/fina-connect/core/oib_validator.py

### Korak 2: Dodaj IBAN + MBS validaciju NA KRAJ fajla
WRITE: /var/www/fina-connect/core/oib_validator.py
Dodaj na kraj (ne briši postojeće):

```python
def validate_iban(iban: str) -> bool:
    """ISO 13616 MOD 97 IBAN validacija."""
    iban = iban.strip().replace(' ', '').upper()
    if len(iban) < 15 or len(iban) > 34:
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = ''
    for ch in rearranged:
        if ch.isdigit():
            numeric += ch
        elif ch.isalpha():
            numeric += str(ord(ch) - ord('A') + 10)
        else:
            return False
    return int(numeric) % 97 == 1

def validate_hr_iban(iban: str) -> bool:
    """HR IBAN: HR + 2 kontrolne + 7 bankovnih + 10 računa = 21 znak."""
    iban = iban.strip().replace(' ', '').upper()
    if not iban.startswith('HR') or len(iban) != 21:
        return False
    return validate_iban(iban)

def validate_mbs(mbs: str) -> bool:
    """MBS: točno 8 znamenki."""
    mbs = mbs.strip()
    return bool(mbs and len(mbs) == 8 and mbs.isdigit())
```

### Korak 3: Kreiraj views_validate.py
WRITE: /var/www/fina-connect/core/views_validate.py

```python
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from core.oib_validator import validate_oib_hr, validate_hr_iban, validate_iban, validate_mbs

@csrf_exempt
@require_POST
def api_validate(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    result = {}
    if 'oib' in data:
        oib = str(data['oib']).strip()
        valid = validate_oib_hr(oib)
        result['oib'] = {'valid': valid, 'value': oib,
            'error': None if valid else 'OIB nije valjan (modulo 11)'}
    if 'iban' in data:
        iban = str(data['iban']).strip()
        valid = validate_hr_iban(iban) if iban.upper().startswith('HR') else validate_iban(iban)
        result['iban'] = {'valid': valid, 'value': iban,
            'error': None if valid else 'IBAN nije valjan (MOD 97)'}
    if 'mbs' in data:
        mbs = str(data['mbs']).strip()
        valid = validate_mbs(mbs)
        result['mbs'] = {'valid': valid, 'value': mbs,
            'error': None if valid else 'MBS mora imati točno 8 znamenki'}
    return JsonResponse(result)
```

### Korak 4: Provjeri core/urls.py i dodaj endpoint
READ: /var/www/fina-connect/core/urls.py (samo zadnjih 30 linija)
WRITE: dodaj u urlpatterns:
```python
path('api/v1/validate/', views_validate.api_validate, name='api_validate'),
```
i import: `from core import views_validate`

### Korak 5: Test validatora
EXEC: cd /var/www/fina-connect && venv/bin/python -c "
from core.oib_validator import validate_oib_hr, validate_hr_iban, validate_mbs
print('OIB test:', validate_oib_hr('37590751921'))
print('IBAN test:', validate_hr_iban('HR1210010051863000160'))
print('MBS test:', validate_mbs('12345678'))
"

---

## SPRINT 1 — Notariat Django app

### Korak 6: Kreiraj notariat app strukturu
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py startapp notariat 2>/dev/null || echo "vec postoji"
EXEC: cd /var/www/fina-connect && ls notariat/

### Korak 7: Provjeri Company model za pdf_template
EXEC: cd /var/www/fina-connect && grep -n "pdf_template\|CompanyManager\|class Company" companies/models.py | head -10

### Korak 8: Provjeri employees model
EXEC: cd /var/www/fina-connect && grep -n "class EmployeeProfile\|class Employee" employees/models.py 2>/dev/null | head -5

### Korak 9: Napiši notariat/models.py
WRITE: /var/www/fina-connect/notariat/models.py

Modeli koje treba implementirati (provjeri FK ime iz rezultata koraka 7 i 8):
- NotariatPredlozak (company FK, vrsta choices: punomoc/osnivanje_jdoo/osnivanje_doo/kupoprodaja_nekr/zaduznica/bjanko_zaduznica/darovanje/maloljetnik_put/nasljedstvo/dozivotno_uzdrz/potvrda_dimnjak/nalaz_dimnjak)
- PravniPredmet (company FK, klijent FK, naziv, vrsta, status, satnica_eur, datum_otvaranja, rok, napomena)
- DimnjacarskaInspekcija (company FK, klijent FK, adresa, broj_dimnjaka, vrsta_goriva, datum_pregleda, status_dimnjaka: ispravan/uvjetno/neispravan, opis_nalaza, preporuke, sljedeci_pregled, pdf_sha256)

Svaki model mora imati: CompanyManager kao objects, class Meta ordering, __str__ metodu.

### Korak 10: Napiši notariat/apps.py
WRITE: /var/www/fina-connect/notariat/apps.py
```python
from django.apps import AppConfig
class NotariatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notariat'
    verbose_name = 'Notariat i pravne usluge'
```

### Korak 11: Dodaj notariat u INSTALLED_APPS
READ: /var/www/fina-connect/core/settings.py (linija oko INSTALLED_APPS)
WRITE: dodaj 'notariat' u INSTALLED_APPS listu

### Korak 12: Migracija
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py makemigrations notariat --name notariat_pravni_dimnjak 2>&1
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py migrate 2>&1 | tail -10

---

## SPRINT 2 — Views i URL-ovi

### Korak 13: Napiši notariat/views.py
WRITE: /var/www/fina-connect/notariat/views.py

```python
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from datetime import date, timedelta
from .models import PravniPredmet, DimnjacarskaInspekcija

@login_required
def pravnik_dashboard(request):
    company = request.user.userprofile.company
    predmeti = PravniPredmet.objects.filter(company=company, status='aktivan')
    pred_s_rokom = predmeti.filter(
        rok__gte=date.today(),
        rok__lte=date.today() + timedelta(days=7)
    )
    return render(request, 'notariat/pravnik_dashboard.html', {
        'predmeti': predmeti,
        'pred_s_rokom': pred_s_rokom,
        'page_title': 'Odvjetnički dashboard',
    })

@login_required
def dimnjacari_dashboard(request):
    company = request.user.userprofile.company
    inspekcije = DimnjacarskaInspekcija.objects.filter(company=company)
    sljedeci = inspekcije.filter(
        sljedeci_pregled__gte=date.today(),
        sljedeci_pregled__lte=date.today() + timedelta(days=30)
    ).order_by('sljedeci_pregled')
    return render(request, 'notariat/dimnjacari_dashboard.html', {
        'inspekcije': inspekcije,
        'sljedeci': sljedeci,
        'page_title': 'Dimnjačarski pregledi',
    })
```

### Korak 14: Napiši notariat/urls.py
WRITE: /var/www/fina-connect/notariat/urls.py

```python
from django.urls import path
from . import views

app_name = 'notariat'

urlpatterns = [
    path('pravnik/', views.pravnik_dashboard, name='pravnik_dashboard'),
    path('dimnjacari/', views.dimnjacari_dashboard, name='dimnjacari_dashboard'),
]
```

### Korak 15: Dodaj notariat URLs u core/urls.py
EXEC: cd /var/www/fina-connect && grep -n "include.*knjiznica\|include.*seasonal\|include.*delivery" core/urls.py | head -5
WRITE: dodaj u urlpatterns: path('notariat/', include('notariat.urls')),

### Korak 16: Kreiraj osnovne template direktorije i fajlove
EXEC: mkdir -p /var/www/fina-connect/notariat/templates/notariat

WRITE: /var/www/fina-connect/notariat/templates/notariat/pravnik_dashboard.html
```html
{% extends "base.html" %}
{% block page_title %}Odvjetnički dashboard{% endblock %}
{% block content %}
<div class="f-container">
  <div class="f-hero">
    <h3 class="f-heading f-heading-lg">⚖️ Odvjetnički dashboard</h3>
    <p class="f-subtitle">Aktivni predmeti i rokovi</p>
  </div>
  {% if pred_s_rokom %}
  <div class="f-card f-card-red mb-3">
    <div class="f-heading f-heading-sm">⏰ Rokovi u sljedećih 7 dana</div>
    {% for p in pred_s_rokom %}
    <div class="d-flex justify-content-between py-2 border-bottom">
      <span>{{ p.naziv }}</span>
      <span class="f-red">{{ p.rok }}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  <div class="f-panel">
    <div class="f-panel-header">Aktivni predmeti ({{ predmeti.count }})</div>
    <table class="f-table">
      <thead><tr><th>Predmet</th><th>Vrsta</th><th>Klijent</th><th>Rok</th></tr></thead>
      <tbody>
      {% for p in predmeti %}
      <tr>
        <td>{{ p.naziv }}</td>
        <td>{{ p.get_vrsta_display }}</td>
        <td>{{ p.klijent|default:"-" }}</td>
        <td>{{ p.rok|default:"-" }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="4" class="text-center f-muted py-3">Nema aktivnih predmeta</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

WRITE: /var/www/fina-connect/notariat/templates/notariat/dimnjacari_dashboard.html
```html
{% extends "base.html" %}
{% block page_title %}Dimnjačarski pregledi{% endblock %}
{% block content %}
<div class="f-container">
  <div class="f-hero">
    <h3 class="f-heading f-heading-lg">🔥 Dimnjačarski pregledi</h3>
    <p class="f-subtitle">Evidencija prema NN 103/15</p>
  </div>
  {% if sljedeci %}
  <div class="f-card f-card-gold mb-3">
    <div class="f-heading f-heading-sm">📅 Sljedeći pregledi (30 dana)</div>
    {% for i in sljedeci %}
    <div class="d-flex justify-content-between py-2 border-bottom">
      <span>{{ i.adresa }}</span>
      <span class="f-amber">{{ i.sljedeci_pregled }}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  <div class="f-panel">
    <div class="f-panel-header">Svi pregledi ({{ inspekcije.count }})</div>
    <table class="f-table">
      <thead><tr><th>Adresa</th><th>Dimnjak</th><th>Status</th><th>Datum</th><th>Sljedeći</th></tr></thead>
      <tbody>
      {% for i in inspekcije %}
      <tr>
        <td>{{ i.adresa }}</td>
        <td>{{ i.broj_dimnjaka }}</td>
        <td>
          {% if i.status_dimnjaka == 'ispravan' %}<span class="badge bg-success">✓ Ispravan</span>
          {% elif i.status_dimnjaka == 'uvjetno' %}<span class="badge bg-warning">⚠ Uvjetno</span>
          {% else %}<span class="badge bg-danger">✗ Neispravan</span>{% endif %}
        </td>
        <td>{{ i.datum_pregleda }}</td>
        <td>{{ i.sljedeci_pregled|default:"-" }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="5" class="text-center f-muted py-3">Nema evidentiranih pregleda</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

---

## SPRINT 3 — Provjera i deploy

### Korak 17: Django check
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | grep -E "ERROR|WARNING|notariat" | head -20

### Korak 18: Git commit
EXEC: cd /var/www/fina-connect && git add notariat/ core/oib_validator.py core/views_validate.py core/urls.py core/settings.py && git commit -m "feat(notariat): bilježnik+odvjetnik+dimnjačar MVP — CroValidator API + 3 modela + dashboardi"

### Korak 19: Restart
EXEC: systemctl restart gunicorn-fina

### Korak 20: Verifikacija
EXEC: curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/v1/validate/ -X POST -H "Content-Type: application/json" -d '{"oib":"37590751921"}' && echo " validate API"

---

## DONE kriterij:
- core/oib_validator.py ima validate_iban() i validate_mbs()
- core/views_validate.py postoji, URL registriran
- notariat/ app postoji s 3 modela i 2 dashboarda
- Migracija primijenjena bez greška
- Gunicorn restartovan
- Validate API vraća 200

