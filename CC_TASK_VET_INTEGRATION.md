# CC Task — Vet Integration: 3 razine (WhatsApp link + Portal + Robot API)

## Pročitaj prvo — OBAVEZNO
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
sed -n '1,30p' /var/www/fina-connect/accounts/models.py          # ROLE_CHOICES
cat /var/www/fina-connect/traceability/models.py                   # UUID public token pattern
sed -n '235,280p' /var/www/fina-connect/propter/views.py           # X-API-Key pattern
cat /var/www/fina-connect/livestock/models.py                      # HealthRecord, Livestock
grep -n "karencija_do\|is_blocked\|blocked_until" \
  /var/www/fina-connect/livestock/models.py \
  /var/www/fina-connect/inventory/models.py 2>/dev/null | head -20
cat /var/www/fina-connect/livestock/urls.py
```

## Kontekst — zašto ovaj task

EU Regulation 2019/6 zahtijeva elektroničku evidenciju antimikrobnih lijekova.
Veterinar je vanjska osoba — obilazi više farmi. Farmer vidi tretman odmah.
POS automatski blokira mlijeko u karenciji (CC_TASK_LIVESTOCK_V3 — Dio A).

**Tri patterne nasljeđujemo direktno:**
- UUID public token → `traceability.ProductTrace.qr_code` (bez logina)
- X-API-Key bez sesije → `propter.api_create_otpremnica`
- Multi-farm vet → novi `VetProfile` (UserProfile.company je FK, ne može M2M)

---

## MODEL SLOJ — čitaj STVARNA polja, ne pretpostavljaj

```bash
# Provjeri ROLE_CHOICES u accounts/models.py
sed -n '7,18p' /var/www/fina-connect/accounts/models.py

# Provjeri postoji li VetProfile već
grep -rn "VetProfile\|vet_profile\|vet_token" /var/www/fina-connect \
  --include="*.py" | grep -v venv | grep -v __pycache__ | head -5
```

### M1: Dodaj 'vet' u ROLE_CHOICES
```python
# accounts/models.py, unutar ROLE_CHOICES liste, dodaj:
('vet', _('Veterinar')),
```

### M2: VetProfile model — dodaj u livestock/models.py
```python
import uuid as _uuid

