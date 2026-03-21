# CC Task — Institutional Access: Read-Only pristup državnim institucijama

## Pročitaj prvo — OBAVEZNO
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
cat /var/www/fina-connect/synesis/models.py | head -60     # api_token pattern — nasljeđujemo
cat /var/www/fina-connect/accounts/auth_models.py           # MagicToken — expires_at pattern
sed -n '235,270p' /var/www/fina-connect/propter/views.py   # X-API-Key auth pattern
grep -n "^class\|karencija_do\|is_blocked\|ear_tag\|jrdz" \
  /var/www/fina-connect/livestock/models.py | head -30
```

## Kontekst i strategija

Državne institucije trebaju **read-only** uvid u podatke farme:

| Institucija | Što smije vidjeti | Zakonska osnova |
|---|---|---|
| HAPIH | Lijekovi + karencije | EU Reg 2019/6, Zakon o vet. djelatnosti |
| JRDŽ / ePoljoprivreda | Kretanje životinja, teljenja | Pravilnik o označavanju |
| VetIS | Kompletna vet. knjiga | Veterinarski zakon HR |
| Sanitarna inspekcija | Blokade prodaje mlijeka | Zakon o hrani |
| FINA / Porezna | Fakture, blagajna | OPZ, Zakon o računovodstvu |

**Ključno pravilo**: institucija NIKAD ne piše podatke. Samo čita.
**Ključni pattern**: `SynesisConfig.api_token` — farmer dobije token,
daje ga instituciji, institucija ga stavlja u header, pristup je odobren.

---

## KORAK 0 — Provjeri stvarna polja PRIJE pisanja
```bash
python manage.py shell -c "
from livestock.models import Livestock, HealthRecord, JRDZRegistration
print('Livestock fields:', [f.name for f in Livestock._meta.fields])
print('HealthRecord fields:', [f.name for f in HealthRecord._meta.fields])
try:
    print('JRDZ fields:', [f.name for f in JRDZRegistration._meta.fields])
except:
    print('JRDZRegistration: NEMA (CC_TASK_LIVESTOCK_V3 mora biti gotov)')
from inventory.models import InventoryItem
print('InventoryItem blocked fields:', [f.name for f in InventoryItem._meta.fields if 'block' in f.name])
"
```

---

## MODEL: InstitutionalAccessToken

```python
# Dodaj u livestock/models.py (ili novi institutional/models.py ako wolish):

import secrets as _secrets

class InstitutionalAccessToken(models.Model):
    """
    Token za read-only pristup državnih institucija podacima OPG-a.

    Pattern nasljeđen iz SynesisConfig.api_token:
    - secrets.token_urlsafe(32) — kriptografski siguran
    - is_active flag — farmer može odmah opozvati
    - expires_at — opcionalno vremensko ograničenje
    - scope — što institucija smije vidjeti

    Farmer kreira token u postavkama → daje ga instituciji →
    institucija šalje X-Institution-Token header → read-only API.
    """

    SCOPE_CHOICES = [
        ('hapih',     'HAPIH — Lijekovi i karencije'),
        ('jrdz',      'JRDŽ — Kretanje životinja'),
        ('vetis',     'VetIS — Kompletna vet. knjiga'),
        ('sanitarna', 'Sanitarna inspekcija — Blokade mlijeka'),
        ('fina',      'FINA / Porezna — Fakture i blagajna'),
        ('full_read', 'Puni read-only pristup (revizija)'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='institutional_tokens',
        verbose_name='OPG / Firma',
    )
    naziv_institucije = models.CharField(
        max_length=200,
        verbose_name='Naziv institucije',
        help_text='npr. HAPIH — Područni ured Osijek',
    )
    scope = models.CharField(
        max_length=20, choices=SCOPE_CHOICES,
        verbose_name='Razina pristupa',
    )
    token = models.CharField(
        max_length=64, unique=True,
        default=lambda: _secrets.token_urlsafe(32),
        editable=False,
        verbose_name='Access token',
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktivan')
    expires_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Ističe (prazno = trajno)',
    )
    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Kreirao',
    )
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)
    request_count = models.PositiveIntegerField(default=0, verbose_name='Broj upita')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'livestock_institutional_token'
        ordering = ['-created_at']
        verbose_name = 'Institucionalni access token'
        verbose_name_plural = 'Institucionalni access tokeni'

    def __str__(self):
        return f'{self.naziv_institucije} → {self.company.name} [{self.get_scope_display()}]'

    @property
    def is_valid(self):
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    def regenerate(self):
        """Farmer opoziva stari token i dobiva novi."""
        self.token = _secrets.token_urlsafe(32)
        self.request_count = 0
        self.last_used_at = None
        self.save(update_fields=['token', 'request_count', 'last_used_at'])
        return self.token

    def record_access(self, ip=None):
        """Bilježi svaki pristup institucije — audit trail."""
        from django.utils import timezone
        self.last_used_at = timezone.now()
        self.last_used_ip = ip
        self.request_count += 1
        self.save(update_fields=['last_used_at', 'last_used_ip', 'request_count'])
