# CC Task — Fitness: simulacija + testovi + WhatsApp izvještaj

## Misija
Fitness modul ima samo Member + MemberCheckIn.
Gemini dodaje nove modele (prati GEMINI_TASK_FITNESS_IMPLEMENT.md).
Ti radiš:
1. Teške testove za sve što postoji i što Gemini doda
2. Simulaciju korištenja s realnim test podacima
3. Screenshot/HTML svake vidljive forme → PDF → WhatsApp 385991908089

## KORAK 0 — Provjeri što Gemini već napravio
```bash
cat /var/www/fina-connect/fitness/models.py
ls /var/www/fina-connect/fitness/
cat /tmp/gemini_fitness_result.txt 2>/dev/null | python3 -m json.tool | head -30
```
Ako Gemini nije završio — radi s onim što ima (Member + MemberCheckIn).
Ako jest — koristi sve nove modele.

## KORAK 1 — Pročitaj OBAVEZNO prije koda
```bash
cat /var/www/fina-connect/fitness/models.py        # stvarna polja
cat /var/www/fina-connect/fitness/views.py         # stvarne view funkcije
cat /var/www/fina-connect/fitness/urls.py          # stvarni URL nazivi
ls /var/www/fina-connect/templates/fitness/        # stvarni templates
cat /var/www/fina-connect/core/whatsapp.py | grep -A5 "def send_document"
grep -r "business_type\|company_type" /var/www/fina-connect/companies/models.py | head -5
```

## KORAK 2 — Management command: sim_fitness

Napiši `/var/www/fina-connect/fitness/management/commands/sim_fitness.py`

### Što kreirati (čitaj models.py pa mappiraj na stvarna polja):

**Kompanija:**
- name='Fitness Centar Fenix', business_type provjeri što je valjano u Company modelu

**10 Member-a s raznolikošću:**
- 2x basic, 3x standard, 3x premium, 2x vip
- 3 s membership_expires za 3-5 dana (expiry warning test)
- 2 s membership_expires prošlim (expired)
- 2 s rfid_card
- Status mix: 7 active, 2 frozen, 1 inactive
- Realistična hrvatska imena

**MemberCheckIn (25 check-ina):**
- Rasporedi po zadnjih 14 dana
- Neki s check_out, neki bez (još su u dvorani)
- Svaki Member barem 1-2 check-ina

**Ako Gemini dodao modele — dodaj i:**
- 2 MembershipPlan (Basic 29.99 EUR/mj, Premium 59.99 EUR/mj)
- MemberSubscription za svaki Member
- 3 Payment zapisa
- 2 WorkoutClass (Yoga ponedjeljak 9:00, CrossFit petak 18:00)
- ClassBooking za nekoliko Member-a
- 3 Equipment (Bicikl ergometar, Traka za trčanje, Utezi)

**Opcija --reset:** briše sve fitness podatke za tu kompaniju i kreira iznova

```bash
# Pokretanje:
cd /var/www/fina-connect
venv/bin/python manage.py sim_fitness
venv/bin/python manage.py sim_fitness --reset
```

## KORAK 3 — Testovi: fitness/tests.py

Standard: teški, realni, ne trivijalni. Minimum 20 testova.

### Kategorije testova:

**A) Model testovi (6):**
```python
# T01 — Member kreiranje i __str__
# T02 — membership_expires logika (is_expired, days_until_expiry ako postoji)
# T03 — CheckIn kreiranje, trajanje (check_out - check_in)
# T04 — Cross-tenant izolacija: Member jedne kompanije nije vidljiv drugoj
# T05 — Member status transitions (active→frozen→inactive)
# T06 — RFID card uniqueness (ako postoji unique constraint) ili duplikat handling
```

**B) View testovi (8):**
```python
# T07 — member_list: GET 200, paginacija, search po imenu
# T08 — member_list: filter po membership_type i status
# T09 — member_create: GET 200 forma, POST kreira Member
# T10 — member_detail: GET 200, prikazuje checkin historiju
# T11 — member_edit: POST ažurira membership_type
# T12 — member_checkin: POST kreira MemberCheckIn, GET 405
# T13 — checkin_dashboard: GET 200, prikazuje aktivne sesije
# T14 — member_detail 404 za tuđu kompaniju (cross-tenant)
```

**C) Simulacijski testovi (6) — realni scenariji:**
```python
# T15 — Scenarij: novi član se upiše, dobiva check-in, ima aktivno clanstvo
# T16 — Scenarij: član s isteklim članstvom → status expired, check-in blokiran ili upozorenje
# T17 — Scenarij: bulk check-in (5 članova u dvoranu za yoga sat)
# T18 — Scenarij: expiry warning — filter members koji ističu za 7 dana
# T19 — Scenarij: frozen member pokušava check-in → odgovarajući response
# T20 — Scenarij: dashboard statistike — ukupno aktivnih, danas check-ini, koji su trenutno u dvorani
```

**D) Ako Gemini dodao modele — dodaj još (po 2 za svaki novi model):**
```python
# T21-T22 — MembershipPlan i MemberSubscription state machine
# T23-T24 — WorkoutClass kapacitet + ClassBooking overbooking zaštita
# T25-T26 — Payment tracking + uplata bez subscriptiona
```