class VetProfile(models.Model):
    """
    Veterinar koji obilazi jednu ili više farmi.
    ARHITEKTURNA NAPOMENA: veterinar = vanjska osoba, više farmi.
    UserProfile.company je FK (jedna firma) — zato koristimo M2M ovdje.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='vet_profile', null=True, blank=True,
        help_text='Popunjeno za Razinu 2 (portal login). Prazno za Razinu 1 (link only).'
    )
    ime = models.CharField(max_length=100, verbose_name='Ime i prezime')
    licenca_broj = models.CharField(max_length=50, blank=True,
                                     verbose_name='Broj veterinarske licence')
    telefon = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    # Farme koje ovaj vet obilazi (M2M — ključna razlika od UserProfile)
    farme = models.ManyToManyField(
        'companies.Company',
        related_name='vets',
        blank=True,
        verbose_name='Farme (OPG-ovi)',
    )

    # Razina 1: jednokratni token za WhatsApp link (bez logina)
    vet_token = models.UUIDField(
        default=_uuid.uuid4, unique=True,
        verbose_name='Vet token (za WhatsApp link)',
        help_text='limit-connect.com/vet/{vet_token}/{livestock_pk}/'
    )
    token_aktivan = models.BooleanField(default=True)
    token_istice = models.DateField(null=True, blank=True,
                                     verbose_name='Token ističe (opcionalno)')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'livestock_vet_profile'
        verbose_name = 'Veterinarski profil'
        verbose_name_plural = 'Veterinarski profili'

    def __str__(self):
        return f'{self.ime} ({self.licenca_broj or "bez licence"})'

    @property
    def token_validan(self):
        from django.utils import timezone
        if not self.token_aktivan:
            return False
        if self.token_istice and self.token_istice < timezone.now().date():
            return False
        return True

    def generiraj_link(self, livestock_pk, base_url='https://limit-connect.com'):
        return f'{base_url}/vet/{self.vet_token}/{livestock_pk}/'
```

### M3: Migracije
```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations livestock --name="add_vet_profile"
venv/bin/python manage.py makemigrations accounts --name="add_vet_role"
venv/bin/python manage.py migrate
venv/bin/python manage.py check
```

---

## RAZINA 1 — WhatsApp link (bez logina, odmah)

### R1-V: View za vet link
```python
# livestock/views.py — dodaj:

def vet_treatment_form(request, vet_token, livestock_pk):
    """
    Javna stranica — veterinar unosi tretman bez logina.
    URL: /vet/{uuid}/{pk}/
    Autentikacija: UUID token koji farmer šalje vetu na WhatsApp.
    """
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages

    vet = get_object_or_404(VetProfile, vet_token=vet_token, token_aktivan=True)

    if not vet.token_validan:
        return render(request, 'livestock/vet_token_expired.html')

    animal = get_object_or_404(Livestock, pk=livestock_pk,
                                company__in=vet.farme.all())

    if request.method == 'POST':
        # Spremi HealthRecord
        from django.utils import timezone
        import datetime
        karencija_dani = int(request.POST.get('karencija_dani', 0) or 0)

        # EU Reg 2019/6: ekološki uzgoj = 2x karencija
        if animal.is_organic and karencija_dani > 0:
            karencija_dani = karencija_dani * 2

        karencija_do = None
        if karencija_dani > 0:
            karencija_do = timezone.now().date() + datetime.timedelta(days=karencija_dani)

        hr = HealthRecord.objects.create(
            animal=animal,
            datum=timezone.now().date(),
            tip=request.POST.get('tip', 'tretman'),
            opis=request.POST.get('opis', ''),
            veterinar=vet.ime,
            lijek=request.POST.get('lijek', ''),
            kolicina=request.POST.get('kolicina', ''),
            karencija_do=karencija_do,
        )

        # WhatsApp obavijest farmeru ODMAH
        _notify_farmer_after_treatment(animal, hr, vet)

        return render(request, 'livestock/vet_treatment_success.html', {
            'animal': animal, 'record': hr, 'vet': vet,
        })

    # Dohvati zadnjih 5 tretmana za context
    zadnji = HealthRecord.objects.filter(animal=animal).order_by('-datum')[:5]

    return render(request, 'livestock/vet_treatment_form.html', {
        'animal': animal,
        'vet': vet,
        'zadnji_tretmani': zadnji,
        'je_organski': animal.is_organic,
    })


def _notify_farmer_after_treatment(animal, health_record, vet):
    """Šalje WhatsApp farmeru odmah nakon unosa tretmana."""
    from core.whatsapp import send_text
    from accounts.models import UserProfile

    admin = UserProfile.objects.filter(
        company=animal.company, role='company_admin'
    ).first()
    if not admin:
        return

    phone = getattr(admin.user, 'phone', '') or ''
    if not phone:
        return

    karencija_info = ''
    if health_record.karencija_do:
        dani = (health_record.karencija_do - __import__('datetime').date.today()).days
        karencija_info = (
            f'\n⚠️ *KARENCIJA: {health_record.karencija_do} '
            f'({dani} dana)*'
            f'\nMlijeko/meso NIJE za prodaju!'
        )
        if animal.is_organic:
            karencija_info += '\n(Ekološki uzgoj: 2× standardna karencija)'

    msg = (
        f'🐄 *Veterinarski tretman — {animal.ear_tag}*'
        f'\n\nVeterinar: {vet.ime}'
        f'\nŽivotinja: {animal.name or animal.ear_tag} ({animal.get_vrsta_display()})'
        f'\nTretman: {health_record.get_tip_display()}'
        f'\nLijek: {health_record.lijek or "—"}'
        f'\nDoza: {health_record.kolicina or "—"}'
        f'{karencija_info}'
    )
    send_text(phone, msg)
```

### R1-URL: Dodaj u livestock/urls.py
```python
path('vet/<uuid:vet_token>/<int:livestock_pk>/', views.vet_treatment_form, name='vet_form'),
```

### R1-WHATSAPP: Helper za slanje linka farmeru
```python
# livestock/views.py ili livestock/services.py:

def posalji_vet_link(vet_profile, livestock_pk, farmer_phone):
    """Farmer klika 'Pozovi veta' — šalje mu WhatsApp link."""
    from core.whatsapp import send_text
    link = vet_profile.generiraj_link(livestock_pk)
    msg = (
        f'🔗 *LIMIT Connect — Vet unos*'
        f'\n\nDr. {vet_profile.ime},'
        f'\nkliknite link za unos tretmana:'
        f'\n{link}'
        f'\n\nLink je jedinstven i siguran.'
    )
    send_text(farmer_phone, msg)
    # Ili odmah na vet telefon:
    if vet_profile.telefon:
        send_text(vet_profile.telefon, msg)
```

### R1-TEMPLATE: livestock/templates/livestock/vet_treatment_form.html
Minimalan, bez logina, mobilan (vet unosi na mobitelu):
```html
{# Minimalan template — radi bez CSS frameworka, čitljiv na mobitelu #}
<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vet unos — {{ animal.ear_tag }}</title>
<style>
  body { font-family: sans-serif; max-width: 500px; margin: 0 auto; padding: 16px; }
  .animal-card { background: #f0f9f0; border: 1px solid #4a7c59; border-radius: 8px; padding: 12px; margin-bottom: 16px; }
  label { display: block; margin: 12px 0 4px; font-weight: bold; font-size: 14px; }
  input, select, textarea { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 16px; box-sizing: border-box; }
  .organic-warning { background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; padding: 10px; margin: 8px 0; font-size: 13px; }
  button[type=submit] { background: #2d6a4f; color: white; border: none; padding: 14px; width: 100%; border-radius: 8px; font-size: 16px; margin-top: 16px; cursor: pointer; }
  .zadnji { margin-top: 24px; border-top: 1px solid #ddd; padding-top: 12px; }
  .zadnji h4 { font-size: 14px; color: #666; }
  .zapis { background: #f9f9f9; border-radius: 6px; padding: 8px; margin: 6px 0; font-size: 13px; }
</style>
</head>
<body>
<div class="animal-card">
  <strong>{{ animal.ear_tag }}</strong>
  {% if animal.name %} — {{ animal.name }}{% endif %}
  <br>{{ animal.get_vrsta_display }} | {{ animal.get_status_display }}
  {% if je_organski %}<br>🌿 <strong>EKOLOŠKI UZGOJ</strong>{% endif %}
</div>

{% if je_organski %}
<div class="organic-warning">
  ⚠️ Ekološki uzgoj: karencija = <strong>2× standardna</strong> (EU Reg 2019/6)
</div>
{% endif %}

<form method="post">
  {% csrf_token %}
  <label>Tip tretmana</label>
  <select name="tip" required>
    <option value="tretman">Tretman / Lijek</option>
    <option value="cijepljenje">Cijepljenje</option>
    <option value="pregled">Pregled</option>
    <option value="bolest">Bolest</option>
    <option value="operacija">Operacija</option>
  </select>

  <label>Lijek / Preparat</label>
  <input type="text" name="lijek" placeholder="npr. Amoksicilin 150 mg/ml" required>

  <label>Doza / Količina</label>
  <input type="text" name="kolicina" placeholder="npr. 10 ml i.m.">

  <label>Karencija (dani) — standardna</label>
  <input type="number" name="karencija_dani" min="0" max="365" value="0"
    {% if je_organski %}
    oninput="document.getElementById('eko_kara').textContent = 'Ekološka: ' + (this.value*2) + ' dana'"
    {% endif %}>
  {% if je_organski %}
  <div style="font-size:13px;color:#856404;margin-top:4px" id="eko_kara">Ekološka: 0 dana</div>
  {% endif %}

  <label>Opis / Napomena</label>
  <textarea name="opis" rows="3" placeholder="Simptomi, nalaz, preporuke..."></textarea>

  <div style="font-size:12px;color:#666;margin-top:8px">
    Dr. {{ vet.ime }} | {{ vet.licenca_broj }}
  </div>

  <button type="submit">💉 Spremi tretman</button>
</form>

{% if zadnji_tretmani %}
<div class="zadnji">
  <h4>Zadnjih 5 tretmana</h4>
  {% for z in zadnji_tretmani %}
  <div class="zapis">
    <strong>{{ z.datum }}</strong> — {{ z.get_tip_display }}
    {% if z.lijek %} | {{ z.lijek }}{% endif %}
    {% if z.karencija_do %} | ⚠️ karencija do {{ z.karencija_do }}{% endif %}
  </div>
  {% endfor %}
</div>
{% endif %}
</body>
</html>
```

---

## RAZINA 2 — Vet Portal (login, vlastiti dashboard)

### R2-V: Vet dashboard view
```python
# livestock/views.py — dodaj:

from django.contrib.auth.decorators import login_required

@login_required
def vet_dashboard(request):
    """
    Vet portal — veterinar vidi sve farme koje obilazi.
    Dostupno samo ako user.profile.role == 'vet'.
    """
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role != 'vet':
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Pristup dozvoljen samo veterinarima.')

    vet = get_object_or_404(VetProfile, user=request.user)
    farme = vet.farme.all().prefetch_related('livestock')

    # Za svaku farmu: broj grla u karenciji, nedavni tretmani
    farme_pregled = []
    for farma in farme:
        from django.utils import timezone
        today = timezone.now().date()
        karencije = HealthRecord.objects.filter(
            animal__company=farma,
            karencija_do__gte=today,
        ).count()
        zadnji = HealthRecord.objects.filter(
            animal__company=farma,
            veterinar=vet.ime,
        ).order_by('-datum')[:3]
        farme_pregled.append({
            'farma': farma,
            'grla': Livestock.objects.filter(company=farma).count(),
            'karencije': karencije,
            'zadnji_tretmani': list(zadnji),
        })

    return render(request, 'livestock/vet_dashboard.html', {
        'vet': vet,
        'farme': farme_pregled,
    })


@login_required
def vet_farm_animals(request, company_pk):
    """Lista grla jedne farme za veta."""
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role != 'vet':
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    vet = get_object_or_404(VetProfile, user=request.user)
    farma = get_object_or_404(
        __import__('companies.models', fromlist=['Company']).Company,
        pk=company_pk
    )
    # Sigurnosna provjera: vet mora imati pristup ovoj farmi
    if not vet.farme.filter(pk=company_pk).exists():
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Nemaš pristup ovoj farmi.')

    grla = Livestock.objects.filter(company=farma, status='aktivno').order_by('ear_tag')
    return render(request, 'livestock/vet_farm_animals.html', {
        'vet': vet, 'farma': farma, 'grla': grla,
    })
```

### R2-URL: Dodaj u livestock/urls.py
```python
path('vet/dashboard/', views.vet_dashboard, name='vet_dashboard'),
path('vet/farma/<int:company_pk>/', views.vet_farm_animals, name='vet_farm_animals'),
```

---

## RAZINA 3 — Robot API za mužnju (bez sesije, API key)

```python
# livestock/views.py — dodaj:

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def api_robot_identify(request):
    """
    POST /livestock/api/robot/identify/
    Header: X-Livestock-Key: {api_key iz VetProfile ili Company settings}

    Robot šalje ear_tag → sustav vraća: smiješ li mužiti?

    Response:
      {"status": "ok", "milk": true}   → muzi normalno
      {"status": "ok", "milk": false,
       "reason": "Karencija do 2026-04-15",
       "days_remaining": 3}             → preskoči, mlijeko u zasebni tank
      {"status": "not_found"}           → nepoznata markica
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    # API Key autentikacija — isti pattern kao propter X-Propter-Key
    api_key = request.headers.get('X-Livestock-Key') or request.POST.get('api_key')
    if not api_key:
        return JsonResponse({'error': 'X-Livestock-Key header obavezan'}, status=401)

    # Pronađi kompaniju po API key
    # Koristimo CompanyModuleConfig ili novi field na Company
    # PROVJERI: postoji li api_key field na Company modelu
    try:
        from companies.models import Company
        # Ako ne postoji dedicated API key na Company,
        # koristi jednostavan hash: sha256(company.oib + 'livestock_robot')
        import hashlib, json
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON required'}, status=400)

        ear_tag = data.get('ear_tag', '').strip()
        if not ear_tag:
            return JsonResponse({'error': 'ear_tag required'}, status=400)

        # Pronađi kompaniju čiji je ključ = sha256(oib + salt)
        # Alternativa: pohrani robot_api_key na Company modelu (preporučeno)
        # Za sada: prođi kroz sve OPG firme (malih je)
        company = None
        for c in Company.objects.filter(business_type='opg', is_active=True):
            expected_key = hashlib.sha256(
                f'{c.oib}:livestock_robot_v1'.encode()
            ).hexdigest()[:32]
            if api_key == expected_key:
                company = c
                break

        if not company:
            return JsonResponse({'error': 'Invalid API key'}, status=403)

        # Pronađi životinju
        try:
            animal = Livestock.objects.get(ear_tag=ear_tag, company=company)
        except Livestock.DoesNotExist:
            return JsonResponse({'status': 'not_found', 'ear_tag': ear_tag})

        # Provjeri karenciju
        from django.utils import timezone
        today = timezone.now().date()

        active_karencija = HealthRecord.objects.filter(
            animal=animal,
            karencija_do__gte=today,
        ).order_by('-karencija_do').first()

        if active_karencija:
            days_remaining = (active_karencija.karencija_do - today).days
            return JsonResponse({
                'status': 'ok',
                'ear_tag': ear_tag,
                'milk': False,
                'reason': f'Karencija — {active_karencija.lijek or "lijek"}',
                'karencija_do': str(active_karencija.karencija_do),
                'days_remaining': days_remaining,
                'action': 'SKIP_OR_SEPARATE_TANK',
            })

        # Normalno — muzi
        return JsonResponse({
            'status': 'ok',
            'ear_tag': ear_tag,
            'milk': True,
            'animal_name': animal.name or '',
            'vrsta': animal.vrsta,
            'avg_daily_milk_l': float(animal.avg_daily_milk_l) if animal.avg_daily_milk_l else None,
        })

    except Exception as e:
        import logging
        logging.getLogger('livestock').error('Robot API error: %s', e)
        return JsonResponse({'error': 'Internal error'}, status=500)


