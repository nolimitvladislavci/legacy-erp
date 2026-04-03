# FENIX STATUS — Koordinacijski fajl
# Zadnje azuriranje: 2026-04-03 — Sonnet (Notariat asimilacija + Gemini pravila)
# Git HEAD: 11c8ebec
# PRAVILO: Ako nesto pise DONE — NE RADIS PONOVO.

---

## ════════════════════════════════════════════════════════
## ★ GEMINI PROTOKOL — ZABETONIRAN 03.04.2026.
## ════════════════════════════════════════════════════════

### PRAVILA PISANJA GEMINI TASK FAJLOVA (nepromjenjivo)

**ZABRANA 1 — Nema code fences:**
Task fajl ne smije sadrzavati ni jedan backtick blok (```).
Gemini ih cita kao Python kod i pada na SyntaxError.
Umjesto toga: opisati sto treba napisati rijecima, Gemini zna sam.

**ZABRANA 2 — Zasticeni fajlovi (NIKAD WRITE):**
- templates/base.html → 914 linija, sidebar, topbar, FAB, sve. Gemini ga je pregazio na 63 linije.
- core/settings.py → bez READ provjere nikad ne pisati
- core/urls.py → samo append na kraj, nikad replace cijelog fajla
- companies/module_registry.py → samo append, nikad replace
- .env → nikad

**ZABRANA 3 — Nema pretpostavki o field imenima:**
UVIJEK READ models.py PRIJE WRITE bilo kojeg koda.
Poznate greske iz proslosti: grand_total vs total, PaymentMethod vs Method.

**ZABRANA 4 — Nema paralelnih Gemini instanci na istom fajlu:**
Ako jedan Gemini task pise core/settings.py, drugi ne smije istovremeno.

---

### FORMAT GEMINI TASK FAJLA (jedini prihvatljiv)

```
GEMINI TASK: Naziv taska
Datum: DD.MM.YYYY. Rok: DD.MM.YYYY.
PRAVILO: Ne pisi nijedan code block s backtickovima.

KORAK 1 - Opis akcije
READ: /var/www/fina-connect/putanja/do/fajla.py

KORAK 2 - Opis sto treba napisati (prose, bez backtick)
WRITE: /var/www/fina-connect/putanja/do/novog_fajla.py
Sadrzaj: [opis sadrzaja rijecima]

KORAK 3 - Provjera
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -5

DONE kriterij:
- fajl X postoji
- check prolazi bez ERROR
```

---

### GEMINI AGENT — TEHNICKE NAPOMENE

- Django setup traje 60-90 sekundi (50+ apps) — normalno, ne panic
- Pokretanje: ./gemini_run.sh IME_TASKA broj_koraka
- Pracenje: tail -f gemini_IME_TASKA.log
- Ako task pada odmah — provjeri je li task fajl bez backtick blokova
- Max koraka: 25 za srednji task, 40 za veliki
- Gemini smije: READ, WRITE, EXEC, QUERY, DONE
- Gemini NE smije: pisati zasticene fajlove (lista gore)
- Nakon svakog Gemini taska: provjeri wc -l templates/base.html → mora biti 914

---

### TEAMWORK PROTOKOL — TIM OD TROJICE

| Agent | Uloga | Ogranicenja |
|-------|-------|-------------|
| Sonnet | Arhitekt, koordinator, reviewer | Ne implementira sam ako moze delegirati |
| Gemini | Executor — pise kod, pokrece migracije | Ne smije pisati zasticene fajlove |
| CC Code | Executor — kompleksni algoritmi, testovi | Pokrece Ivan rucno s terminala |
| Haiku | Classifier, brze provjere | Inline pozivi, ne autonomno |

**Komunikacija u timu:**
- Sonnet → Gemini: pise GEMINI_TASK_XXX.md, pokrece gemini_run.sh
- Gemini → Sonnet: rezultat u logu, git commit
- CC Code → Sonnet: Ivan kaze "CC Code je gotov", Sonnet reviewira commit
- Sonnet → Ivan: samo kad treba odluka ili novac

---

## ════════════════════════════════════════════════════════
## ★ DEPLOYAN 03.04.2026. — SJEDNICA (Sonnet + Ivan + Gemini)
## ════════════════════════════════════════════════════════

### Git commitovi danas:

| Commit | Sto | Tko |
|--------|-----|-----|
| a466f711 | fix: TemplateSyntaxError base.html (zagrade u if tagu) | Sonnet |
| a466f711 | fix: celery core.tasks autodiscover (backup nije radio od 02:00) | Sonnet |
| 3b78d6da | security: _bypass URL onemogucen, ALLOWED_IPS za _dev, Nginx 403, token rotacija | Sonnet |
| f68f31d8 | ops: gemini_run.sh + gemini_watch.sh + HRVOJE_ONBOARDING.md | Sonnet |
| 02e4de28 | feat(ui): dark/light tema polish + 2-way switcher + pdf_utils (Gemini) | Gemini |
| 11c8ebec | feat(notariat): tarifa + dimnjacari + admin + PDF predlosci | Sonnet+Gemini |

### Novo deployan danas:

**NOTARIAT APP — POTPUNA ASIMILACIJA:**
- notariat/ Django app s 3 modela (PravniPredmet, DimnjacarskaInspekcija, NotariatPredlozak)
- Migracija 0001_notariat_init primijenjena
- CroValidator API: /api/v1/validate/ (OIB+IBAN+MBS)
- Tarifa kalkulator: notariat/tarifa.py (punomoc, osnivanje, zaduznica, dimnjak...)
- 2 PDF predloska: potvrda_dimnjaka.html + punomoc.html
- 2 dashboarda: /notariat/pravnik/ + /notariat/dimnjacari/
- Admin registracija sva 3 modela
- Module registry: odvjetnik + biljeznik + dimnjacari (kategorija pravne_usluge)
- BusinessType: ODVJETNIK + BILJEZNIK + DIMNJACARI dodani u Company model

**UI REVOLUTION (Gemini Sprint 1+2):**
- global_themes.css: kompletne CSS varijable za obje teme
- base.html: 2-way theme switcher (tamno/svjetlo)
- core/pdf_utils.py: globalni PDF template registry

**SECURITY SPRINT:**
- /_bypass/ URL onemogucen (Seki bypass je bio javno dostupan)
- /_dev/exec/ blokiran na Nginx razini (samo 127.0.0.1)
- ALLOWED_IPS za remote_api.py
- DEV_API_TOKEN rotiran
- Nginx blokira wp-admin, .env, phpmyadmin skenere (return 444)
- Dva MCP servisa na istom portu — fenix-mcp.service treba gasiti

**BUGS FIKSIRANI:**
- TemplateSyntaxError na svakom 404 (zagrade u Django template if tagu)
- core.database_backup nije radio od 02:00 (celery autodiscover fix)
- AppRegistryNotReady — prolazna greska, sustav stabilan

---

## ════════════════════════════════════════════════════════
## ★ NOTARIAT — STANJE ASIMILACIJE
## ════════════════════════════════════════════════════════

| Komponenta | Status | URL / Lokacija |
|-----------|--------|---------------|
| PravniPredmet model | ✅ LIVE | notariat/models.py |
| DimnjacarskaInspekcija model | ✅ LIVE | notariat/models.py |
| NotariatPredlozak model | ✅ LIVE | notariat/models.py |
| CroValidator API | ✅ LIVE | /api/v1/validate/ |
| Tarifa kalkulator | ✅ LIVE | notariat/tarifa.py |
| PDF potvrda dimnjaka | ✅ LIVE | notariat/templates/notariat/pdf/ |
| PDF punomoc | ✅ LIVE | notariat/templates/notariat/pdf/ |
| Odvjetnicki dashboard | ✅ LIVE | /notariat/pravnik/ |
| Dimnjacari dashboard | ✅ LIVE | /notariat/dimnjacari/ |
| Admin | ✅ LIVE | /admin/notariat/ |
| Module registry | ✅ LIVE | odvjetnik + biljeznik + dimnjacari |
| BusinessType choices | ✅ LIVE | Company.BusinessType.ODVJETNIK/BILJEZNIK/DIMNJACARI |
| WeasyPrint generate_pdf view | ⏳ FALI | CC Code sprint |
| Ostali PDF predlosci (8) | ⏳ FALI | CC Code sprint |
| Sidebar linkovi aktivni | ⏳ FALI | Ovisi o company.enabled_modules |

**Pilot korisnik:** Simasek (biljeznik, Osijek) — demo 22.04. post-Uskrs
**Rok kompletne asimilacije:** 10.04.2026.

---

## ════════════════════════════════════════════════════════
## ★ RATNI RASPORED — DO GO-LIVE 15.04.2026.
## ════════════════════════════════════════════════════════

| Dan | Datum | Zadatak | Odgovorni | Status |
|-----|-------|---------|-----------|--------|
| 0-7 | 25.3-01.4 | Sve prethodne sesije | Sonnet+CC+Gemini | ✅ DONE |
| 8 | 03.4. | Notariat asimilacija + Security sprint + UI teme | Sonnet+Gemini | ✅ DONE |
| 9 | 04-05.4. | **Hrvoje vikend** — notariat PDF views + DRON2 onboarding | Hrvoje+CC | 🔴 VIKEND |
| 10 | 05.4. | **IVAN: Narudi Hetzner CCX33** — 89 EUR/mj | **IVAN** | 🔴 CEKA |
| 11 | 07.4. | Invoice mapping dijagnoza (synesis_compare > 95%) | CC Code | ⏳ |
| 12 | 08.4. | **Marija: Full uskladenje pregled** | **Marija** | ⏳ |
| 13 | 09.4. | Redis warm_cache + audit cleanup aktivacija | CC Code | ⏳ |
| 14 | 10.4. | Notariat kompletno (PDF views + predlosci) | CC Code | ⏳ |
| 14 | 10.4. | MARIJA_BLAGOSLOV.md popunjen | Marija | ⏳ |
| 15 | 12.4. | Final load test na CCX33 | Sonnet+CC | ⏳ |
| 17 | 14.4. | DNS cutover priprema (03:00) | Sonnet | ⏳ |
| 18 | 15.4. | **GO/NO-GO odluka** | Ivan + Marija | ⏳ |
| 18 | 15.4. | **PRODUKCIJA — 0-downtime** | Sonnet+CC | ⏳ |

---

## ════════════════════════════════════════════════════════
## ★ TASKOVI ZA VIKEND (Hrvoje + CC Code)
## ════════════════════════════════════════════════════════

### P1 — NOTARIAT KOMPLETIRANJE (rok 10.04.)
Fajl: CC_TASK_BLAGDANSKI_SPRINT_NOTARIAT.md
- generate_dimnjak_pdf view + URL
- generate_punomoc_pdf view + URL
- Preostalih 8 WeasyPrint predlozaka
- Tarifa kalkulator u UI (forma s izracunom uzivo)

### P2 — DRON2 ONBOARDING WIZARD (rok 10.04.)
Fajl: CC_TASK_DRON2_ONBOARDING_WIZARD.md
- 3 polja registracija (OIB → auto-fill → paket)
- Ne 12 polja. Tri.

### P3 — DRON3 CSS KIRURGIJA (rok 12.04.)
Fajl: CC_TASK_DRON3_CSS_KIRURGIJA.md
- CSS token fix — bez diranja HTML predlozaka

### P4 — SYNESIS INVOICE MAPPING (rok 07.04.)
Fajl: CC_TASK_USKLADENJE_A.md
- SYN-IRA-xxx → XINVOICESB-xxx mapping
- Target: OK% > 95% (sad 0.9%)

---

## ════════════════════════════════════════════════════════
## ★ BORG FENIX — ASIMILIRANI SEGMENTI (azurirano 03.04.)
## ════════════════════════════════════════════════════════

```
LIMIT Connect Borg (03.04.2026):
  ├── Invoicing (eRacun, fiskalizacija, PO-SD auto-fill)
  ├── POS (QuickActions, DSFinV-K, timer, waiter shifts, offline 48h)
  ├── Konto (EUR, DATEV, JournalEntry, LedgerLine, D=P verificirano)
  ├── Worktime (sati, ArbZG, EU fondovi, JOPPD, /mine/)
  ├── Rental (Property.owner, Booking, Meldeschein)
  ├── Tax Wizard (PO-SD/DOH/EUR/AnlageV/UStVA/JOPPD + widget)
  ├── Udruge (9 segmenata: DVD/KUD/Ribolov/Pcelari/Rakija/Vocari/Branitelji/Lov/Zadruge)
  ├── Arhiva (49/49 testova zelenih, integrity hash, ZOR compliance)
  ├── Transport (CMR, putni nalog PDF)
  ├── BORG Ops (FSMMixin, CardActivity, SLA, dispatch, GPS, Kanban)
  ├── Seasonal (SeasonalWorker, Contract, Payment, HZMO alerts)
  ├── Notariat ← NOVO (Biljeznik + Odvjetnik + Dimnjacari)
  └── AI (Gemini patrol, Haiku classifier, BORG signal, RAG)
```

---

## ════════════════════════════════════════════════════════
## ★ PROJEKTI U PIPETTU — IZVAN LIMIT CONNECT
## ════════════════════════════════════════════════════════

### MEMIO (bivsi naziv: MNEMIO / AION)
- Digitalna riznica obiteljske bastine
- Kriptografski zasticeno, Platform Covenant SHA-256
- Domena: memio.hr SLOBODNA — registrirati odmah
- memio.com istice 20.06.2026. — backorder na GoDaddy
- Euipo TMview provjera: MEMIO trademark
- Konzorcij: NO LIMIT udruga (nositelj) + Konjik d.o.o. (tech) + Marija Cacic (voditeljica)
- EU fondovi: Creative Europe (100-500k EUR) — treba konzorcij s muzejom
- Muzej Slavonije, Osijek — potencijalni konzorcijski partner
- Pismo namjere PDF: generiran 03.04.2026. (AION_Pismo_Namjere_2026.pdf)
- Status: IDEJA → PLAN. Ceka Mariju Cacic da potvrdi.

### TROJKA PRSTEN (buduca arhitektura)
- Portal 1: LIMIT Connect (posao, zakon, sadašnjost)
- Portal 2: sati (covjek, tijelo, trenutak)
- Portal 3: MEMIO (obitelj, uspomena, buducnost)
- Infrastruktura: jedan Hetzner CCX33, tri Django projekti, zajednicki Redis+AI
- Tesla 3-6-9: 3 portala, 6 infrastrukturnih slojeva, 9 = autonomni API ekosustav

---

## ════════════════════════════════════════════════════════
## ★ INFRASTRUKTURA — STANJE 03.04.2026.
## ════════════════════════════════════════════════════════

### Server: Hetzner 37.27.248.86 (ubuntu-8gb-hel1-1)

| Servis | Status | Napomena |
|--------|--------|----------|
| gunicorn-fina | ✅ active | 6 workera, 2 threada |
| celery-worker | ✅ active | queue: default, heavy |
| celery-worker-pos | ✅ active | queue: pos |
| celery-beat | ✅ active | schedules: backup, test, ai_health |
| fenix-mcp | ⚠️ DUPLIKAT | Gasiti — mcp-fina ga zamjenjuje |
| mcp-fina | ✅ active | :8765, Claude pristup |
| nginx | ✅ active | SSL, security blokovi |
| postgresql | ✅ active | PgBouncer aktivan |
| redis | ✅ active | |

### Backup:
- DB: svaki dan 05:00 → /var/backups/limit-connect/db_YYYYMMDD.sql.gz
- Zadnji: db_20260403.sql.gz (96MB) ✅
- Media: svaki dan → /var/backups/limit-connect/media_YYYYMMDD.tar.gz

### HITNA AKCIJA — fenix-mcp gasiti:
```bash
systemctl stop fenix-mcp
systemctl disable fenix-mcp
```
Uzrok: dva servisa na portu :8765 → Errno 98 svakih 8 sekundi u lagu.

---

## ════════════════════════════════════════════════════════
## ★ SECURITY — STANJE 03.04.2026.
## ════════════════════════════════════════════════════════

| Vektor | Prije | Nakon |
|--------|-------|-------|
| /_bypass/ | ⚠️ Javno dostupno | ✅ URL onemogucen |
| /_dev/exec/ | ⚠️ Samo Bearer token | ✅ Nginx 403 + ALLOWED_IPS=localhost |
| DEV_API_TOKEN | ⚠️ Kompromitiran | ✅ Rotiran |
| wp-admin skeneri | ⚠️ Django obraduje | ✅ Nginx return 444 |
| S3_SECRET_KEY hardcoded | ⚠️ Fallback u settings.py | ⏳ Treba u .env |

### Hrvoje testira vikend — moze probati:
- SQL injection na formama (zastiteno Django ORM-om, ali provjeri)
- IDOR na API endpointima (CompanyManager stiti, ali edge caseovi)
- Brute force login (nema rate limitinga — treba django-axes)
- XSS u text inputima
- JWT/session hijacking

### Sljedeci security korak (post-Uskrs):
- django-axes (brute force protection)
- Rate limiting na Nginx (login endpoint max 5/min)
- S3_SECRET_KEY premjestiti iz settings.py u .env

---

## ════════════════════════════════════════════════════════
## ★ CLAUDE.AI MAX PLAN
## ════════════════════════════════════════════════════════
Placeno: 01.04.2026. | Istice: ~01.05.2026.
Automatska naplata: UKLJUCENA (27.04.2026) ← azurirano
Kartica: Mastercard 8859
Cijena: ~107 EUR/mj

### Kada limit udari:
1. Pricekaj reset sessiona (5h)
2. Gemini preuzima: ./gemini_run.sh IME_TASKA 25
3. CC Code na terminalu: claude
4. Ne placaj 5 EUR extra — nije isplativo

---

## ════════════════════════════════════════════════════════
## ★ STANJE BILANCE — VERIFICIRANO 02.04.2026.
## ════════════════════════════════════════════════════════

```
Konjik d.o.o. — Konto uskladenje:
  JournalEntry:    12,840 (svi posted=True)
  LedgerLine:      50,669
  Debit (D):    7,268,444.16 EUR
  Credit (C):   7,268,444.16 EUR
  D-P diff:             0.00 EUR  PERFEKTNO
  KontoAccount:       563 konta (2,514 ispravljeno)
  Test suite:      17/17 PASS

Synesis compare (zadnji, 02.04.):
  OK (0.02EUR):   7 od 772  (0.9%) — PROBLEM, treba >95%
  Uzrok: invoice mapping kriv (prefiks/PDV)
  Sljedeci korak: CC_TASK_USKLADENJE_A.md (Dron #1 DONE, sad mapping)
```

---

## ════════════════════════════════════════════════════════
## ★ SONNET PROTOKOL — VODJA PROJEKTA
## ════════════════════════════════════════════════════════

Sonnet se poziva svaka 2h iz Celery beat taska (core.sonnet_cycle).
Svaki poziv dobiva: FENIX_STATUS + git log + system test + aktivni Gemini taskovi.

### Duznosti (nepromjenjivo):
1. Cita FENIX_STATUS, git log, system test na pocetku svake sesije
2. 500 greske, pravni rizici, security propusti = ODMAH akcija
3. Pise GEMINI_TASK fajlove, pokrece gemini_run.sh
4. WhatsApp Ivanu SAMO za: kritican bug, odluka/novac/certifikat, milestone

### Sto Sonnet NE smije:
- Pitati za odobrenje tehnickih odluka
- Pisati zasticene fajlove (base.html, .env) bez Ivana
- Implementirati bez testiranja
- Krsiti zakonske okvire (fiskalizacija, GDPR, ZOR, ArbZG)

### Eskalacijska matrica:
| Situacija | Akcija |
|-----------|--------|
| 500 u produkciji | ODMAH Gemini fix + WhatsApp Ivan |
| Pravni rizik | ODMAH Gemini fix + WhatsApp Ivan |
| Gemini pregazio base.html | Odmah: git show COMMIT:templates/base.html > templates/base.html |
| Gemini task zaglavljen >4h | Kill PID, restart, novi task |
| Manji bug | Gemini fix, bez WhatsAppa |
| Novi feature live | Verificiraj testove, azuriraj STATUS |

---

## ════════════════════════════════════════════════════════
## ★ IVAN — JEDINE HITNE AKCIJE
## ════════════════════════════════════════════════════════

| # | Akcija | Rok | Napomena |
|---|--------|-----|----------|
| 1 | **Narudi Hetzner CCX33** (89 EUR/mj) | 05.04. | setup_new_server.sh spreman |
| 2 | **memio.hr registracija** (10-15 EUR/god) | Odmah | Slobodna domena, moze nestati |
| 3 | Gasiti fenix-mcp.service | Odmah | Errno 98 log spam |
| 4 | Marija Cacic — potvrda za MEMIO | Ovaj tjedan | Pismo namjere PDF spreman |
| 5 | EUIPO TMview provjera — MEMIO trademark | Ovaj tjedan | euipo.europa.eu/eSearch |

---

## ════════════════════════════════════════════════════════
## ★ UDRUGE SEGMENT MAPA (26.03.2026. — live)
## ════════════════════════════════════════════════════════

| Segment | Modeli | URL | Status |
|---------|--------|-----|--------|
| DVD (vatrogasci) | VatrogasnaOprema, Vozilo, Intervencija, Vjezba, Zvanje | /udruge/dvd/ | ✅ |
| KUD | Repertoar, ProbaLog, Kostim, NastupPlan | /udruge/kud/ | ✅ |
| Ribolov | Revir, RibolovnaDozvola, UlovEvidencija | /udruge/ribolov/ | ✅ |
| Pcelari | Pcelinjak, Kosnica, TretmanKosnice, MedProizvodnja | /udruge/pcelari/ | ✅ |
| Rakija | DestilacijaKotao, DestilacijaLog, TrosarinaPrijava | /udruge/rakija/ | ✅ |
| Vocari | Vocnjak, BerbaLog, TretmanVocnjaka | /udruge/vocari/ | ✅ |
| Branitelji | StatusBranitelja, OdlikovanjeBranitelja | /udruge/branitelji/ | ✅ |
| Lov | Loviste, LovackaIskaznica, DopustenjeLova, Trofej | /udruge/lov/ | ✅ |
| Zadruge | Zadrugar, ZadruznRevizija | /udruge/zadruge/ | ✅ |

Nitko u HR nema ovo. 9 dashboardova, svi zakonski kompatibilni.

---

## ════════════════════════════════════════════════════════
## ★ AI INFRASTRUKTURA PRAVILA — ZABETONIRAN 27.03.2026.
## ════════════════════════════════════════════════════════

Svaki novi AI kljuc: dodaj u .env + settings.py + ai_health.py.
Celery beat: ai_health_check svaki sat u :15, sonnet_cycle svaka 2h, run_system_test 02:00+07:30.
GeminiAgent v2: ako files_written=0 i commands_run=0 → WhatsApp upozorenje.