### Setup pattern (kopiraj iz udruge testova):
```python
_n = [0]
def _uid():
    _n[0] += 1
    return _n[0]

class FitnessTest(TestCase):
    def setUp(self):
        n = _uid()
        from companies.models import Company
        # provjeri koji business_type je valjan za fitness
        self.company = Company.objects.create(
            name='FitTest %d' % n,
            oib='%011d' % (70000000000 + n),
            # business_type='fitnes'  ← provjeri u models.py
        )
        self.company2 = Company.objects.create(
            name='Druga %d' % n,
            oib='%011d' % (80000000000 + n)
        )
        self.user = User.objects.create_user(username='fit%d' % n, password='x')
        self.client = Client()
        self.client.force_login(self.user)
        s = self.client.session
        s['company_id'] = str(self.company.pk)
        s.save()
```

## KORAK 4 — Pokreni testove i spremi rezultate
```bash
cd /var/www/fina-connect

# Pokreni fitness testove
venv/bin/python manage.py test fitness --verbosity=2 --keepdb 2>&1 | tee /tmp/fitness_test_output.txt

# Summary
echo "=== SUMMARY ===" >> /tmp/fitness_test_output.txt
grep -E "^(OK|FAIL|ERROR|Ran [0-9])" /tmp/fitness_test_output.txt | tail -5
cat /tmp/fitness_test_output.txt | tail -10
```

## KORAK 5 — Generiraj HTML forme i pošalji na WhatsApp

### Što generirati (WeasyPrint → PDF):

**Dokument 1 — Lista članova** (A4 portrait)
Tabela: Ime Prezime | Tip | Status | Datum isteka | RFID
Zaglavlje: "Fitness Centar Fenix — Lista članova"
Datum generiranja, ukupan broj, aktivnih X / zamrznutih Y

**Dokument 2 — Iskaznica člana** (A4 landscape, po jedna po stranici za prvih 3 člana)
Ime, prezime, membership_type (badge boja: basic=siva, standard=plava, premium=zlatna, vip=ljubičasta)
Datum isteka, RFID, QR kod s "FENIX-{member.pk}"

**Dokument 3 — Check-in dnevnik** (A4 portrait)
Zadnjih 14 dana, po datumu, tko je bio kada
Ukupno posjeta, prosječno po danu, koji dan najposjećeniji

**Dokument 4 — Test rezultati** (A4 portrait)
Sadržaj /tmp/fitness_test_output.txt formatirano:
- Zeleni tick za OK testove
- Crveni X za FAIL
- Ukupno: X/Y prošlo

### Slanje:
```python
import os
from core.whatsapp import send_document, send_text

IVAN = '385991908089'

# Najava
send_text(IVAN,
    '🏋️ Fitness modul — simulacija završena!\n'
    f'Testovi: vidi priložene dokumente\n'
    f'Kompanija: Fitness Centar Fenix\n'
    f'Članova: 10 | Check-ini: 25',
    company_id=None
)

# Svaki PDF
docs = [
    ('/tmp/fitness_docs/lista_clanova.pdf', '📋 Lista članova'),
    ('/tmp/fitness_docs/iskaznice.pdf', '🪪 Iskaznice članova'),
    ('/tmp/fitness_docs/checkin_dnevnik.pdf', '📅 Check-in dnevnik'),
    ('/tmp/fitness_docs/test_rezultati.pdf', '✅ Test rezultati'),
]
for path, caption in docs:
    if os.path.exists(path):
        result = send_document(IVAN, path, caption=caption)
        print(f'{caption}: {result}')
    else:
        print(f'NEMA FAJLA: {path}')
```

## KORAK 6 — Finalna provjera i rezultat

```bash
# Provjeri sve
ls -la /tmp/fitness_docs/
cat /tmp/fitness_test_output.txt | grep -E "Ran|OK|FAIL|ERROR"

# Napiši result fajl
python3 -c "
import json, os
tests = open('/tmp/fitness_test_output.txt').read()
ran = [l for l in tests.split('\n') if l.startswith('Ran')]
ok = 'OK' in tests
result = {
    'status': 'DONE' if ok else 'PARTIAL',
    'tests': ran[-1] if ran else 'unknown',
    'docs_sent': [f for f in os.listdir('/tmp/fitness_docs/') if f.endswith('.pdf')],
    'whatsapp': '385991908089',
}
open('/tmp/fitness_done.txt','w').write(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
"
```

## Definicija DONE
- [ ] sim_fitness command kreira 10 Member + 25 CheckIn bez greške
- [ ] Minimum 20 testova — svi prolaze (ili jasno dokumentirani FAIL razlozi)
- [ ] 4 PDF dokumenta u /tmp/fitness_docs/
- [ ] Najava + sva 4 PDF poslana na 385991908089
- [ ] /tmp/fitness_done.txt postoji

## Napomena o redoslijedu
Ako Gemini tek radi — pokreni sim_fitness i testove s osnovnim modelima (Member + MemberCheckIn).
Kad Gemini završi → proširi testove za nove modele i pošalji ažurirani dokument.
