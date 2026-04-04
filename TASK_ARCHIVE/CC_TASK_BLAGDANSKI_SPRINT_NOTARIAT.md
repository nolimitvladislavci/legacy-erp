# CC_TASK: Bilježnik + Odvjetnik + Dimnjačar — UBRZANI Sprint
**Datum:** 03.04.2026. | **Rok:** 10.04.2026. (UBRZANO — 5 dana ranije)
**Vođa:** Sonnet | **Izvršava:** CC Code
**Cilj:** Demo spreman za Šimašeka + odvjetnika + dimnjačarski pilot PRE go-live 15.04.

---

## ZAŠTO SPAJAMO SVA TRI

Sva tri profila dijele ISTI kostur:
```
WeasyPrint PDF isprava  ← ZAJEDNIČKO (jedan engine, razni predlošci)
CroValidator API        ← ZAJEDNIČKO (OIB/IBAN/MBS za sve)
Arhiviranje (ZOR)       ← ZAJEDNIČKO (ArhivaEntry + integrity_hash)
BORG dispatch           ← ZAJEDNIČKO (odvjetnik terenska posjeta = dimnjačar terenska posjeta)
Fiskalizacija POS       ← ZAJEDNIČKO (naplata na licu mjesta)
```

Dimnjačar nije poseban projekt — on je **BORG dispatch + bilježnički PDF** u jednom.
Odvjetnik nije poseban projekt — on je **BORG dispatch + notariat predlošci** u jednom.

---

## OBVEZNO PRIJE PISANJA KODA
```bash
grep -n "class Appointment\|class ClientDossier" appointments/models.py
grep -n "class ArhivaEntry\|integrity_hash" documents/models.py
grep -n "hourly_rate\|is_billable\|project" worktime/models.py | head -20
grep -n "class WorkOrder\|class CardActivity" borg_ops/models.py | head -10
grep -n "class WeasyPrint\|def generate_pdf" documents/views.py | head -10
ls documents/templates/documents/
```

---

## SPRINT 0 — CroValidator API (DAN 1 — DANAS)
**Rok:** 03.04. do ponoći | Nema migracije → deploy odmah

### 0.1 Lokacija: `core/oib_validator.py` — dodati na kraj

```python
def validate_iban(iban: str) -> bool:
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
    iban = iban.strip().replace(' ', '').upper()
    if not iban.startswith('HR') or len(iban) != 21:
        return False
    return validate_iban(iban)

def validate_mbs(mbs: str) -> bool:
    mbs = mbs.strip()
    return bool(mbs and len(mbs) == 8 and mbs.isdigit())
```

### 0.2 Novi fajl: `core/views_validate.py`

```python
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from core.oib_validator import validate_oib_hr, validate_hr_iban, validate_iban, validate_mbs
import json

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
            'error': None if valid else 'MBS mora imati 8 znamenki'}
    return JsonResponse(result)
```

### 0.3 URL u `core/urls.py`:
```python
path('api/v1/validate/', views_validate.api_validate, name='api_validate'),
```

### 0.4 Test:
```bash
curl -X POST https://limit-connect.com/api/v1/validate/ \
  -H "Content-Type: application/json" \
  -d '{"oib":"37590751921","iban":"HR1210010051863000160"}'
# Očekivano: {"oib":{"valid":true},"iban":{"valid":true}}
```

---

## SPRINT 1 — Notariat modul + Dimnjačar (DAN 1-3)
**Rok:** 05.04. | **App:** `notariat/` (nova Django app)

### 1.1 Modeli (1 migracija)