```

### Migracije
```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations livestock --name="add_institutional_token"
venv/bin/python manage.py migrate livestock
venv/bin/python manage.py check
```

---

## AUTH HELPER — zajednički za sve institucionalne endpointe

```python
# livestock/views.py — dodaj helper:

def _get_institutional_token(request, required_scope=None):
    """
    Autentikacija institutionalnog pristupa.
    Header: X-Institution-Token: <token>

    Vraća (token_obj, error_response).
    Ako error_response nije None — odmah vrati ga iz viewa.
    """
    from django.http import JsonResponse
    from django.utils import timezone

    raw = request.headers.get('X-Institution-Token', '').strip()
    if not raw:
        return None, JsonResponse(
            {'error': 'X-Institution-Token header obavezan'},
            status=401
        )

    try:
        tok = InstitutionalAccessToken.objects.select_related('company').get(
            token=raw
        )
    except InstitutionalAccessToken.DoesNotExist:
        return None, JsonResponse({'error': 'Nevaljan token'}, status=403)

    if not tok.is_valid:
        return None, JsonResponse(
            {'error': 'Token istekao ili deaktiviran. Kontaktirajte OPG.'},
            status=403
        )

    if required_scope and tok.scope not in (required_scope, 'full_read'):
        return None, JsonResponse(
            {'error': f'Ovaj token nema pristup scope={required_scope}'},
            status=403
        )

    # Audit
    tok.record_access(ip=request.META.get('REMOTE_ADDR'))
    return tok, None
```

---

## ENDPOINT 1 — HAPIH: Evidencija lijekova i karencija

```
GET /livestock/api/institutional/hapih/
Header: X-Institution-Token: <token>
Scope: hapih | full_read
```

```python
# livestock/views.py:

