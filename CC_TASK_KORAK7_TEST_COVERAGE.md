# CC TASK — KORAK 7: Critical Path Test Coverage
**Datum: 14.04.2026.**

## ⚠️ NAPOMENE
1. Python: `/var/www/fina-connect/venv/bin/python` — NIKAD `python`
2. systemctl: NEMOJ — napiši "POTREBAN GUNICORN RELOAD" na kraju
3. WhatsApp pattern:
```bash
/var/www/fina-connect/venv/bin/python -c "
import os,sys,django
os.environ['DJANGO_SETTINGS_MODULE']='core.settings'
sys.path.insert(0,'/var/www/fina-connect')
django.setup()
from core.whatsapp import send_text
send_text('4915771998747','OVDJE PORUKA')
" 2>/dev/null
```

---

## Cilj
Coverage > 40% na kritičnim app-ovima: `pos/`, `invoicing/`, `accounts/`
Svaki kritični put ima happy path + jedan error case test.

---

## 7.1 — Provjeri trenutni coverage

```bash
cd /var/www/fina-connect
/var/www/fina-connect/venv/bin/pytest \
  pos/tests/ invoicing/tests/ accounts/tests/ \
  --co -q 2>/dev/null | tail -5

# Coverage na kritičnim modulima
/var/www/fina-connect/venv/bin/pytest \
  pos/tests/ invoicing/tests/ accounts/tests/ \
  --cov=pos --cov=invoicing --cov=accounts \
  --cov-report=term-missing -q \
  --no-header 2>/dev/null | tail -20
```

---

## 7.2 — Kritični putevi koji MORAJU imati test

Provjeri postoje li testovi, ako ne — napiši ih:

### A) Login flow
```bash
grep -rn "def test.*login\|def test.*auth\|def test.*pin" \
  accounts/tests/ --include="*.py" | head -10
```

Ako nema, napiši `accounts/tests/test_login_flow.py`:
```python
# Test: username+password login → 200
# Test: PIN login → redirect na dashboard
# Test: nepostojeci korisnik → 401
# Test: AnonymousUser → redirect na login
```

### B) Faktura kreiranje
```bash
grep -rn "def test.*invoice\|def test.*faktur" \
  invoicing/tests/ --include="*.py" | head -10
```

Ako nema, napiši `invoicing/tests/test_invoice_critical.py`:
```python
# Test: kreiranje Invoice → status DRAFT
# Test: slanje fakture → status SENT
# Test: client_portal GET bez login → 200 (PUBLIC)
# Test: client_portal POST accept → status ACCEPTED
```

### C) POS bon
```bash
grep -rn "def test.*pos\|def test.*receipt\|def test.*bon" \
  pos/tests/ --include="*.py" | head -10
```

Ako nema, napiši `pos/tests/test_pos_critical.py`:
```python
# Test: kreiranje POSReceipt → status PAID
# Test: fiskalizacija mock → ZKI/JIR se generira
# Test: company switch → POSReceipt pripada novoj kompaniji
```

### D) Company switch
```bash
grep -rn "def test.*switch\|def test.*company" \
  accounts/tests/ --include="*.py" | head -5
```

Ako nema, napiši `accounts/tests/test_company_switch.py`:
```python
# Test: switch_company POST s membership_id → 302 na /
# Test: switch_company bez login → 302 na login
# Test: AnonymousUser na COMPANY ruti → 302
```

---

## 7.3 — Pokreni testove

```bash
cd /var/www/fina-connect

# Samo kritični putevi
/var/www/fina-connect/venv/bin/pytest \
  accounts/tests/test_login_flow.py \
  invoicing/tests/test_invoice_critical.py \
  pos/tests/test_pos_critical.py \
  accounts/tests/test_company_switch.py \
  -v --tb=short 2>/dev/null

# Ako puca: popravi test, ne app kod
# Ako test otkriva pravi bug: fix app kod + commit posebno
```

---

## 7.4 — Coverage report

```bash
/var/www/fina-connect/venv/bin/pytest \
  pos/tests/ invoicing/tests/ accounts/tests/ \
  --cov=pos --cov=invoicing --cov=accounts \
  --cov-report=term-missing \
  --cov-fail-under=40 \
  -q --no-header 2>/dev/null | tail -15
```

Cilj: **coverage >= 40%** na sva 3 modula.

---

## Po završetku

```bash
cd /var/www/fina-connect

/var/www/fina-connect/venv/bin/python manage.py check

git add -A
git commit -m "test(korak7): critical path coverage — login, invoice, POS, company switch"

/var/www/fina-connect/venv/bin/python -c "
c = open('FENIX_STATUS.md').read()
c = c.replace('| 7 Test coverage | 🔄 AKTIVAN | 0% |', '| 7 Test coverage | ✅ GOTOVO | 100% |')
c = c.replace('| 8 Load test | ⏳ na redu | — |', '| 8 Load test | 🔄 AKTIVAN | 0% |')
open('FENIX_STATUS.md', 'w').write(c)
"
git add FENIX_STATUS.md
git commit -m "status: KORAK 7 ✅ → KORAK 8 🔄"

/var/www/fina-connect/venv/bin/python -c "
import os,sys,django
os.environ['DJANGO_SETTINGS_MODULE']='core.settings'
sys.path.insert(0,'/var/www/fina-connect')
django.setup()
from core.whatsapp import send_text
send_text('4915771998747','KORAK 7 GOTOV — Test coverage >40%. Kritični putevi testirani. Kreće KORAK 8 Load test.')
" 2>/dev/null

echo "POTREBAN GUNICORN RELOAD"
```
