# DIO 2: CSRF EXEMPT AUDIT + GHOST APP CLEANUP (HAIKU/SONNET)
> Sistematičan, pravila-baziran posao — jasna pravila, jasan scope

## CILJ A: Reducirati 147 csrf_exempt na < 10
## CILJ B: Ukloniti GHOST appove i repo clutter

---

## A. CSRF EXEMPT AUDIT

### Kompletna lista (147 referenci, ~80 dekoratora):
```
appointments/views.py     — 14 csrf_exempt (NAJVIŠE!)
pos/views.py              — 18 referenci  
core/views.py             — 16 referenci
eracun/services/          — 7
synesis/views.py          — 6 + export.py 2
fenix_input/views.py      — 4
inventory/views.py        — 4
payments/views.py         — 3
partners/b2b_views.py     — 2 + wizard_views.py import
livestock/views.py        — 3
website/views.py          — 3
propter/views.py          — 2
documents/views.py        — 2
einvoice/api/webhook.py   — 2
webshop/views.py          — 2
memio_pet/views.py        — 2
memio_world/views.py      — 2
accounts/auth_views.py    — 2
interventions/views.py    — 2
helpdesk/views.py         — 2
gov_export/views.py       — 2
gastro_menu/views.py      — 2
limit_connect_ai/views.py — 2
smart_import/views.py     — 2
superadmin_ai/views.py    — 2
registration/views.py     — 2
zeleni_otok/views.py      — 1
rental/views.py           — 1
```

### PRAVILA — csrf_exempt SMIJE ostati SAMO ako:
1. **Webhook endpoint** koji prima POST od externog servisa (Stripe, eRačun, FINA) — OBAVEZNO dodaj HMAC/signature verifikaciju
2. **API endpoint s token auth** (DRF TokenAuthentication) — DRF sam handla CSRF
3. **Public booking endpoint** koji koristi BookingSignature — već ima HMAC

### PRAVILA — csrf_exempt se MORA ukloniti ako:
1. View koristi `@login_required` ili `LoginRequiredMixin` — CSRF token je dostupan
2. View renderira HTML form — template MORA imati `{% csrf_token %}`
3. AJAX POST iz browsera — HTMX auto-header već šalje CSRF token
4. Interni API poziv — CSRF token dostupan

### Red rada:
1. **appointments/** (14!) — pregled svake funkcije, većina su AJAX handleri koji TREBAJU CSRF
2. **pos/** (18) — POS API vs. browser views
3. **core/** (16) — razluči middleware bypass vs. lazy fix
4. Za svaki uklonjeni csrf_exempt:
   - Provjeri da template/HTMX šalje CSRF token
   - Provjeri da JavaScript uključuje X-CSRFToken header
   - AKO je API endpoint → prebaci na DRF + TokenAuth umjesto csrf_exempt

### Za webhook endpointe koji OSTAJU csrf_exempt, DODAJ:
```python
import hmac, hashlib

def verify_webhook_signature(request, secret):
    """Verify webhook HMAC signature."""
    signature = request.headers.get('X-Signature', '')
    payload = request.body
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
```

---

## B. GHOST APP CLEANUP

### Identificirani GHOST appovi u settings.py:
```python
"fitness",      # GHOST: 0 data but referenced by tests
"insurance",    # GHOST: 0 data but model loaded
"gastro_menu",  # GHOST: 0 data, traceability FK
```

### Procedura za svaki GHOST:
1. `python manage.py shell -c "from <app>.models import *; print([(m.__name__, m.objects.count()) for m in [list svih modela]])"` — potvrdi 0 data
2. Pretraži FK reference: `grep -rn "fitness\|FitnessModel" --include="*.py" | grep -v venv`
3. Pretraži URL uključivanja: `grep -rn "fitness" core/urls.py`
4. Pretraži template reference: `grep -rn "fitness" --include="*.html"`
5. Ako nema FK iz živih modela → ukloni iz INSTALLED_APPS + zakomentariši URL include
6. NE briši fajlove — samo deaktiviraj. Brisanje u sljedećem ciklusu.

### DODATNO: Repo clutter cleanup
- Premjesti sve `*.md` planove iz root-a u `docs/plans/`:
  ```
  BORG_*.md, FENIX_*.md, HAIKU_TASK_*.md, GEMINI_*.md, 
  EU_FONDOVI_*.md, GTM_*.md, HW_SPEC_*.md, etc.
  ```
- Premjesti `backups/audit_patch*` van git-a (to su stari code snapshoti)
- Provjeri `.gitignore` — dodaj `.env`, `*.pid`, `*.log`, `ai_analiza.txt`

---

## NE DIRATI:
- Exception handling (DIO 1 — Opus)
- ORM optimizacije (DIO 3)
- Modele, migracije, poslovnu logiku

## METRIKA USPJEHA
- `grep -rn "csrf_exempt" --include="*.py" | grep -v venv | grep -c "@csrf_exempt"` < 10
- Svaki preostali csrf_exempt ima komentar: `# CSRF exempt: webhook from <service>, verified via HMAC`
- GHOST appovi deaktivirani u settings.py
- Root direktorij čist od plan-fajlova
- `python manage.py check` prolazi
- `python manage.py migrate --check` — nema pending migracija

## COMMIT PORUKE
```
security(csrf): audit 147 csrf_exempt — reduce to N, add HMAC verification

fix(settings): deactivate 3 ghost apps (fitness, insurance, gastro_menu)

chore: move 50+ planning docs to docs/plans/, clean .gitignore
```