@csrf_exempt
def api_institutional_hapih(request):
    """
    HAPIH read-only: svi tretmani s antimikrobnim lijekovima.
    EU Reg 2019/6 format: životinja, lijek, doza, karencija, veterinar.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET only'}, status=405)

    tok, err = _get_institutional_token(request, required_scope='hapih')
    if err:
        return err

    from django.utils import timezone
    from livestock.models import HealthRecord, Livestock

    # Parametri filtera iz query stringa
    od = request.GET.get('od')   # YYYY-MM-DD
    do = request.GET.get('do')   # YYYY-MM-DD
    samo_antibiotici = request.GET.get('antibiotici', '0') == '1'

    qs = HealthRecord.objects.filter(
        animal__company=tok.company,
        tip__in=['tretman', 'cijepljenje'],
    ).select_related('animal').order_by('-datum')

    if od:
        try:
            import datetime
            qs = qs.filter(datum__gte=datetime.date.fromisoformat(od))
        except ValueError:
            pass
    if do:
        try:
            import datetime
            qs = qs.filter(datum__lte=datetime.date.fromisoformat(do))
        except ValueError:
            pass
    if samo_antibiotici:
        # Filtriraj samo zapise s karencijom (proxy za antibiotike)
        qs = qs.filter(karencija_do__isnull=False)

    today = timezone.now().date()
    rezultati = []
    for hr in qs[:500]:  # Max 500 zapisa po pozivu
        rezultati.append({
            'ear_tag': hr.animal.ear_tag,
            'vrsta': hr.animal.get_vrsta_display(),
            'datum_tretmana': str(hr.datum),
            'tip': hr.get_tip_display(),
            'lijek': hr.lijek,
            'doza': hr.kolicina,
            'veterinar': hr.veterinar,
            'karencija_do': str(hr.karencija_do) if hr.karencija_do else None,
            'u_karenciji': hr.u_karenciji,
            'karencija_dani_preostalo': (hr.karencija_do - today).days if hr.karencija_do and hr.karencija_do >= today else 0,
            'is_organic': hr.animal.is_organic,
        })

    return JsonResponse({
        'institution': tok.naziv_institucije,
        'company': tok.company.name,
        'oib_opg': tok.company.oib,
        'scope': 'hapih',
        'eu_regulation': 'EU 2019/6',
        'zapisi': len(rezultati),
        'tretmani': rezultati,
        'generiran': str(timezone.now().isoformat()),
    })
```

---

## ENDPOINT 2 — JRDŽ: Kretanje životinja

```
GET /livestock/api/institutional/jrdz/
Header: X-Institution-Token: <token>
Scope: jrdz | full_read
```

```python
@csrf_exempt
def api_institutional_jrdz(request):
    """
    JRDŽ read-only: sve registracije kretanja (teljenja, uginuća, premještaji).
    Kompatibilan s JRDŽ XML formatom za ePoljoprivreda.mps.hr.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET only'}, status=405)

    tok, err = _get_institutional_token(request, required_scope='jrdz')
    if err:
        return err

    from django.utils import timezone

    try:
        from livestock.models import JRDZRegistration, Livestock
    except ImportError:
        return JsonResponse({'error': 'JRDŽ modul nije instaliran (CC_TASK_LIVESTOCK_V3)'}, status=503)

    # Sva grla farme
    grla = Livestock.objects.filter(company=tok.company).order_by('ear_tag')
    registracije = JRDZRegistration.objects.filter(
        company=tok.company
    ).select_related('animal').order_by('-datum_dogadjaja')[:500]

    return JsonResponse({
        'institution': tok.naziv_institucije,
        'company': tok.company.name,
        'oib_opg': tok.company.oib,
        'scope': 'jrdz',
        'stado': {
            'ukupno': grla.count(),
            'aktivnih': grla.filter(status='aktivno').count(),
            'gravidnih': grla.filter(status='gravidno').count(),
        },
        'registracije': [
            {
                'ear_tag': r.animal.ear_tag,
                'tip': r.get_tip_display(),
                'status': r.get_status_display(),
                'datum_dogadjaja': str(r.datum_dogadjaja),
                'rok_prijave': str(r.rok_prijave),
                'datum_prijave': str(r.datum_prijave) if r.datum_prijave else None,
                'prekoraceno': r.prekoraceno,
                'jrdz_referenca': r.jrdz_referenca,
            } for r in registracije
        ],
        'generiran': str(timezone.now().isoformat()),
    })
