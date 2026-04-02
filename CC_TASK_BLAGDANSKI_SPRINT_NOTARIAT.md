# CC_TASK: Bilježnik + Odvjetnik — Blagdanski Sprint
**Datum:** 03.04.2026. | **Rok:** 14.04.2026. (dan prije go-live)
**Vođa:** Sonnet | **Izvršava:** CC Code
**Cilj:** Demo spreman za Šimašeka i odvjetnika post-Uskrs (22.04.+)

---

## OBVEZNO PRIJE PISANJA KODA
```bash
grep -n "class Appointment\|class ClientDossier\|class BookingService" appointments/models.py
grep -n "class ArhivaEntry\|class Document" documents/models.py
grep -n "hourly_rate\|is_billable\|project" worktime/models.py | head -20
grep -n "project" invoicing/models.py | head -10
```

---

## SPRINT 1 — CroValidator API (03.-04.04., ~12h)

### 1.1 IBAN puni algoritam
Lokacija: `core/oib_validator.py` — dodati ispod postojećeg koda

```python
def validate_iban(iban: str) -> bool:
    """ISO 13616 MOD 97 validacija IBAN-a."""
    iban = iban.strip().replace(' ', '').upper()
    if len(iban) < 15 or len(iban) > 34:
        return False
    # Premjesti prvih 4 znaka na kraj
    rearranged = iban[4:] + iban[:4]
    # Zamijeni slova s brojevima (A=10, B=11, ...)
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
```

### 1.2 MBS validator (Matični broj subjekta)
```python
def validate_mbs(mbs: str) -> bool:
    """MBS: 8 znamenki."""
    mbs = mbs.strip()
    return bool(mbs and len(mbs) == 8 and mbs.isdigit())
```

### 1.3 API endpoint
Lokacija: novi `core/views_validate.py`

```python
# POST /api/v1/validate/
# Body: {"oib": "...", "iban": "...", "mbs": "..."}
# Response: {"oib": {"valid": true}, "iban": {"valid": false, "error": "..."}}

@csrf_exempt
@require_POST
def api_validate(request):
    import json
    from core.oib_validator import validate_oib_hr, validate_hr_iban, validate_mbs
    
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    result = {}
    
    if 'oib' in data:
        oib = str(data['oib']).strip()
        valid = validate_oib_hr(oib)
        result['oib'] = {
            'valid': valid,
            'value': oib,
            'error': None if valid else 'OIB nije valjan (modulo 11 provjera)'
        }
    
    if 'iban' in data:
        iban = str(data['iban']).strip()
        valid = validate_hr_iban(iban) if iban.upper().startswith('HR') else validate_iban(iban)
        result['iban'] = {
            'valid': valid,
            'value': iban,
            'error': None if valid else 'IBAN nije valjan (MOD 97 provjera)'
        }
    
    if 'mbs' in data:
        mbs = str(data['mbs']).strip()
        valid = validate_mbs(mbs)
        result['mbs'] = {
            'valid': valid,
            'value': mbs,
            'error': None if valid else 'MBS mora imati 8 znamenki'
        }
    
    return JsonResponse(result)
```

URL: `path('api/v1/validate/', views_validate.api_validate, name='api_validate')` u core/urls.py

### 1.4 Test
```bash
curl -X POST http://localhost:8000/api/v1/validate/ \
  -H "Content-Type: application/json" \
  -d '{"oib":"37590751921","iban":"HR1210010051863000160"}'
# Očekivano: {"oib":{"valid":true},"iban":{"valid":true}}
```

---

## SPRINT 2 — 10 Bilježničkih predložaka (04.-05.04., ~16h)

Lokacija: novi `notariat/` Django app ili `documents/templates_notariat.py`

WeasyPrint PDF za svaki predložak. Forma → validacija → PDF preview → print/download.

### Predlošci (po prioritetu):

**1. Opunomoćenje (punomoć)** — najčešće, 2-3x dnevno
```
Polja: vlastodavac_ime, vlastodavac_oib, opunomocenik_ime, 
       opunomocenik_oib, opseg_ovlasti (textarea), trajanje, datum
URL: /notariat/predlosci/punomoc/
```

**2. Osnivački akt j.d.o.o.** — jednostavno d.o.o., kapital 1 EUR
```
Polja: osnivac_oib, tvrtka_naziv, sjediste, temeljni_kapital,
       djelatnost_nkd (dropdown iz NKD 331), direktor_oib
URL: /notariat/predlosci/osnivanje-jdoo/
```

**3. Osnivački akt d.o.o.** — standardno
```
Kao j.d.o.o. + više osnivača (dynamic formset), kapital min 2.500 EUR
```

**4. Ugovor o kupoprodaji nekretnine** — najvažniji, najveće tarife
```
Polja: prodavatelj_oib, kupac_oib, adresa_nekretnine,
       katastarska_opcina, kat_cestica, zk_ulozak, povrsina_m2,
       cijena_eur, rok_isplate, nacin_placanja
```

**5. Zadužnica**
```
Polja: duznik_oib, duznik_adresa, vjerovnik_oib, 
       iznos_eur, rok_placanja, zakonska_kamata_bool
```

**6. Bjanko zadužnica**
```
Kao zadužnica + max_iznos_eur, trajanje_ovlastenja_god
```

**7. Ugovor o darovanju**
```
Polja: darovatelj_oib, obdarenik_oib, predmet_darovanja,
       procjena_vrijednosti, uvjeti (textarea, blank=True)
```

