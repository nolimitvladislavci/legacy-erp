# GEMINI TASK: QR Integracija — Asimilacija u sve segmente

**Prioritet:** HIGH  
**Dodijeljeno:** Gemini autonomous  
**Datum:** 2026-04-14  
**Provjera:** Sonnet na kraju sesije

---

## Kontekst

Implementiran globalni QR endpoint (`/qr/`) sa HMAC zaštitom.
Postoje **28 mjesta** koja još direktno importaju `qrcode` Python library
umjesto da koriste centralnu `signed_qr_url()` / `qr_base64()` funkciju.

## Cilj

Sve `import qrcode` reference u projektu zamijeniti s centralnim utils-om.
Nema iznimaka. Svaki QR kod u platformi mora ići kroz `core/qr_views.py`.

---

## Datoteke za refaktoriranje

### Python views (zamijeniti qr_base64):
```
memio_pet/views.py          (pet_qr_code view → već ima endpoint, ali generacija nije centralna)
accounts/auth_views.py      (3 mjesta: 2FA QR, barcode, device token QR)
livestock/views_pets.py     (panic QR)
appointments/views.py       (booking QR)
boxgram/tasks.py            (boxgram QR)
pos/utils.py                (FINA fiscalizacijski QR — POSEBNO: zadržati ERROR_CORRECT_H!)
pos/views.py                (checkout QR)
pos/complaint_views.py      (2 mjesta)
pos/management/commands/generate_pos_qr.py
invoicing/services/fiscalize.py  (FINA QR — zadržati ERROR_CORRECT_H!)
invoicing/services/pdf_service.py  (2 mjesta — WeasyPrint, koristiti qr_base64)
assessment/views.py
registration/views.py
udruge/qr_utils.py
marketplace/views.py
documents/views_scan.py
documents/views_arhiva.py
scripts/generate_table_qr.py
```

### Pattern zamjene (Python):
```python
# STARO:
import qrcode
qr = qrcode.QRCode(version=1, box_size=8, border=2)
qr.add_data(url)
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")
buf = io.BytesIO()
img.save(buf, format="PNG")
b64 = base64.b64encode(buf.getvalue()).decode()

# NOVO (za base64/PDF/email):
from core.qr_views import qr_base64
b64 = qr_base64(url, size=200)

# NOVO (za URL u templateu):
from core.qr_views import signed_qr_url
url = signed_qr_url(data, size=200)
```

### Poseban slučaj — FINA QR (fiscalizacija):
FINA zahtijeva `ERROR_CORRECT_H` (highest). `qr_base64()` koristi `ERROR_CORRECT_M`.
Dodaj parametar u `qr_base64()`:
```python
def qr_base64(data, size=200, color="000000", bg="ffffff", error_correction=None):
    # error_correction=None → ERROR_CORRECT_M (default)
    # error_correction="H"  → ERROR_CORRECT_H (za FINA)
```
Primjer: `qr_base64(fina_url, size=150, error_correction="H")`

---

## Testovi koje treba pokrenuti

### 1. Unit testovi (pokrenuti pytest):
```bash
cd /var/www/fina-connect
venv/bin/pytest pos/tests/ invoicing/tests/ accounts/tests/ -x -q 2>/dev/null
```

### 2. Test QR endpoint sigurnosti:
```python
# Mora vratiti 403 bez potpisa
from django.test import Client
c = Client()
resp = c.get('/qr/?data=https://phishing.com')
assert resp.status_code == 403, "FAIL: open proxy ranjivost!"

# Mora raditi s potpisom
from core.qr_views import signed_qr_url
url = signed_qr_url('https://limit-connect.com')
resp = c.get(url)
assert resp.status_code == 200
assert resp['Content-Type'] == 'image/png'
print("QR security OK")
```

### 3. Test FINA QR (ERROR_CORRECT_H):
```python
from core.qr_views import qr_base64
b64 = qr_base64("https://porezna.hr/fiskalizacija/test", size=150, error_correction="H")
assert b64.startswith("data:image/png;base64,")
print("FINA QR OK")
```

### 4. Test rate limiting:
```python
from django.test import RequestFactory
from core.qr_views import qr_code_view, signed_qr_url
from django.core.cache import cache
cache.clear()
rf = RequestFactory()
from urllib.parse import urlparse, parse_qs
url = signed_qr_url('https://limit-connect.com')
params = parse_qs(urlparse(url).query)
for i in range(125):
    req = rf.get('/qr/', {k: v[0] for k, v in params.items()},
                 REMOTE_ADDR='1.2.3.4')
    resp = qr_code_view(req)
    if resp.status_code == 429:
        print(f"Rate limit na zahtjevu {i+1} — OK")
        break
else:
    print("FAIL: rate limit nije radio")
```

### 5. Test iz vana (curl simulacija):
```bash
# Mora biti 403
curl -s -o /dev/null -w "%{http_code}" "https://limit-connect.com/qr/?data=https://google.com"
# Mora biti 200 s potpisom (generiraj potpis internim alatom)
```

### 6. Test svih QR generacija po modulu:
```bash
venv/bin/python manage.py shell -c "
from core.qr_views import qr_base64, signed_qr_url
modules = [
    ('invoicing', 'https://limit-connect.com/hr/ponuda/test/'),
    ('pos-fina', 'https://porezna.hr/fiskalizacija/zki=TEST'),
    ('memio', 'https://memio.pet/pas/12345'),
    ('udruge', 'https://limit-connect.com/no-limit/clan/abc'),
]
for name, url in modules:
    b64 = qr_base64(url, size=200)
    surl = signed_qr_url(url)
    print(f'{name}: b64={len(b64)}chars, url={surl[:60]}')
print('ALL OK')
"
```

---

## Provjera završetka

Po završetku postavi u FENIX_STATUS.md:
```
QR Integracija: DONE [datum] — 0 direktnih qrcode importa u views
```

I pokreni:
```bash
grep -rn "import qrcode" /var/www/fina-connect/ \
  --include="*.py" | grep -v venv | grep -v core/qr_views.py | wc -l
# Mora biti 0
```

---

## Napomene

- `scripts/` i `management/commands/` mogu zadržati direktan import (CLI alati)
- `core/qr_views.py` sam sebi smije importati qrcode
- Svaka zamjena mora proći `python manage.py check` bez grešaka
- Commit nakon svakih 5 datoteka s jasnom porukom