```

---

## ENDPOINT 3 — Sanitarna inspekcija: Blokade mlijeka

```
GET /livestock/api/institutional/sanitarna/
Header: X-Institution-Token: <token>
Scope: sanitarna | full_read
```

```python
@csrf_exempt
def api_institutional_sanitarna(request):
    """
    Sanitarna inspekcija: koji artikli su blokirani za prodaju i zašto.
    Direktno iz InventoryItem.is_blocked (post karencija signal).
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET only'}, status=405)

    tok, err = _get_institutional_token(request, required_scope='sanitarna')
    if err:
        return err

    from django.utils import timezone
    from inventory.models import InventoryItem
    from livestock.models import HealthRecord

    today = timezone.now().date()

    # Trenutno blokirani artikli
    blokirani = InventoryItem.objects.filter(
        company=tok.company, is_blocked=True
    )

    # Aktivne karencije (direktno iz HealthRecord)
    aktivne_karencije = HealthRecord.objects.filter(
        animal__company=tok.company,
        karencija_do__gte=today,
    ).select_related('animal').order_by('karencija_do')

    return JsonResponse({
        'institution': tok.naziv_institucije,
        'company': tok.company.name,
        'oib_opg': tok.company.oib,
        'scope': 'sanitarna',
        'status_farme': 'UPOZORENJE' if blokirani.exists() else 'ČISTO',
        'blokirani_artikli': [
            {
                'naziv': item.name,
                'sku': item.sku,
                'razlog': item.blocked_reason,
                'blokirano_do': str(item.blocked_until) if item.blocked_until else None,
            } for item in blokirani
        ],
        'aktivne_karencije': [
            {
                'ear_tag': hr.animal.ear_tag,
                'lijek': hr.lijek,
                'karencija_do': str(hr.karencija_do),
                'preostalo_dana': (hr.karencija_do - today).days,
                'veterinar': hr.veterinar,
            } for hr in aktivne_karencije
        ],
        'generiran': str(timezone.now().isoformat()),
    })
```

---

## ENDPOINT 4 — VetIS: Kompletna veterinarska knjiga (EU obveza)

```
GET /livestock/api/institutional/vetis/
Header: X-Institution-Token: <token>
Scope: vetis | full_read
```

```python
@csrf_exempt
def api_institutional_vetis(request):
    """
    VetIS / EU Knjiga evidencije o liječenju (EU Reg 2019/6, čl. 108).
    Svi vet zapisi, uključujući preglede i cjepiva.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET only'}, status=405)

    tok, err = _get_institutional_token(request, required_scope='vetis')
    if err:
        return err

    from django.utils import timezone
    from livestock.models import Livestock, HealthRecord

    od = request.GET.get('od')
    do = request.GET.get('do')

    qs = HealthRecord.objects.filter(
        animal__company=tok.company
    ).select_related('animal').order_by('-datum')

    if od:
        try:
            import datetime
            qs = qs.filter(datum__gte=datetime.date.fromisoformat(od))
        except ValueError:
            pass
    if do:
        try:
            import datetime
            qs = qs.filter(datum__lte=datetime.date.fromisoformat(do))
        except ValueError:
            pass

    return JsonResponse({
        'institution': tok.naziv_institucije,
        'company': tok.company.name,
        'oib_opg': tok.company.oib,
        'scope': 'vetis',
        'eu_regulation': 'EU Regulation 2019/6, Article 108',
        'knjiga_lijecenja': [
            {
                'id': hr.pk,
                'ear_tag': hr.animal.ear_tag,
                'naziv_zivotinje': hr.animal.name or '',
                'vrsta': hr.animal.get_vrsta_display(),
                'datum': str(hr.datum),
                'tip': hr.get_tip_display(),
                'dijagnoza_opis': hr.opis,
                'veterinar': hr.veterinar,
                'lijek': hr.lijek,
                'doza': hr.kolicina,
                'karencija_meso_do': str(hr.karencija_do) if hr.karencija_do else None,
                'karencija_mlijeko_do': str(hr.karencija_do) if hr.karencija_do else None,
                'trosak_eur': float(hr.trošak_eur) if hr.trošak_eur else None,
            } for hr in qs[:1000]
        ],
        'ukupno_zapisa': qs.count(),
        'generiran': str(timezone.now().isoformat()),
    })
```

---

## URL REGISTRACIJA

```python
# livestock/urls.py — dodaj:

path('api/institutional/hapih/',     views.api_institutional_hapih,     name='api_hapih'),
path('api/institutional/jrdz/',      views.api_institutional_jrdz,      name='api_jrdz'),
path('api/institutional/sanitarna/', views.api_institutional_sanitarna,  name='api_sanitarna'),
path('api/institutional/vetis/',     views.api_institutional_vetis,      name='api_vetis'),
```

---

## UI ZA FARMERA — upravljanje tokenima

```python
# livestock/views.py — farmer kreira/opoziva tokene:

