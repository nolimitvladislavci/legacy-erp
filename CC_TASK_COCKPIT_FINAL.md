## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — Ivan Cockpit: okrugli stol + live podaci

## Stanje
- Template: `/var/www/fina-connect/templates/dashboards/ivan_cockpit.html` (325 linija) ✅
- View: `core/views.py` → `ivan_cockpit()` ✅  
- URL: `/hr/superadmin/ivan/` → 302 ✅
- Okrugli stol template: `/var/www/fina-connect/templates/dashboards/tim_chat.html` ✅

## Zadatak — 3 stvari

### 1. Provjeri što cockpit template trenutno prikazuje
```bash
head -50 /var/www/fina-connect/templates/dashboards/ivan_cockpit.html
grep -n "okrugli\|stol\|seat\|SVG\|svg" /var/www/fina-connect/templates/dashboards/ivan_cockpit.html | head -10
tail -80 /var/www/fina-connect/templates/dashboards/ivan_cockpit.html
```

### 2. Dodaj okrugli stol na dno cockpit templatea
Iz `tim_chat.html` izvuci SVG okruglog stola i JS logiku za superadmin
(blok između `{% if request.user.is_superuser %}` i `{% else %}`).
Dodaj ga na kraj `ivan_cockpit.html` kao zasebnu sekciju.

Prilagodi: umjesto `fetch('/superadmin/ai/api/submit-request/')` 
koristi isti endpoint ali dodaj context `[COCKPIT]` prefix u description.

### 3. Provjeri da cockpit prikazuje live podatke iz contexta
Cockpit view šalje: `mrr`, `pos_promet_danas`, `pos_bonovi_danas`,
`users_active_week`, `subs`, `pos_by_company`, `disk_info`, `mem_info`

Provjeri da template ih prikazuje. Ako template ima hardkodirane vrijednosti
(npr. "1.330 EUR" umjesto `{{ mrr }}`) — zamijeni s template varijablama.

```bash
grep -n "1\.330\|hardcode\|TODO\|XXX\|0\.00\|dummy" \
  /var/www/fina-connect/templates/dashboards/ivan_cockpit.html | head -20
```

### 4. Test
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -2
systemctl reload gunicorn-fina 2>/dev/null || systemctl restart gunicorn-fina
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/superadmin/ivan/
```
Mora biti 302.

## PRAVILA
- Ne diraj views.py ni urls.py
- Samo template promjene — sigurno, bez 502 rizika  
- Backup: `cp ivan_cockpit.html ivan_cockpit.html.bak` prije promjene
