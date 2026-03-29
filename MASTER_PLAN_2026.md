# MASTER PLAN 2026 — REVIZIJA 2
# Ažurirano: 2026-03-29 — Sonnet (post-simulacija audit)
# Git HEAD: bfc20c95
# simulate_borg: 106/106 (100%) ← nova baseline
#
# STATUS SESIJE: P0.1-P0.5 DONE. T&C, Golubar, PgBouncer, REST API — NISU deployani.
# Joker Pricing: 200 OK (radi). 3-klik registracija: CC_TASK postoji.
# Golubar: module ne postoji u INSTALLED_APPS. T&C middleware kreiran ali NIJE aktiviran.

---

## ═══════════════════════════════════════════════════════
## CURRENT STATE — 2026-03-29
## ═══════════════════════════════════════════════════════

### ✅ DONE (ova sesija + prethodne)
- Experiences 12 templates → 23/23 (100%)
- Design System 6 partials → stat_card, stat_grid, kanban_column, timeline, empty_state, page_header
- BORG Hub → /hub/ live
- CardActivity is_public_facing + is_system_generated → sigurnosna zaštita
- simulate_borg 30 modula → 106/106 (100%)
- sidebar_urls 12/12 (100%)
- GovExport Standard / CroXML Verify → javno live
- Financijski plan + Politika naplate → PDFs
- Didin Konak brošura → PDF
- OPG Turizam prezentacija → PPTX

### ❌ NIJE DEPLOYANO (ostaje za go-live sprint)
| Što | Zašto nije | Blokira |
|-----|-----------|---------|
| T&C middleware | Kreiran ali nije u MIDDLEWARE settings | go-live — 77 firmi |
| Golubar G3-G6 | Module ne postoji (`No module named 'golubar'`) | Petar + golobar uzgajivači |
| 3-klik registracija | CC_TASK postoji, nije buildano | novi korisnici |
| PgBouncer | inactive, nema config | load test na 150+ korisnika |
| Load test | nema load_test* fajlova | go-live verifikacija |
| REST API | 404 na /api/invoicing/ i /api/pos/ | vanjski korisnici, channel manager |
| PropterSoba security | CC_TASK kreiran, nije deployano | sigurnost |

---

## ═══════════════════════════════════════════════════════
## PHASE 0 — GO-LIVE SPRINT (do 15.4.2026)
## Sve ovo MORA biti DONE. Ništa drugo se ne radi.
## ═══════════════════════════════════════════════════════

### P0-A: T&C Consent Middleware [DAN 1 — KRITIČNO]
**Što:** TCConsentMiddleware postoji u core/middleware_tc.py ali NIJE aktiviran.
**Fix:** Dodati u MIDDLEWARE u core/settings.py.
**Redoslijed u MIDDLEWARE:** nakon SessionMiddleware, prije AuthenticationMiddleware.

```python
# core/settings.py — u MIDDLEWARE listu:
MIDDLEWARE = [
    ...
    'django.contrib.sessions.middleware.SessionMiddleware',
    'core.middleware_tc.TCConsentMiddleware',   # ← DODATI OVDJE
    'django.middleware.common.CommonMiddleware',
    ...
]
```

**Verifikacija:**
```bash
/var/www/fina-connect/venv/bin/python manage.py shell -c "
from django.conf import settings
tc = [m for m in settings.MIDDLEWARE if 'TCConsent' in m]
print('TCConsent u MIDDLEWARE:', tc)
assert tc, 'NIJE AKTIVIRAN!'
print('OK')
"
```
**Cilj:** Svih 77 firmi mora proći T&C pri sljedećem loginu.
**Procjena:** 15 min
**Status:** ⏳ ČEKA CC Code

---