**8. Suglasnost za putovanje maloljetnika**
```
Polja: dijete_ime, dijete_datum_rod, roditelj1_oib, roditelj2_oib,
       destinacija, pratnja_ime, pratnja_oib, datum_od, datum_do
NAPOMENA: GDPR posebna kategorija — roditeljski potpis obavezan
```

**9. Izjava o prihvatu nasljedstva**
```
Polja: nasljednik_oib, ostavitelj_ime, datum_smrti, 
       imovina_opis (textarea), udio_postotak
```

**10. Ugovor o doživotnom uzdržavanju**
```
Polja: primatelj_oib, davatelj_oib, imovina (textarea),
       obveze_davatelja (textarea), raskidni_uvjeti (textarea)
```

### PDF template (WeasyPrint):
```python
# documents/management/commands/generate_notariat_pdf.py
# Svaki predložak ima: header s grbom HR, tijelo s popunjenim podacima,
# footer "Ovaj dokument pripremljen je u LIMIT Connect sustavu.
#         Za pravnu valjanost potrebna je ovjera javnog bilježnika."
```

---

## SPRINT 3 — Odvjetnički dashboard (06.-07.04., ~12h)

### Model PravniPredmet (novo, 1 migracija)
```python
# pravnik/models.py
class PravniPredmet(models.Model):
    company      = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    klijent      = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL, null=True)
    naziv        = models.CharField(max_length=300)  # "Horvat vs. Marković"
    vrsta        = models.CharField(choices=[
        ('parnica','Parnični postupak'),
        ('ovrha','Ovršni postupak'),
        ('ugovor','Izrada ugovora'),
        ('savjet','Pravni savjet'),
        ('nekretnina','Promet nekretnina'),
        ('osnivanje','Osnivanje d.o.o.'),
        ('ostalo','Ostalo'),
    ])
    status       = models.CharField(choices=[
        ('aktivan','Aktivan'),('zatvoren','Zatvoren'),('arhiva','Arhiva')
    ], default='aktivan')
    satnica_eur  = models.DecimalField(max_digits=8, decimal_places=2, default=100)
    datum_otvaranja = models.DateField(auto_now_add=True)
    rok          = models.DateField(null=True, blank=True)
    napomena     = models.TextField(blank=True)
    objects      = CompanyManager()
```

### Dashboard /pravnik/
- Lista aktivnih predmeta
- Ukupno billable sati ovaj mjesec
- Predmeti s rokovima u sljedećih 7 dana (alarm)
- Brzi unos "Novi predmet"

### Integracija s postojećim:
- worktime/ → TimeEntry.project = PravniPredmet (billable sati)
- appointments/ → ClientDossier.linked_predmet
- documents/ → ArhivaEntry.predmet (spis predmeta)
- invoicing/ → Invoice.project = PravniPredmet (faktura po predmetu)

---

## SPRINT 4 — Tarifa kalkulator + Bilježnik profil (07.04., ~8h)

### Tarifa kalkulator
```python
# notariat/tarifa.py
# Zakon o javnobilježničkim pristojbama (NN 115/12)

TARIFE = {
    'opunomocenje':           {'osnovna': 10.00, 'pdv': True},
    'osnivanje_jdoo':         {'osnovna': 50.00, 'pdv': True},
    'osnivanje_doo':          {'osnovna': 100.00, 'pdv': True},
    'kupoprodaja_nekretnine': {
        'do_10000':   16.84,
        'do_50000':   33.63,
        'do_100000':  67.26,
        'do_500000': 134.52,
        'nad_500000': 201.78,
        'pdv': True
    },
    'zaduznica': {
        'postotak': 0.001,  # 1‰ od iznosa
        'minimum': 10.00,
        'maximum': 200.00,
        'pdv': True
    },
}

def izracunaj_tarifu(vrsta: str, vrijednost_eur: float = 0) -> dict:
    """Vraca: {'nagrada': EUR, 'pristojba': EUR, 'pdv': EUR, 'ukupno': EUR}"""
```

### "Bilježnik" profil u onboardingu
- Novi business_type u SubscriptionPlan: `'biljeznik'`
- Modules: notariat, appointments, invoicing, documents, partners
- Sidebar: Predlošci | Termini | Klijenti | Arhiva | Tarifa | Fakture

---

## COMMIT FORMAT
```
feat(notariat): biljeznicki + odvjetnicki modul — blagdanski sprint

- CroValidator API: /api/v1/validate/ (OIB+IBAN+MBS)
- IBAN ISO 13616 MOD 97 validacija
- 10 WeasyPrint predložaka (opunomocenje, osnivanje, kupoprodaja...)
- PravniPredmet model (1 migracija)
- Odvjetnički dashboard (integracija worktime+appointments+docs)
- Tarifa kalkulator (ZJBPristojbe)
- 'biljeznik' i 'odvjetnik' profil u onboardingu
```

## MIGRACIJE
```bash
venv/bin/python manage.py makemigrations pravnik --name pravni_predmet
venv/bin/python manage.py migrate
```

## DEPLOY REDOSLIJED
1. CroValidator API (nema migracije) → odmah deploy
2. WeasyPrint predlošci (nema migracije) → deploy
3. PravniPredmet migracija → deploy + migrate
4. Dashboard + tarifa → deploy
5. Systemctl restart gunicorn-fina

---
*Cilj: Demo spreman 14.04. za Šimašeka i odvjetnike post-Uskrs*
*Šimašek: toplim kontakt, bivši klijent potrošnog materijala, Osijek*