def api_robot_key(request, company_pk):
    """
    Superadmin helper: pokaži robot API key za jednu farmu.
    limit-connect.com/livestock/api/robot/key/{pk}/ (samo superadmin)
    """
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    import hashlib
    from companies.models import Company
    company = get_object_or_404(Company, pk=company_pk)
    key = hashlib.sha256(f'{company.oib}:livestock_robot_v1'.encode()).hexdigest()[:32]
    return JsonResponse({
        'company': company.name,
        'oib': company.oib,
        'robot_api_key': key,
        'usage': f'POST /livestock/api/robot/identify/ Header: X-Livestock-Key: {key}',
        'example': {'ear_tag': 'HR414399935730001'},
    })
```

### R3-URL: Dodaj u livestock/urls.py
```python
path('api/robot/identify/', views.api_robot_identify, name='api_robot_identify'),
path('api/robot/key/<int:company_pk>/', views.api_robot_key, name='api_robot_key'),
```

---

## NOTIFIKACIJSKI CELERY TASK — svako jutro za farmere

```python
# livestock/tasks.py — dodaj:

@shared_task(bind=True)
def morning_farm_briefing(self):
    """
    Svako jutro u 06:30 — svaki farmer dobije WhatsApp briefing:
    - Koliko grla u karenciji
    - Koje krave tele uskoro
    - JRDŽ rokovi koji ističu
    """
    from django.utils import timezone
    from companies.models import Company
    from livestock.models import Livestock, HealthRecord, JRDZRegistration
    from core.whatsapp import send_text
    from accounts.models import UserProfile

    today = timezone.now().date()
    opg_firme = Company.objects.filter(business_type='opg', is_active=True)

    for company in opg_firme:
        admin = UserProfile.objects.filter(
            company=company, role='company_admin'
        ).first()
        if not admin:
            continue
        phone = getattr(admin.user, 'phone', '') or ''
        if not phone:
            continue

        # Karencije
        karencije = HealthRecord.objects.filter(
            animal__company=company, karencija_do__gte=today
        ).count()

        # Teljenja uskoro
        teljenja = Livestock.objects.filter(
            company=company, status='gravidno',
            expected_calving__lte=today + timezone.timedelta(days=7),
            expected_calving__gte=today,
        ).count()

        # JRDŽ rokovi
        try:
            jrdz_hitno = JRDZRegistration.objects.filter(
                company=company, status='pending',
                rok_prijave__lte=today + timezone.timedelta(days=3),
            ).count()
        except Exception:
            jrdz_hitno = 0

        # Šalji samo ako ima nešto za reći
        if not any([karencije, teljenja, jrdz_hitno]):
            continue

        linije = [f'🐄 *{company.name} — Jutarnji izvještaj*\n']
        if karencije:
            linije.append(f'⚠️ {karencije} grla u karenciji (mlijeko/meso NE za prodaju)')
        if teljenja:
            linije.append(f'🐮 {teljenja} krave tele za 7 dana — pripremi boxeve')
        if jrdz_hitno:
            linije.append(f'📋 {jrdz_hitno} JRDŽ prijava ističe za 3 dana!')

        send_text(phone, '\n'.join(linije))