```python
# notariat/models.py

from django.db import models
from core.models import CompanyManager

class NotariatPredlozak(models.Model):
    """Bilježnički i odvjetnički predlošci dokumenata."""
    VRSTE = [
        # BILJEŽNIČKI
        ('punomoc',          'Opunomoćenje (punomoć)'),
        ('osnivanje_jdoo',   'Osnivački akt j.d.o.o.'),
        ('osnivanje_doo',    'Osnivački akt d.o.o.'),
        ('kupoprodaja_nekr', 'Ugovor o kupoprodaji nekretnine'),
        ('zaduznica',        'Zadužnica'),
        ('bjanko_zaduznica', 'Bjanko zadužnica'),
        ('darovanje',        'Ugovor o darovanju'),
        ('maloljetnik_put',  'Suglasnost za putovanje maloljetnika'),
        ('nasljedstvo',      'Izjava o prihvatu nasljedstva'),
        ('dozivotno_uzdrz',  'Ugovor o doživotnom uzdržavanju'),
        # ODVJETNIČKI
        ('pravni_savjet',    'Ugovor o pravnom savjetovanju'),
        ('tuzba',            'Prijedlog tužbe'),
        # DIMNJAČARSKI
        ('potvrda_dimnjak',  'Potvrda o ispravnosti dimnjaka'),
        ('nalaz_dimnjak',    'Nalaz i mišljenje dimnjačara'),
        ('plan_obilasku',    'Godišnji plan obilazaka'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    vrsta   = models.CharField(max_length=30, choices=VRSTE)
    naslov  = models.CharField(max_length=200)
    aktivan = models.BooleanField(default=True)
    objects = CompanyManager()

    class Meta:
        unique_together = ['company', 'vrsta']


class PravniPredmet(models.Model):
    """Odvjetnički predmet / dosje."""
    VRSTE = [
        ('parnica',    'Parnični postupak'),
        ('ovrha',      'Ovršni postupak'),
        ('ugovor',     'Izrada ugovora'),
        ('savjet',     'Pravni savjet'),
        ('nekretnina', 'Promet nekretnina'),
        ('osnivanje',  'Osnivanje d.o.o./obrta'),
        ('ostalo',     'Ostalo'),
    ]
    STATUS = [
        ('aktivan',  'Aktivan'),
        ('zatvoren', 'Zatvoren'),
        ('arhiva',   'Arhiva'),
    ]
    company          = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    klijent          = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL,
                                         null=True, blank=True)
    naziv            = models.CharField(max_length=300)
    vrsta            = models.CharField(max_length=20, choices=VRSTE)
    status           = models.CharField(max_length=20, choices=STATUS, default='aktivan')
    satnica_eur      = models.DecimalField(max_digits=8, decimal_places=2, default=100.00)
    datum_otvaranja  = models.DateField(auto_now_add=True)
    rok              = models.DateField(null=True, blank=True)
    napomena         = models.TextField(blank=True)
    objects          = CompanyManager()

    class Meta:
        ordering = ['-datum_otvaranja']


class DimnjacarskaInspekcija(models.Model):
    """Evidencija dimnjačarskog pregleda — zakon NN 103/15."""
    STATUS = [
        ('ispravan',    'Dimnjak ispravan'),
        ('uvjetno',     'Uvjetno ispravan — potrebni popravci'),
        ('neispravan',  'Dimnjak neispravan — zabrana korištenja'),
    ]
    company          = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    klijent          = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL,
                                         null=True, blank=True)
    adresa           = models.CharField(max_length=300)
    kat_cestica      = models.CharField(max_length=50, blank=True)
    broj_dimnjaka    = models.CharField(max_length=30)
    vrsta_goriva     = models.CharField(max_length=100, blank=True)
    datum_pregleda   = models.DateField()
    status_dimnjaka  = models.CharField(max_length=20, choices=STATUS)
    opis_nalaza      = models.TextField(blank=True)
    preporuke        = models.TextField(blank=True)
    dimnjačar        = models.ForeignKey('employees.EmployeeProfile',
                                          on_delete=models.SET_NULL, null=True, blank=True)
    sljedeci_pregled = models.DateField(null=True, blank=True)
    pdf_sha256       = models.CharField(max_length=64, blank=True)
    objects          = CompanyManager()

    class Meta:
        ordering = ['-datum_pregleda']
        verbose_name = 'Dimnjačarska inspekcija'
```

### 1.2 Migracija:
```bash
venv/bin/python manage.py makemigrations notariat --name notariat_dimnjacari_pravni
venv/bin/python manage.py migrate
```

### 1.3 WeasyPrint PDF — Potvrda o ispravnosti dimnjaka

```python
# notariat/pdf_generators.py
# PROVJERI PRVO: kako je implementiran WeasyPrint u documents/views.py
# Koristi isti pattern, ne izmišljaj iznova

def generiraj_potvrdu_dimnjaka(inspekcija_id: int) -> bytes:
    """
    Generira PDF: Potvrda o ispravnosti dimnjaka
    Zakonska osnova: Zakon o obavljanju dimnjačarskih poslova NN 103/15
    Format: A4, HR grb u headeru, potpis dimnjačara, pečat tvrtke
    """
    # Učitaj DimnjacarskaInspekcija objekt
    # Renderaj HTML predložak
    # WeasyPrint → bytes
    # Izračunaj SHA-256 → spremi u inspekcija.pdf_sha256
    # Spremi u ArhivaEntry (integracija s Arhivom)
    pass
```