### P0-B: Golubar modul G3-G6 [DAN 1-2]
**Problem:** `No module named 'golubar'` — nije u INSTALLED_APPS.
**Provjeri najprije:**
```bash
find /var/www/fina-connect -name "golubar" -type d | grep -v venv
ls /var/www/fina-connect/golubar/ 2>/dev/null || echo "DIR NE POSTOJI"
```

**Scenarij A — dir postoji, nije u INSTALLED_APPS:**
Dodati `'golubar'` u INSTALLED_APPS + URL include u core/urls.py.
Pokrenuti migracije: `python manage.py migrate golubar`

**Scenarij B — dir ne postoji:**
Buildati modul od nule. Osnova:
- Jato model (jato golubova, vlasnik)
- Golub model (prsten, boja, roditelji → GSS-256 seal za rodovnik)
- PDF rodovnik (WeasyPrint template koji postoji: brochure_golubar.html)
- PMV podsjetnik (Celery task: 7 dana prije roka)

**Verifikacija:** `simulate_borg --modules golubar` → >0/0

**Procjena:** A = 1h, B = 6-8h
**Status:** ⏳ ČEKA CC Code (provjeri scenarij A/B)

---

### P0-C: 3-klik registracija + OIB auto-fill [DAN 2-3]
**Referenca:** CC_TASK_3KLIK_REGISTRACIJA.md ← postoji
**Što:** Novi korisnik od OIB-a do prvog računa za <5 min
**Flow:**
1. `/register/` → unesi OIB → auto-fetch naziv tvrtke (FINA API ili Porezna)
2. Email + lozinka
3. Odaberi tip (paušalac / obrt / d.o.o. / OPG / udruga)
4. Automatski kreirati Company + korisnik + POS terminal + subscription (POS Besplatno)
5. Redirect na onboarding wizard: "Napravite prvi račun →"

**Verifikacija:** registracija od nule do prvog računa < 5 min (ručni test)
**Procjena:** 1 tjedan
**Status:** ⏳ ČEKA CC Code

---

### P0-D: PgBouncer instalacija [DAN 3-4]
**Zašto:** Go-live s 150+ korisnika bez connection poolinga = Django konekcije rastu eksponencijalno.
**PostgreSQL default max_connections = 100. Svaki Gunicorn worker otvara 1+ konekciju.**

```bash
# Instaliraj
apt-get install -y pgbouncer

# Config: /etc/pgbouncer/pgbouncer.ini
[databases]
fina_connect = host=localhost port=5432 dbname=fina_connect

[pgbouncer]
listen_port = 6432
listen_addr = 127.0.0.1
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 200
default_pool_size = 20
min_pool_size = 5
server_idle_timeout = 30
log_file = /var/log/pgbouncer/pgbouncer.log
```

**settings.py update:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'fina_connect',
        'USER': '...',
        'PASSWORD': '...',
        'HOST': '127.0.0.1',
        'PORT': '6432',  # ← PgBouncer port, ne 5432
    }
}
```

**Verifikacija:**
```bash
systemctl start pgbouncer && systemctl enable pgbouncer
psql -h 127.0.0.1 -p 6432 -U fina_user fina_connect -c "SELECT 1;"
```
**Procjena:** 2h
**Status:** ⏳ ČEKA CC Code

---

### P0-E: Load test (150 korisnika) [DAN 4-5 — 10.4.]
**Alat:** locust (pip install locust --break-system-packages)
**Scenarij:**
```python
# /var/www/fina-connect/locustfile.py
from locust import HttpUser, task, between

class LimitConnectUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        self.client.post("/hr/accounts/login/", {
            "username": "testuser", "password": "testpass"
        })
    
    @task(3)
    def dashboard(self):
        self.client.get("/hr/dashboard/")
    
    @task(2)
    def invoice_list(self):
        self.client.get("/hr/invoicing/")
    
    @task(2)
    def pos(self):
        self.client.get("/hr/pos/")
    
    @task(1)
    def experiences(self):
        self.client.get("/hr/experiences/")
    
    @task(1)
    def borg_hub(self):
        self.client.get("/hub/")