```

```python
# core/settings.py CELERY_BEAT_SCHEDULE dodaj:
'morning-farm-briefing': {
    'task': 'livestock.tasks.morning_farm_briefing',
    'schedule': crontab(hour=6, minute=30),
},
```

---

## PROVJERA I VERIFIKACIJA

```bash
cd /var/www/fina-connect

# 1. Migracije
venv/bin/python manage.py makemigrations livestock --name="add_vet_profile"
venv/bin/python manage.py makemigrations accounts --name="add_vet_role"
venv/bin/python manage.py migrate
venv/bin/python manage.py check

# 2. Kreiraj test vet profil za OPG Kruljac
venv/bin/python manage.py shell -c "
from livestock.models import VetProfile
from companies.models import Company

kruljac = Company.objects.get(name__icontains='Kruljac')
vet, created = VetProfile.objects.get_or_create(
    ime='Dr. Test Veterinar',
    defaults={
        'licenca_broj': 'HR-VET-001',
        'telefon': '0912345678',
        'email': 'vet@test.hr',
    }
)
vet.farme.add(kruljac)
from livestock.models import Livestock
grlo = Livestock.objects.filter(company=kruljac).first()
if grlo:
    link = vet.generiraj_link(grlo.pk)
    print('Vet link:', link)
    print('Token valid:', vet.token_validan)

