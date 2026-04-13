# Frontend Faza 3 — Documents + Inventory JS Extraction

## Cilj
Izvući inline <script> blokove iz templates/documents/ i templates/inventory/ u statičke JS fajlove.

## Documents (6 fajlova s inline JS)
- ai_inbox.html — 1 script
- arhiva_convert.html — 1 script  
- arhiva_list.html — 2 scripta (13 ukupno inline blokova — NAJGORI)
- arhiva_upload.html — 1 script
- otpremnica_form.html — 1 script
- scan_mobile.html — 1 script

**Output:** static/js/documents.js

## Inventory (7 fajlova s inline JS)
- blind_count.html — 1 script
- goods_receipt_form.html — 1 script
- inventura_count.html — 2 scripta
- inventura_create.html — 1 script
- kalo.html — 1 script
- predictive_dashboard.html — 1 script
- transfer_create.html — 1 script

**Output:** static/js/inventory.js

## Pravila
1. Django template varijable → `<script id="X-config" type="application/json">`
2. Svaki fajl: backup (.bak), zamjena, provjera
3. Nakon svakog templatea: `cd /var/www/fina-connect && source venv/bin/activate && python manage.py check`
4. Smoke test: `curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/documents/arhiva/`
5. Ako pukne — rollback iz .bak

## Referentni primjer (Faza 2 — POS)
Pogledaj static/js/pos/ za primjer kako je rađeno:
- pos-core.js, pos-quick.js, pos-scanner.js, pos-fiscal.js, itd.
- Svaki template ima `<script type="application/json" id="pos-config">` za Django varijable
- Inline JS zamijenjen s `<script src="/static/js/pos/X.js"></script>`
