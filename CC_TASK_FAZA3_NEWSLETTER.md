# CC Task — Faza 3 + Newsletter (sekvencijalno)

Danas radiš dva zadatka REDOM (ne paralelno):

---

## ZADATAK 1 — Frontend Faza 3: Documents + Inventory JS Extraction

Pročitaj /var/www/fina-connect/FRONTEND_FAZA3_4_PLAN.md za detalje.

### Kratko:

**A) documents.js** — izvuci inline JS iz templates/documents/ (6 fajlova):
- ai_inbox.html, arhiva_convert.html, arhiva_list.html, arhiva_upload.html, otpremnica_form.html, scan_mobile.html
- Output: static/js/documents.js (ili ako su previše različiti, static/js/documents/ direktorij s više fajlova)

**B) inventory.js** — izvuci inline JS iz templates/inventory/ (7 fajlova):
- blind_count.html, goods_receipt_form.html, inventura_count.html, inventura_create.html, kalo.html, predictive_dashboard.html, transfer_create.html
- Output: static/js/inventory.js (ili static/js/inventory/ direktorij)

### Pravila:
1. Django varijable → `<script id="X-config" type="application/json">`
2. Backup svaki fajl (.bak) prije promjene
3. Nakon SVAKOG templatea:
   - `cd /var/www/fina-connect && source venv/bin/activate && python manage.py check`
   - `systemctl restart gunicorn-fina`
   - `curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/documents/arhiva/`
4. Ako pukne — rollback: `cp X.html.bak X.html && systemctl restart gunicorn-fina`
5. Pogledaj static/js/pos/ za primjer kako je Faza 2 rađena

### Referenca:
- Server: root@37.27.248.86 (ali ti si VEĆ na serveru)
- Projekt: /var/www/fina-connect
- Venv: source venv/bin/activate
- Gunicorn restart: systemctl restart gunicorn-fina

---

## ZADATAK 2 — Newsletter deploy (TEK KAD ZADATAK 1 ZAVRŠI!)

### Stanje:
- Trenutni newsletter: /var/www/fina-connect/templates/core/newsletter_2026.html
- URL route: core/urls.py linija 94:
  `path("newsletter/", lambda r: render(r, core/newsletter_2026.html), name="newsletter")`
- Trenutno samo HR verzija, nema DE

### Koraci:
1. Pročitaj trenutni newsletter template: `cat /var/www/fina-connect/templates/core/newsletter_2026.html`
2. Backup: `cp newsletter_2026.html newsletter_2026.html.bak`
3. Ažuriraj HR newsletter template (moderniji dizajn, dodaj "Moduli" sekciju ako fali)
4. Kreiraj DE verziju: `/var/www/fina-connect/templates/core/newsletter_2026_de.html`
5. Dodaj DE route u core/urls.py:
   `path("de/newsletter/", lambda r: render(r, core/newsletter_2026_de.html), name="newsletter_de"),`
6. Restart: `systemctl restart gunicorn-fina`
7. Test:
   - `curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/newsletter/` → 200
   - `curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/de/newsletter/` → 200

---

VAŽNO: Radi ova dva zadatka SEKVENCIJALNO. Završi Zadatak 1 pa tek onda kreni na Zadatak 2.
