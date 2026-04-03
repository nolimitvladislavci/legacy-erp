# GEMINI TASK: UI Revolution — Sprint 1+2
**Datum:** 03.04.2026. | **Prioritet:** 🔴 ODMAH
**Instrukcije:** Pročitaj CC_TASK_UI_REVOLUTION_10_10.md i primijeni Sprint 1 i Sprint 2.

## REDOSLIJED (ne preskačaj korake):

### KORAK 1 — Pročitaj task
READ: /var/www/fina-connect/CC_TASK_UI_REVOLUTION_10_10.md

### KORAK 2 — Pročitaj trenutni CSS
READ: /var/www/fina-connect/static/css/global_themes.css

### KORAK 3 — Primijeni CSS varijable (Sprint 1)
WRITE: /var/www/fina-connect/static/css/global_themes.css
- Dodaj sve CSS varijable iz Sprint 1.2 (tamna tema) i Sprint 1.3 (svjetla tema)
- NE brišaj postojeće, samo dopunjuj

### KORAK 4 — Provjeri base.html theme switcher
READ: /var/www/fina-connect/templates/base.html (samo dio oko theme-toggle)

### KORAK 5 — Zamijeni theme switcher (Sprint 1.5)
WRITE: templates/base.html
- Zamijeni stari theme-toggle button s novim 2-way switcherom
- Zamijeni toggleTheme() s setTheme()
- Init script (čita localStorage, prikazuje aktivan gumb)

### KORAK 6 — Provjeri fenix-ui.css
READ: /var/www/fina-connect/static/css/fenix-ui.css

### KORAK 7 — Dodaj tranzicije (Sprint 5)
WRITE: /var/www/fina-connect/static/css/fenix-ui.css
- Dodaj tranzicije na kraju fajla
- Dodaj scanning animaciju za forme

### KORAK 8 — pdf_utils.py (Sprint 2.1)
WRITE: /var/www/fina-connect/core/pdf_utils.py
- Cijeli fajl iz CC_TASK Sprint 2.1

### KORAK 9 — Provjeri postoji li Company.pdf_template
EXEC: cd /var/www/fina-connect && grep -n "pdf_template\|PDF_TEMPLATE" companies/models.py | head -10

### KORAK 10 — collectstatic + test
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py collectstatic --noinput 2>&1 | tail -5
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -5

### KORAK 11 — git commit
EXEC: cd /var/www/fina-connect && git add static/css/global_themes.css static/css/fenix-ui.css templates/base.html core/pdf_utils.py && git commit -m "feat(ui): dark/light tema polish + 2-way switcher + pdf_utils globalni registry"

### KORAK 12 — restart
EXEC: systemctl restart gunicorn-fina

## DONE kriterij:
- global_themes.css ima sve varijable za obje teme
- base.html ima 2-way theme switcher (tamno/svjetlo)
- core/pdf_utils.py postoji s PDF_TEMPLATE_REGISTRY
- Gunicorn restartovan bez greška