Template: `notariat/templates/notariat/potvrda_dimnjaka.html`
- Header: naziv tvrtke, logo, "Potvrda o ispravnosti dimnjaka"
- Zakonska osnova: NN 103/15, čl. X
- Tijelo: adresa, katastarska čestica, broj dimnjaka, datum, nalaz, status
- Footer: "Ovaj dokument je generiran u LIMIT Connect sustavu. Valjan samo s potpisom ovlaštenog dimnjačara."
- SHA-256 hash u footeru (integrity)

### 1.4 WeasyPrint PDF — 5 prioritetnih bilježničkih predložaka

Isti pattern kao dimnjačar. Prioritet redoslijed:
1. `punomoc` — najčešće (2-3x/dan u uredu)
2. `osnivanje_jdoo` — AI Wizard ulaz
3. `kupoprodaja_nekretnine` — najveće tarife
4. `zaduznica`
5. `maloljetnik_put` — GDPR posebna kategorija

Svaki predložak: forma → CroValidator API → preview → PDF download.

---

## SPRINT 2 — Odvjetnički dashboard (DAN 3-4)
**Rok:** 07.04. | Integracija s postojećim modulima

### 2.1 Views i URLs

```python
# notariat/views.py

@login_required
def pravnik_dashboard(request):
    """
    /notariat/pravnik/
    - Lista aktivnih PravniPredmet (company scope)
    - Billable sati ovaj mjesec (TimeEntry.project=predmet, is_billable=True)
    - Predmeti s rokovima u sljedećih 7 dana
    - Brzi unos novog predmeta
    """
    predmeti = PravniPredmet.objects.filter(status='aktivan')
    pred_s_rokom = predmeti.filter(
        rok__gte=date.today(),
        rok__lte=date.today() + timedelta(days=7)
    )
    # Billable sati iz worktime
    # ... integracija
    return render(request, 'notariat/pravnik_dashboard.html', {...})

@login_required
def dimnjačar_dashboard(request):
    """
    /notariat/dimnjacari/
    - Pregled svih inspekcija po statusu (ispravan/uvjetno/neispravan)
    - Sljedeći pregledi (30 dana)
    - Brzi unos inspekcije
    - Generiranje PDF potvrde
    """
    pass
```

### 2.2 Integracije (PROVJERI modele PRVO):

```bash
# Provjeri prije pisanja koda:
grep -n "class TimeEntry\|project\|is_billable" worktime/models.py
grep -n "class ClientDossier\|linked" appointments/models.py
grep -n "class ArhivaEntry\|document_type" documents/models.py
```

Integracija:
- `worktime.TimeEntry.project_id` → `PravniPredmet.id` (billable sati)
- `appointments.ClientDossier` → `linked_predmet = FK(PravniPredmet)`
- `documents.ArhivaEntry.document_type = 'notariat'` → spis predmeta
- `invoicing.Invoice` → `project = PravniPredmet` (faktura po predmetu)

---

## SPRINT 3 — Tarifa kalkulator + AI Wizard (DAN 4-5)
**Rok:** 09.04.

### 3.1 Tarifa kalkulator

```python
# notariat/tarifa.py
# Zakon o javnobilježničkim pristojbama (NN 115/12)

TARIFE = {
    'punomoc':          {'osnovna': 10.00, 'pdv': True},
    'osnivanje_jdoo':   {'osnovna': 50.00, 'pdv': True},
    'osnivanje_doo':    {'osnovna': 100.00, 'pdv': True},
    'kupoprodaja_nekretnine': {
        'razredi': [
            (10_000,   16.84),
            (50_000,   33.63),
            (100_000,  67.26),
            (500_000, 134.52),
            (None,    201.78),
        ],
        'pdv': True
    },
    'zaduznica': {
        'postotak': 0.001,
        'minimum': 10.00,
        'maximum': 200.00,
        'pdv': True
    },
    # DIMNJAČAR (paušal prema ZJBPristojbe adaptiran)
    'pregled_dimnjaka': {'osnovna': 15.00, 'pdv': True},
    'potvrda_dimnjaka': {'osnovna': 5.00, 'pdv': True},
}

def izracunaj_tarifu(vrsta: str, vrijednost_eur: float = 0) -> dict:
    """Vraca: {'nagrada': EUR, 'pristojba': EUR, 'pdv': EUR, 'ukupno': EUR}"""
```

