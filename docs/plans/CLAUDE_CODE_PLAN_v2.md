# FINA-CONNECT – Master Plan v2
# Server: root@85.9.201.204 | /var/www/fina-connect

## SESIJA A – SECURITY + NGINX + WEBSITE + DASHBOARD
### A1. Security
- DEBUG=False in core/settings.py
- SECRET_KEY -> os.environ.get('DJANGO_SECRET_KEY', existing_key)
- ALLOWED_HOSTS = ['fina-connect.online', 'viskovic-group.de', '85.9.201.204']

### A2. viskovic-group.de routing
- Check nginx config
- Fix so viskovic-group.de/ shows new black-gold template

### A3. Burza button on website
- Add "Pošalji projekt upit →" to viskovic_group_index.html (DE) and /hr/ (HR)
- Link to https://fina-connect.online/burza/upit/

### A4. Company dashboard
- Add company table to superadmin with subscription plan
- Module toggles (checkboxes) per company, POST to save

## SESIJA B – IMPERSONATION
### B1. Middleware - session['impersonated_company_id'] overrides request.user.profile.company
### B2. ImpersonationLog model
### B3. Banner in base.html
### B4. /superadmin/companies/ list + "Pristupi" button

## SESIJA E – HITNA INTERVENCIJA MODULE
## SESIJA F – TESTIRANJE


---

## SESIJA 15 — DOMAIN ARCHITECTURE + PROPTER FAZA C (2026-03-08)

### Arhitekturna odluka (potvrđeno):
- `fina-connect.online` → ERP platforma (sve ostaje)
- `grosmarkt-online.eu` → Tržnica Online HR varijanta
- `viskovic-group.de` → Holding corporate
- Propter SaaS landing = dio fina-connect.online, NE zasebna domena
- Detalji: vidi DOMAIN_ARCHITECTURE.md

### Faza C — Propter (SLJEDEĆE):
1. Javna eko stranica `/propter/eko/public/<company_slug>/`
2. ESG PDF godišnje izvješće
3. Propter SaaS landing sekcija na fina-connect.online

### Faza D — Tržnica Online:
1. Nginx virtualhost grosmarkt-online.eu (treba root)
2. SSL certbot
3. Django ALLOWED_HOSTS
4. Landing page + marketplace integracija

### Hotfix završen (2026-03-08):
- Login 500 fix: MultipleObjectsReturned — .get() -> .filter().order_by('-last_login').first()
- Duplikat user: ID:2 (ivan.brtan) i ID:27 (grosmarkt) oba imaju isti email