```

**Pokretanje:**
```bash
cd /var/www/fina-connect
locust --headless -u 150 -r 10 --run-time 5m --host=https://limit-connect.com
```

**Prihvatljivo:** p95 < 2s, error rate < 1%, bez 500 grešaka
**Ako pada:** Gunicorn workers povećati, Redis cache na dashboard queryje
**Procjena:** 1 dan (install + testiranje + tune)
**Status:** ⏳ ČEKA (preduvjet: PgBouncer mora biti up)

---

### P0-F: REST API stub (Invoicing + POS) [DAN 5-7]
**Zašto:** Channel manager za iznajmljivače (H2.1) treba API.
Externos integratori čekaju.

**Minimalni endpoint set:**
```
GET  /api/v1/invoices/          → lista faktura kompanije
POST /api/v1/invoices/          → kreiranje fakture
GET  /api/v1/invoices/<id>/     → detalj fakture
GET  /api/v1/pos/receipts/      → POS računi
GET  /api/v1/partners/          → partneri
GET  /api/v1/inventory/items/   → artikli
```

**Auth:** Bearer token (API ključ vezan za Company)
**Format:** JSON, paginacija (page/page_size)

**Provjeri postoji li nešto:**
```bash
find /var/www/fina-connect -name "api_views.py" -o -name "api.py" | grep -v venv | head -10
grep -rn "api/v1\|APIView\|ModelViewSet" /var/www/fina-connect/invoicing/ | head -10
```

**Procjena:** 3-5 dana (ovisno o tome što već postoji)
**Status:** ⏳ ČEKA CC Code

---

## ═══════════════════════════════════════════════════════
## VREMENSKI PLAN — TJEDAN PO TJEDAN DO 15.4.
## ═══════════════════════════════════════════════════════

| Dan | Datum | Zadatak | Agent | Est. |
|-----|-------|---------|-------|------|
| 1 | 30.3. (ned) | P0-A: T&C middleware aktivacija | CC Code | 15 min |
| 1 | 30.3. | P0-B: Golubar — provjeri scenarij + deploy | CC Code | 1-8h |
| 2-3 | 31.3.-1.4. | P0-C: 3-klik registracija | CC Code | 1 tjedan |
| 3-4 | 1.4.-2.4. | P0-D: PgBouncer instalacija + config | CC Code | 2h |
| 4 | 2.4. | PropterSoba security (CC_TASK postoji) | CC Code | 2h |
| 5 | 5.4. | **IVAN: Naruči Hetzner CCX33** (89€/mj) | IVAN | - |
| 6-7 | 6.4.-7.4. | P0-E: Load test 150 korisnika | CC Code | 1 dan |
| 7-10 | 7.4.-10.4. | P0-F: REST API stub | CC Code | 3-5 dana |
| 10 | 10.4. | Bug fix buffer — što izađe iz load testa | CC Code | - |
| 11-14 | 11.4.-14.4. | Final verification + FENIX_STATUS update | Sonnet | - |
| 15 | **15.4.** | **GO-LIVE** | SVI | - |

---

## ═══════════════════════════════════════════════════════
## HORIZONT 1 (post go-live, Q2-Q3 2026)
## ═══════════════════════════════════════════════════════

### H1.1 — Beauty Instagram Booking Widget
- CC_TASK_BEAUTY_INSTAGRAM_WIDGET.md ← kreiran, spreman
- Početi NAKON go-live
- Pilot: 1-3 salona u Slavoniji (Ivan identificira)

### H1.2 — Distributor akvizicija (3-5 računovođa)
- Marija = proof of concept. Tražiti njene kolege.
- Brošura za računovođe (analogno Didin Konak brošuri) → Ivan šalje

### H1.3 — Paušalni obrti freemium gateway
- POS Besplatno bez billing provjeke = aktivirati
- "Paušalac Starter" onboarding flow: OIB → tvrtka → prvi račun za 10 min

### H1.4 — Kruljac OPG pilot onboarding
- Ivan kontaktira Ivicu Kruljac
- Farma + kafić + smještaj → full onboarding 4-6 tjedana

### H1.5 — Didin Konak konverzija
- Ivan šalje brošuru Viktoru
- 30-min demo → cilj: plaćajući korisnik do Q2

---

## ═══════════════════════════════════════════════════════
## HORIZONT 2 (Q4 2026 — Q2 2027)
## ═══════════════════════════════════════════════════════

### H2.1 — Channel Manager za iznajmljivače [NAJVEĆA PRIIKA]
- Preduvjet: REST API (P0-F) mora biti stabilan
- iCal sync (Booking + Airbnb + VRBO)
- Direktna rezervacija bez provizije
- 111.000 subjekata potencijal

### H2.2 — QR Traceability na Burzi
- Preduvjet: CardActivity is_public_facing ✅ DONE
- CC_TASK_QR_TRACEABILITY.md (kreirati)

### H2.3 — FSM Policy Export
- CC_TASK_FSM_POLICY_EXPORT.md (kreirati)
- Generira Mermaid.js dijagram iz TRANSITIONS matrica

### H2.4 — SLA Anomaly Report (Celery Z-score)
- CC_TASK_SLA_ANOMALY_REPORT.md ← kreiran, spreman
- Preduvjet: 30+ dana produkcije (dovoljno StatusTimestamp podataka)

### H2.5 — Građevinarstvo normativi materijala
- Nikša Viskovic = pilot
- Bautagebuch, Aufmaß DE obrasci

### H2.6 — OPG EU fond izvještavanje
- Mjera 6.4 format, APPRRR API
- Kruljac OPG = pilot

---

## ═══════════════════════════════════════════════════════
## IVAN — AKCIJE SAMO ZA TEBE
## ═══════════════════════════════════════════════════════

| Datum | Akcija | Hitnost |
|-------|--------|---------|
| **5.4.2026** | Naruči Hetzner CCX33 (89€/mj, Konjik d.o.o.) | 🔴 KRITIČNO |
| Uskoro | Kontaktirati Ivicu Kruljac — demo → pilot | 🟡 VISOKO |
| Uskoro | Poslati brošuru Viktoru (Didin Konak) + zakazati demo | 🟡 VISOKO |
| Uskoro | Identificirati 2-3 računovođe u Slavoniji (30+ klijenata) | 🟡 VISOKO |
| Uskoro | 1 kontakt u HAPIH / Poreznoj za CroXML Verify | 🟢 SREDNJE |
| Horizont 2 | FINA certifikat za produkciju (eRačun posrednik) | 🟢 KAD BUDEMO 50+ plaćajućih |

---

## ═══════════════════════════════════════════════════════
## METRIKE USPJEHA
## ═══════════════════════════════════════════════════════

| Datum | Metrika | Sada | Cilj |
|-------|---------|------|------|
| 15.4. | simulate_borg | 106/106 ✅ | Ostaje 100% |
| 15.4. | T&C consent | 0/77 | 77/77 |
| 15.4. | Load test p95 | - | <2s |
| 15.4. | Plaćajući korisnici | 13 | 13 (stable) |
| 30.6. | Plaćajući korisnici | 13 | 20+ |
| 30.6. | MRR | €2.380 | €4.000+ |
| 30.9. | Plaćajući korisnici | - | 50+ |
| 30.9. | MRR | - | €8.000+ |
| 31.12. | Plaćajući korisnici | - | 150+ |
| 31.12. | MRR | - | €20.000+ |

---
# Zadnje ažuriranje: 2026-03-29 — Sonnet
# simulate_borg: 106/106 (100%) — baseline verified
# Sljedeći korak: CC Code → P0-A T&C middleware (15 min)