# Robot API key
import hashlib
key = hashlib.sha256(f'{kruljac.oib}:livestock_robot_v1'.encode()).hexdigest()[:32]
print('Robot API key:', key)
print('Usage: POST /livestock/api/robot/identify/ X-Livestock-Key:', key)
" 2>&1 | grep -v Warning | grep -v Deprecat

# 3. Test robot API
venv/bin/python manage.py shell -c "
import hashlib, json
from companies.models import Company
kruljac = Company.objects.get(name__icontains='Kruljac')
key = hashlib.sha256(f'{kruljac.oib}:livestock_robot_v1'.encode()).hexdigest()[:32]
print('Testiraj s:')
print(f\"curl -X POST https://limit-connect.com/livestock/api/robot/identify/ \\\\\\n  -H 'X-Livestock-Key: {key}' \\\\\\n  -H 'Content-Type: application/json' \\\\\\n  -d '{json.dumps({\'ear_tag\': \'HR414399935730001\'})}'\")
" 2>&1 | grep -v Warning | grep -v Deprecat

# 4. Restart
systemctl restart celery-worker
```

---

## VLASTITI PRIJEDLOZI — CC Code slobodne ruke

Dok čitaš kod, provjeri i predloži:
1. Je li `animal.is_organic` flag sinkroniziran s `Field.is_organic` (parcela)? Krava na bio parceli je bio krava — možda treba automatski postavljati flag.
2. Postoji li `BookOfTreatments` (Knjiga evidencije o liječenju) — EU zakonska obveza? Ako ne → predloži model ili PDF export iz HealthRecord.
3. `VetProfile.farme` M2M — postoji li view za dodavanje nove farme vetu (farmer poziva veta → vet dobiva pristup toj farmi)?

---

## Ažuriraj FENIX_STATUS.md

```
### Vet Integration (NOVO)
- VetProfile model (M2M farme, UUID token) — DONE
- accounts: 'vet' role dodan — DONE
- Razina 1: /vet/{token}/{pk}/ bez logina, WhatsApp link — DONE
- Razina 2: /vet/dashboard/ vet portal (login) — DONE
- Razina 3: /api/robot/identify/ robot API (X-Livestock-Key) — DONE
- EU Reg 2019/6: 2x karencija za eko uzgoj automatski — DONE
- morning_farm_briefing Celery task (06:30) — DONE
```

## Definicija DONE
- [ ] VetProfile model i migracija
- [ ] 'vet' u ROLE_CHOICES
- [ ] /vet/{token}/{pk}/ view — radi bez logina
- [ ] EU 2019/6: karencija 2x ako is_organic automatski
- [ ] WhatsApp odmah nakon unosa tretmana
- [ ] /vet/dashboard/ (login required, role='vet')
- [ ] /livestock/api/robot/identify/ — JSON odgovor milk: true/false
- [ ] morning_farm_briefing Celery task
- [ ] Test vet profil za OPG Kruljac, vet link generiran
- [ ] Robot API curl test prolazi
- [ ] django check: 0 grešaka
- [ ] /tmp/vet_integration_done.txt

---

## ⚠️ ARHITEKTURNA KOREKCIJA — nakon analize Gemini + Sonnet

### Što smo otkrili

`CompanyMembership` već postoji u `accounts/models.py` (linija 155):
```python
class CompanyMembership(models.Model):
    user = models.ForeignKey(User, ...)
    company = models.ForeignKey(Company, ...)
    role = models.CharField(max_length=30, choices=UserProfile.ROLE_CHOICES)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
```

`get_user_company()` već ima session switching:
- `umbrella_as_company` u sesiji
- `impersonated_company_id` za superadmin
- Thread-local fallback

**Zaključak: ne trebamo ExternalAccess ni novi VetProfile M2M.**
Trebamo samo:
1. Dodati `'vet'` u `ROLE_CHOICES`
2. Koristiti `CompanyMembership` za vezivanje veta na više farmi
3. Session switching za "odabir aktivne farme" — isti mehanizam koji umbrella admin već koristi

### Kako CC Code treba implementirati Razinu 2 (korekcija)

**UMJESTO** `VetProfile.farme = ManyToManyField`:

```python
# Vet se dodaje na farmu ovako:
CompanyMembership.objects.create(
    user=vet_user,
    company=opg_kruljac,
    role='vet',
    is_active=True,
)
# Vet na više farmi = više CompanyMembership zapisa

# Vet dashboard — dohvat svih farmi:
memberships = CompanyMembership.objects.filter(
    user=request.user,
    role='vet',
    is_active=True,
).select_related('company')

# Vet odabere farmu → session switching (isti mehanizam kao umbrella):
request.session['active_vet_company'] = company_pk
# get_user_company() treba jedan if blok više:
vet_company_id = request.session.get('active_vet_company')
if vet_company_id:
    membership = CompanyMembership.objects.filter(
        user=request.user, company_id=vet_company_id,
        role='vet', is_active=True
    ).first()
    if membership:
        return membership.company
```

**VetProfile model OSTAJE** ali bez `farme = ManyToManyField`:
```python
class VetProfile(models.Model):
    user = models.OneToOneField(User, ...)  # ostaje
    ime = models.CharField(...)             # ostaje
    licenca_broj = models.CharField(...)    # ostaje
    vet_token = models.UUIDField(...)       # ostaje — za Razinu 1
    token_aktivan = models.BooleanField()   # ostaje

    # UKLONI:
    # farme = models.ManyToManyField(...)  ← zamijenjeno s CompanyMembership
```

`VetProfile.farme` property postaje:
```python
@property
def farme(self):
    """Sve farme ovog veta — čita iz CompanyMembership."""
    from accounts.models import CompanyMembership
    return CompanyMembership.objects.filter(
        user=self.user, role='vet', is_active=True
    ).values_list('company', flat=True)
```

### Što NIJE potrebno graditi iznova

- `get_user_company()` — ne diraj, dodaj samo `active_vet_company` grana
- `CompanyMembership` — ne diraj, samo dodaj role='vet' zapise
- Session switching UI — kopija `umbrella_as_company` mehanizma, promijeni samo labele

### Provjera prije implementacije

```bash
# Potvrdi da CompanyMembership postoji i ima pravo polje
python manage.py shell -c "
from accounts.models import CompanyMembership
print('Fields:', [f.name for f in CompanyMembership._meta.fields])
print('Count:', CompanyMembership.objects.count())
"

# Potvrdi da get_user_company podržava session switching
grep -n 'umbrella_as_company\|active_vet\|session.*company' \
  /var/www/fina-connect/core/company_utils.py
```
