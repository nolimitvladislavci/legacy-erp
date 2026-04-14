# CC TASK — KORAK 6: Globalni standardi
**Datum: 14.04.2026.**

## ⚠️ NAPOMENE
1. Python: `/var/www/fina-connect/venv/bin/python` — NIKAD `python`
2. systemctl: NEMOJ koristiti — napiši "POTREBAN GUNICORN RELOAD" na kraju
3. WhatsApp pattern (kopiraj doslovno):
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
Nula direktnih `import qrcode` izvan `core/qr_views.py`.
Sve liste koriste `.entity-link`, `.col-actions`, `.btn-action` CSS klase.
Sve ponuda URL reference koriste `get_portal_url()` iz `invoicing/utils.py`.

---

## 6.1 — QR Integracija (28 fajlova)

Pročitaj `/var/www/fina-connect/GEMINI_TASK_QR_INTEGRATION.md` za detalje.

```bash
# Koliko direktnih import qrcode još ima?
grep -rn "import qrcode" /var/www/fina-connect/ --include="*.py" \
  | grep -v venv | grep -v backup | grep -v "core/qr_views.py"
```

**Fix pattern za svaki fajl:**
```python
# STARO:
import qrcode
qr = qrcode.QRCode(...)
qr.add_data(url)
img = qr.make_image(...)
buf = io.BytesIO()
img.save(buf, format="PNG")
b64 = base64.b64encode(buf.getvalue()).decode()

# NOVO:
from core.qr_views import qr_base64
b64 = qr_base64(url, size=200)
```

**Poseban slučaj — FINA fiskalizacija (ERROR_CORRECT_H):**
```python
# FINA zahtijeva najviši error correction
# invoicing/services/fiscalize.py, invoicing/services/pdf_service.py
from core.qr_views import qr_base64
b64 = qr_base64(fina_url, size=150, error_correction="H")
```

Provjeri je li `qr_base64` u `core/qr_views.py` već podržava `error_correction` parametar.
Ako ne, dodaj ga:
```python
def qr_base64(data, size=200, color="000000", bg="ffffff", error_correction=None):
    import qrcode
    ec = {
        "H": qrcode.constants.ERROR_CORRECT_H,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "L": qrcode.constants.ERROR_CORRECT_L,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
    }.get(error_correction, qrcode.constants.ERROR_CORRECT_M)
    ...
```

Commitiraj svake 5 fajlova.

---

## 6.2 — Liste: entity-link, col-actions, btn-action

```bash
# Sve liste koje imaju akcije ali ne koriste globalne CSS klase
grep -rn "btn-sm btn-outline-warning\|btn-sm btn-outline-danger" \
  /var/www/fina-connect/templates/ --include="*.html" \
  | grep -v "partner_list\|BUGLIST\|backup" | head -30
```

**Fix pattern:**
```html
<!-- STARO: -->
<a href="..." class="btn btn-sm btn-outline-warning me-1"><i class="fas fa-edit"></i></a>
<a href="..." class="btn btn-sm btn-outline-danger"><i class="fas fa-trash"></i></a>

<!-- NOVO: -->
<a href="..." class="btn btn-sm btn-outline-warning btn-action me-1" title="Uredi"><i class="fas fa-edit"></i></a>
<a href="..." class="btn btn-sm btn-outline-danger btn-action" title="Obriši"><i class="fas fa-trash"></i></a>
```

Za naziv entiteta (firma, partner, artikl):
```html
<!-- STARO: -->
<a href="..." class="fw-bold text-decoration-none text-dark">{{ naziv }}</a>

<!-- NOVO: -->
<a href="..." class="entity-link">{{ naziv }}</a>
```

Fokus na top 10 najkorištenijih lista:
- `invoicing/templates/invoicing/index.html`
- `partners/templates/partners/partner_list.html` (već ok)
- `inventory/templates/inventory/list.html`
- `work_orders/templates/work_orders/work_order_list.html`
- `documents/templates/documents/arhiva_list.html`
- `pos/templates/pos/products.html`
- `accounts/templates/accounts/employee_list.html`

---

## 6.3 — get_portal_url() za sve ponuda reference

```bash
grep -rn "client_token\|ponuda.*UUID\|/ponuda/" \
  /var/www/fina-connect/ --include="*.py" --include="*.html" \
  | grep -v venv | grep -v backup | grep -v "invoicing/utils.py" \
  | grep -v "core/urls.py\|RouteRegistry\|BUGLIST"
```

Svaki `f"https://limit-connect.com/...{token}..."` ili `/ponuda/{token}/` →
```python
from invoicing.utils import get_portal_url
url = get_portal_url(invoice, lang="hr")
```

---

## Završni test

```bash
# Mora biti 0:
grep -rn "import qrcode" /var/www/fina-connect/ --include="*.py" \
  | grep -v venv | grep -v backup | grep -v "core/qr_views.py" | wc -l

/var/www/fina-connect/venv/bin/python manage.py check
```

---

## Po završetku

```bash
cd /var/www/fina-connect
/var/www/fina-connect/venv/bin/python manage.py check
git add -A
git commit -m "fix(korak6): globalni standardi — QR endpoint, entity-link CSS, get_portal_url"

/var/www/fina-connect/venv/bin/python -c "
c = open('FENIX_STATUS.md').read()
c = c.replace('| 6 Globalni standardi | 🔄 AKTIVAN | 0% |', '| 6 Globalni standardi | ✅ GOTOVO | 100% |')
c = c.replace('| 7 Test coverage | ⏳ na redu | — |', '| 7 Test coverage | 🔄 AKTIVAN | 0% |')
open('FENIX_STATUS.md', 'w').write(c)
"
git add FENIX_STATUS.md
git commit -m "status: KORAK 6 ✅ → KORAK 7 🔄"

# WhatsApp
/var/www/fina-connect/venv/bin/python -c "
import os,sys,django
os.environ['DJANGO_SETTINGS_MODULE']='core.settings'
sys.path.insert(0,'/var/www/fina-connect')
django.setup()
from core.whatsapp import send_text
send_text('4915771998747','KORAK 6 GOTOV — QR + CSS + URL standardi. Kreće KORAK 7 Test coverage.')
" 2>/dev/null

echo "POTREBAN GUNICORN RELOAD"
```