### 3.2 AI Wizard za otvaranje firme (Haiku)

```python
# notariat/views_wizard.py
# Haiku vodi korisnika kroz osnivanje korak po korak
# Na kraju: popunjeni predložak + NKD preporuka + tarifa

WIZARD_PROMPT = """
Ti si asistent za otvaranje tvrtke u Hrvatskoj.
Korisnik odabire vrstu: j.d.o.o., d.o.o., obrt, OPG, udruga.
Postavljaj JEDNO pitanje najednom. Kada imaš sve podatke,
vrati JSON s populated_fields.
Na osnovi opisa djelatnosti predloži NKD kod (poznaješ 331 NKD kodova).
Jezik: hrvatski. Ton: topao, konkretan, bez žargona.
"""
```

### 3.3 Profili u onboardingu:
- `business_type = 'biljeznik'` → modules: notariat, appointments, invoicing, documents, partners
- `business_type = 'odvjetnik'` → modules: pravnik dashboard, worktime (billable), invoicing
- `business_type = 'dimnjacari'` → modules: dimnjačar dashboard, BORG dispatch, POS mobilni, dokumenti

---

## DIMNJAČAR ↔ BORG INTEGRACIJA (BONUS — ako ostane vremena)

```python
# Dimnjačarska inspekcija kao BORG WorkOrder
# WorkOrder.category = 'dimnjacarski_pregled'
# WorkOrder.location = adresa objekta
# GPS dispatch → najbliži ovlašteni dimnjačar
# Po završetku: auto-generira DimnjacarskaInspekcija + PDF potvrda

# Periodični plan obilazaka → Celery beat
# Svaki objekt: pregled 1-2x godišnje (zakon)
# 30 dana prije → WhatsApp obavijest vlasniku
```

---

## DEPLOY REDOSLIJED

```bash
# Dan 1: Sprint 0 (bez migracije)
git add core/oib_validator.py core/views_validate.py core/urls.py
git commit -m "feat(core): CroValidator API — OIB+IBAN+MBS validacija"
systemctl restart gunicorn-fina

# Dan 2-3: Sprint 1 (s migracijom)
venv/bin/python manage.py makemigrations notariat
venv/bin/python manage.py migrate
git commit -m "feat(notariat): modeli + dimnjačar + bilježnik predlošci WeasyPrint"
systemctl restart gunicorn-fina

# Dan 4: Sprint 2
git commit -m "feat(notariat): odvjetnički dashboard + integracija worktime/docs"
systemctl restart gunicorn-fina

# Dan 5: Sprint 3
git commit -m "feat(notariat): tarifa kalkulator + AI Wizard + profili"
systemctl restart gunicorn-fina
```

---

## STATUS PRAĆENJE

| Sprint | Sadržaj | Rok | Status |
|--------|---------|-----|--------|
| S0 | CroValidator API | 03.04. | ⏳ ODMAH |
| S1a | DimnjacarskaInspekcija model + migracija | 04.04. | ⏳ |
| S1b | PDF Potvrda dimnjaka (WeasyPrint) | 04.04. | ⏳ |
| S1c | 5 bilježničkih predložaka | 05.04. | ⏳ |
| S2a | PravniPredmet model | 05.04. | ⏳ |
| S2b | Odvjetnički dashboard | 06.04. | ⏳ |
| S2c | Dimnjačarski dashboard | 07.04. | ⏳ |
| S3a | Tarifa kalkulator | 08.04. | ⏳ |
| S3b | AI Wizard (Haiku) | 09.04. | ⏳ |
| S3c | 3 profila u onboardingu | 09.04. | ⏳ |
| BONUS | BORG dispatch integracija | 10.04. | ⏳ |

---

## PILOT KORISNICI KOJI ČEKAJU

| Korisnik | Profil | Kontakt | Napomena |
|----------|--------|---------|----------|
| Šimašek | Bilježnik | Osijek, toplim kontakt | Demo 22.04. post-Uskrs |
| TBD odvjetnik | Odvjetnik | Osijek | Post-Uskrs |
| TBD dimnjačar | Dimnjačar | Slavonija | 800 obrta HR, 1. pilot |

---
*Ivan: "rezervoari su puni — idemo prije roka"*
*Novi rok: 10.04. (5 dana ranije od originalnih 14.04.)*
*Geometrija: bilježnik + odvjetnik + dimnjačar = isti engine, tri lica*