@login_required
def institutional_tokens(request):
    """
    Farmer vidi sve aktivne institucionalne tokene i kreira nove.
    /livestock/institutional-tokens/
    """
    from core.company_utils import get_user_company
    company = get_user_company(request)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            tok = InstitutionalAccessToken.objects.create(
                company=company,
                naziv_institucije=request.POST.get('naziv', ''),
                scope=request.POST.get('scope', 'hapih'),
                created_by=request.user,
            )
            from django.contrib import messages
            messages.success(request,
                f'Token kreiran: {tok.token[:20]}... — daj ga instituciji.')

        elif action == 'revoke':
            tok_id = request.POST.get('token_id')
            InstitutionalAccessToken.objects.filter(
                pk=tok_id, company=company
            ).update(is_active=False)
            from django.contrib import messages
            messages.warning(request, 'Token opozvan — institucija više nema pristup.')

        elif action == 'regenerate':
            tok_id = request.POST.get('token_id')
            tok = InstitutionalAccessToken.objects.filter(
                pk=tok_id, company=company
            ).first()
            if tok:
                novi = tok.regenerate()
                from django.contrib import messages
                messages.success(request, f'Novi token: {novi[:20]}...')

        return redirect('livestock:institutional_tokens')

    tokeni = InstitutionalAccessToken.objects.filter(
        company=company
    ).order_by('-created_at')

    return render(request, 'livestock/institutional_tokens.html', {
        'tokeni': tokeni,
        'scope_choices': InstitutionalAccessToken.SCOPE_CHOICES,
    })
