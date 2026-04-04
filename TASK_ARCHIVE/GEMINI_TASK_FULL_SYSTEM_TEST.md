# GEMINI_TASK: Potpuni simulacijski test sustava
# Kreirao: Sonnet (26.03.2026) — Ivanov nalog prije odlaska u HR
# Prioritet: 🔴 KRITIČNO
# max_steps: 80

## KONTEKST
Ivan je otišao u HR. Trebas autonomno testirati SVE module LIMIT Connect sustava.
Koristis: MCP alate (exec_command, query_db, django_orm), Haiku za brze provjere.
Ivan prima WhatsApp report na: **+491723006985** (DE broj, Nufringen)

## TVOJ ZADATAK
Prodi kroz SVAKI modul i provjeri:
1. Modeli se učitavaju (ImportError = greška)
2. URLs resolveaju (reverse() radi)
3. Views vraćaju 200/302 (ne 500)
4. Kritične poslovne logike rade (fiskalizacija, fakture, POS)
5. Sve greške → odmah popraviti → commitati

## REDOSLJED TESTIRANJA

### FAZA 1 — Infrastruktura (odmah)
```bash
cd /var/www/fina-connect
# 1. Django check
/var/www/fina-connect/venv/bin/python manage.py check --deploy 2>&1 | tail -20
# 2. Migracije
/var/www/fina-connect/venv/bin/python manage.py showmigrations | grep '\[ \]' | head -20
# 3. Celery status
systemctl status celery-worker celery-beat --no-pager
# 4. Gunicorn
systemctl status gunicorn --no-pager
```

### FAZA 2 — Modul testovi (django test runner)
```bash
cd /var/www/fina-connect
# Pokreni sve postojeće testove
/var/www/fina-connect/venv/bin/python manage.py test \
  invoicing pos archiva worktime konto udruge delivery \
  --verbosity=2 --keepdb 2>&1 | tail -100
```

### FAZA 3 — Simulacijski testovi (po modulu)

#### 3A. Invoicing
```python
# Kreiraj testnu fakturu, fiskaliziraj (test mode), provjeri status
from invoicing.models import Invoice
from companies.models import Company
co = Company.objects.first()
inv = Invoice.objects.filter(company=co, status='DRAFT').first()
print('Invoicing OK' if inv else 'NEMA DRAFT FAKTURA')
```

#### 3B. POS
```python
from pos.models import POSTerminal, POSReceipt
terminals = POSTerminal.objects.all()
print(f'Terminala: {terminals.count()}')
receipts = POSReceipt.objects.order_by('-id')[:1]
print(f'Zadnji račun: {receipts.first()}')
```

#### 3C. Worktime
```python
from worktime.models import TimeEntry, EmployeeProfile
entries = TimeEntry.objects.count()
profiles = EmployeeProfile.objects.count()
print(f'TimeEntry: {entries}, Profila: {profiles}')
```

#### 3D. Konto / Računovodstvo
```python
from konto.models import JournalEntry
je = JournalEntry.objects.order_by('-id').first()
print(f'Zadnja temeljnica: {je}')
```

#### 3E. Udruge (9 segmenata)
```python
from django.apps import apps
udruge_modeli = ['Loviste', 'LovackaIskaznica', 'Pcelinjak', 'Kosnica',
                 'Revir', 'DestilacijaKotao', 'Vocnjak', 'Intervencija',
                 'StatusBranitelja', 'Zadrugar']
for m_name in udruge_modeli:
    for app in apps.get_app_configs():
        try:
            m = app.get_model(m_name)
            print(f'{m_name}: OK ({m.objects.count()} zapisa)')
            break
        except:
            pass
```

#### 3F. Tax Wizard
```python
from tax_wizard.models import TaxFormTemplate, TaxDeadline
print(f'Obrasci: {TaxFormTemplate.objects.count()}')
print(f'Deadlineovi: {TaxDeadline.objects.count()}')
```

#### 3G. Delivery / Transport
```python
from delivery.models import DispatchOffer, ConsolidatedDelivery
print(f'Ponude: {DispatchOffer.objects.count()}')
print(f'Dostave: {ConsolidatedDelivery.objects.count()}')
```

#### 3H. Fiskalizacija
```python
from fiscal.models import FiscalLog
failed = FiscalLog.objects.filter(success=False).count()
pending = FiscalLog.objects.filter(jir='').count()
print(f'Fiscal failed: {failed}, Pending JIR: {pending}')
```

### FAZA 4 — URL smoke test
```bash
# Provjeri kritične URL-ove vraćaju 200 (s curl, bez auth = 302 je OK)
for url in /hr/invoicing/ /hr/pos/joker/ /hr/worktime/ /hr/konto/ /hr/udruge/ /hr/ai/ /hr/gdpr/dashboard/; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/hr/login/?next=$url)
  echo "$url -> $STATUS"
done
```

### FAZA 5 — Greške i popravci
Za svaku grešku koju naideš:
1. Procijeni težinu (🔴 kritično / 🟠 visoko / 🟡 srednje)
2. Napravi fix direktno
3. Commitaj: `git add -A && git commit -m "fix: [opis] — Gemini auto-fix"`
4. Dodaj u izvještaj

### FAZA 6 — WhatsApp report Ivanu
Na kraju pošalji WhatsApp na **+491723006985**:

```python
from core.whatsapp import send_whatsapp_text
report = """
🤖 FENIX TEST REPORT — {datum}

✅ Testovi prošli: X/Y
🔴 Kritične greške: N
🟠 Visoki problemi: N
🟡 Srednji problemi: N

Popravci commitani: {commit_hash}

Moduli OK: invoicing, pos, worktime...
Moduli s problemima: ...

Link: https://limit-connect.com/superadmin/ai/
"""
send_whatsapp_text(phone='+491723006985', message=report, session='default')
```

## PRAVILA
1. Nikad ne gasiš live servise
2. Samo testni podaci za simulacije (test=True ili rollback)
3. Svaki fix ide u git commit ODMAH
4. Haiku koristiš za klasifikaciju grešaka i pisanje fix opisa
5. Javi Ivanu samo greške 🔴 i 🟠 — ne zatrpavaj s 🟡

## KRAJ SESIJE
Ažuriraj FENIX_STATUS.md s rezultatima.