```

```python
# URL:
path('institutional-tokens/', views.institutional_tokens, name='institutional_tokens'),
```

---

## TEMPLATE — livestock/templates/livestock/institutional_tokens.html

Minimalan, funkcionalan:
```html
{% extends "base.html" %}
{% block content %}
<div class="container mt-4">
  <h2>Pristup državnim institucijama</h2>
  <p class="text-muted">
    Svaka institucija dobiva vlastiti token. Farmer može opozvati pristup u bilo koje trenutku.
  </p>

  {% for tok in tokeni %}
  <div class="card mb-3 {% if not tok.is_valid %}border-danger{% endif %}">
    <div class="card-body">
      <div class="d-flex justify-content-between">
        <div>
          <strong>{{ tok.naziv_institucije }}</strong>
          <span class="badge bg-secondary ms-2">{{ tok.get_scope_display }}</span>
          {% if not tok.is_valid %}<span class="badge bg-danger ms-1">Neaktivan</span>{% endif %}
        </div>
        <small class="text-muted">{{ tok.request_count }} upita | zadnji: {{ tok.last_used_at|default:"nikad" }}</small>
      </div>
      <code class="d-block mt-2 text-break">{{ tok.token }}</code>
      <small class="text-muted">
        Kreiran: {{ tok.created_at|date:"d.m.Y." }}
        {% if tok.expires_at %} | Ističe: {{ tok.expires_at|date:"d.m.Y." }}{% endif %}
      </small>
      <div class="mt-2">
        <form method="post" class="d-inline">
          {% csrf_token %}
          <input type="hidden" name="token_id" value="{{ tok.pk }}">
          <button name="action" value="revoke" class="btn btn-sm btn-outline-danger"
            onclick="return confirm('Opozovi pristup?')">Opozovi</button>
          <button name="action" value="regenerate" class="btn btn-sm btn-outline-warning"
            onclick="return confirm('Generiraj novi token? Stari prestaje raditi odmah.')">Novi token</button>
        </form>
        <small class="ms-3 text-muted">
          Endpoint: <code>GET /livestock/api/institutional/{{ tok.scope }}/</code>
          | Header: <code>X-Institution-Token: [token]</code>
        </small>
      </div>
    </div>
  </div>
  {% endfor %}

  <hr>
  <h5>Dodaj pristup novoj instituciji</h5>
  <form method="post" class="row g-3">
    {% csrf_token %}
    <input type="hidden" name="action" value="create">
    <div class="col-md-5">
      <input type="text" name="naziv" class="form-control"
        placeholder="HAPIH — Područni ured Osijek" required>
    </div>
    <div class="col-md-4">
      <select name="scope" class="form-select">
        {% for val, label in scope_choices %}
        <option value="{{ val }}">{{ label }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="col-md-3">
      <button type="submit" class="btn btn-primary w-100">Kreiraj token</button>
    </div>
  </form>
</div>
{% endblock %}
```

---

## UPUTE ZA INSTITUCIJU (generiraj kao PDF ili email)

```python
# livestock/services.py — helper za slanje uputa instituciji:

def posalji_upute_instituciji(token_obj, email_institucije=None):
    """
    Šalje email ili WhatsApp s uputama za korištenje API-ja.
    """
    scope_endpoint = {
        'hapih': '/livestock/api/institutional/hapih/',
        'jrdz': '/livestock/api/institutional/jrdz/',
        'vetis': '/livestock/api/institutional/vetis/',
        'sanitarna': '/livestock/api/institutional/sanitarna/',
        'fina': '/livestock/api/institutional/fina/',
        'full_read': '/livestock/api/institutional/hapih/ (i ostali)',
    }
    endpoint = scope_endpoint.get(token_obj.scope, '/livestock/api/institutional/')

    upute = f"""
LIMIT Connect — Pristup podacima OPG-a
======================================
Institucija: {token_obj.naziv_institucije}
OPG: {token_obj.company.name} (OIB: {token_obj.company.oib})
Razina pristupa: {token_obj.get_scope_display()}

KAKO KORISTITI:
GET https://limit-connect.com{endpoint}
Header: X-Institution-Token: {token_obj.token}

Primjer (curl):
curl -H "X-Institution-Token: {token_obj.token}" \\
     https://limit-connect.com{endpoint}

Primjer (Python):
import requests
r = requests.get(
    "https://limit-connect.com{endpoint}",
    headers={{"X-Institution-Token": "{token_obj.token}"}}
)
data = r.json()

FILTERI (opcionalni query parametri):
?od=2026-01-01&do=2026-12-31   — vremenski raspon
?antibiotici=1                  — samo antimikrobni (za HAPIH)

NAPOMENA: Token je read-only. Nema mogućnosti mijenjanja podataka.
Farmer može opozvati pristup u bilo koje trenutku.
"""
    return upute
```

---

## VERIFIKACIJA

```bash
cd /var/www/fina-connect

# 1. Migracije
venv/bin/python manage.py makemigrations livestock --name="add_institutional_token"
venv/bin/python manage.py migrate livestock
venv/bin/python manage.py check

# 2. Kreiraj test token za OPG Kruljac
venv/bin/python manage.py shell -c "
from livestock.models import InstitutionalAccessToken
from companies.models import Company
kruljac = Company.objects.get(name__icontains='Kruljac')
tok = InstitutionalAccessToken.objects.create(
    company=kruljac,
    naziv_institucije='HAPIH — Test',
    scope='hapih',
)
print('Token:', tok.token)
print('Valid:', tok.is_valid)
print('Test:')
print(f'curl -H \"X-Institution-Token: {tok.token}\" https://limit-connect.com/livestock/api/institutional/hapih/')
"

# 3. Restart
systemctl restart gunicorn-fina
```

---

## VLASTITI PRIJEDLOZI — CC Code slobodne ruke

Dok čitaš kod, provjeri:
1. Postoji li rate limiting na API endpointima? Institucija ne smije "floodati" API.
   → Dodaj `request_count` provjeru: max 1000 upita/dan po tokenu.
2. Treba li `InstitutionalAccessLog` model za detaljni audit trail svakog upita?
   → Svaki GET → log s IP, timestamp, query params, rezultat count.
   → HAPIH može tražiti "pokažite mi sve vaše API logove" pri inspekciji.
3. Je li JSON format kompatibilan s onime što HAPIH/JRDŽ stvarno očekuje?
   → Istraži ePoljoprivreda.mps.hr API dokumentaciju.
   → Ako imaju vlastiti XML format — dodaj ?format=xml parametar.

---

## Ažuriraj FENIX_STATUS.md

```
### Institutional Access (NOVO)
- InstitutionalAccessToken model (scope, token, audit) — DONE
- HAPIH endpoint: evidencija lijekova EU Reg 2019/6 — DONE
- JRDŽ endpoint: kretanje životinja — DONE
- Sanitarna inspekcija: blokade mlijeka — DONE
- VetIS: kompletna vet. knjiga — DONE
- Farmer UI: kreira/opoziva/regenerira tokene — DONE
- posalji_upute_instituciji() helper — DONE
```

## Definicija DONE
- [ ] InstitutionalAccessToken model i migracija
- [ ] _get_institutional_token() auth helper
- [ ] 4 read-only endpointa (hapih, jrdz, sanitarna, vetis)
- [ ] URL registracija
- [ ] institutional_tokens view (farmer UI)
- [ ] Template za upravljanje tokenima
- [ ] Test token za OPG Kruljac, curl test prolazi
- [ ] django check: 0 grešaka
- [ ] /tmp/institutional_access_done.txt
