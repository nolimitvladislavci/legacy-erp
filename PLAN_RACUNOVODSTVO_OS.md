# PLAN: Računovodstveni OS — "Novo normalno za mobilizaciju knjigovodstava"
# Kreirao: Sonnet (koordinator) — 2026-04-10
# Naručio: Ivan Brtan
# Status: NA ODOBRENJU

---

## VIZIJA (jednom rečenicom)

LIMIT Connect postaje **operativni sustav za računovodstvo** u kojem:
- računovođa (Marija-model) ima potpunu kontrolu i odgovornost nad 80+ firmi
- svaki komitent ima vlastiti portal pristupa prema platnom planu
- AI nadzire SVE u realnom vremenu i sprječava greške **prije** nego nastanu
- svaka akcija ima digitalni potpis, timestamp, IP — zakonski validan 11 godina

Ovo nije feature — ovo je **nova kategorija proizvoda** za HR tržište.

---

## TKO SU AKTERI

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 0: SUPERADMIN (Ivan + Konjik d.o.o.)                     │
│  Vidi sve, konfigurira sve, billing                             │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 1: RAČUNOVOĐA (Marija-model)                             │
│  1 računovođa → N firmi (komitenti)                             │
│  Puna akcijska ovlast + AI asistent + audit trail               │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: KOMITENT (klijent računovođe)                         │
│  Pristup vlastitim podacima prema platnom planu                 │
│  Može unijeti dokumente, vidjeti stanje — NE može knjižiti      │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3: ZAPOSLENIK komitenta (po timu)                        │
│  Ograničen pristup — POS, unos dokumenata, pregled              │
└─────────────────────────────────────────────────────────────────┘
```

---

## STUP 1: RAČUNOVOĐA PORTAL (Marija-model)

### Što Marija dobiva (novo/prošireno)

**Dashboard računovođe — "Cockpit 80 firmi"**
- Jedna stranica: sve firme, semafor status (zelena/žuta/crvena)
- Crvena = PDV rok za 3 dana / neusklađena knjiženja / blokirana fiskalizacija
- Žuta = čeka dokument od komitenta / neplaćeni stariji od 30 dana
- Zelena = sve OK

**Akcijski panel po firmi (bez mijenjanja kompanije)**
- Marija klikne na komitenta → desni Shell panel
- Direktno unosi knjiženje, generira PDV obrazac, odobrava fakturu
- Nema "switch firma" — sve se radi iz master cockpita
- Svaka akcija: `signed_by=Marija, for_company=X, timestamp=T, ip=I`

**Masovne akcije (batch)**
- PDV-S generiranje za sve firme odjednom (jedan klik → PDF za svaku)
- JOPPD za sve honorarce u jednom prolazu
- Rok podsjetnici — WhatsApp svim komitentima s istim rokom

**AI Proknjižava (proširenje postojećeg)**
- Marija uploada paket dokumenata (zip, email)
- AI razvrstava po firmi → proknjižava → flagira sumnjivo
- Marija pregledava samo flagirane → odobrava jednim klikom
- Target: 90%+ automatizacije rutinskog knjiženja

---

## STUP 2: KOMITENT PORTAL (platni plan)

### Pristup prema PricingPlan.included_modules

```
PAUŠALAC (0 EUR):
  ✓ Pregled vlastitih faktura
  ✓ POS stanje danas
  ✓ PO-SD obrazac (read)
  ✗ Knjiženja, PDV, izvještaji

MICRO (9 EUR):
  ✓ Sve iz Paušalac
  ✓ Arhiva dokumenata (upload)
  ✓ Stanje salda prema dobavljačima
  ✓ AI sažetak tjedni (email)
  ✗ PDV, JOPPD, Konto

STARTER (19 EUR):
  ✓ Sve iz Micro
  ✓ Konto pregled (read-only, bez knjiženja)
  ✓ PDV pregled (ne generira — vidi što je računovođa generirao)
  ✓ Partneri + CRM
  ✓ AI cockpit (jutarnji izvještaj WhatsApp)

PROFESSIONAL (49 EUR):
  ✓ Sve iz Starter
  ✓ Konto s unosom (unosi dokument, računovođa odobrava)
  ✓ PDV-S pregled + download
  ✓ Radni sati
  ✓ AI asistent (Fenix) — pita pitanja, dobiva odgovore
  ✓ Usporedba plan/ostvarenje

ENTERPRISE (149 EUR):
  ✓ Sve bez ograničenja
  ✓ Vlastita računovođa konfiguracija
  ✓ White-label
  ✓ API pristup
  ✓ Multi-firma konsolidacija
```

### Komitent nikad ne vidi:
- Podatke druge firme
- Detalje knjiženja koje nije sam inicirao
- Lozinke/certifikate računovođe
- Billing podatke računovođe

---

## STUP 3: AI NADZOR — "Sprječava greške prije nastanka"

### Razina 1: Real-time validacija (u momentu unosa)

```
KORISNIK UNOSI → AI provjerava ODMAH → blokira ili upozorava
```

Primjeri:
- Faktura s PDV-om za paušalca → blokada + objašnjenje
- Knjiženje na konto koji ne odgovara tipu transakcije → upozorenje
- Datum u prošlosti za fiskalni dokument → zahtijeva potvrdu s razlogom
- Duplikat fakture (isti dobavljač, isti iznos, ±3 dana) → alert

Implementacija: Django signal `pre_save` + `clean()` + Haiku API poziv za semantičku provjeru

### Razina 2: Noćni audit (Gemini)

```
Svake noći 02:00 — Gemini skenira sve knjiženja dana
```

Što provjerava:
- Saldo matematika (dugujna = potrajna)
- PDV konzistentnost (knjiženi PDV vs. obračunati)
- Anomalije iznosa (3σ od prosječne stavke firme)
- Zakonski rokovi koji ističu u 7 dana

Izlaz: `NightlyAuditReport` — Marija dobiva sažetak ujutro

### Razina 3: Compliance watchdog (Gemini, postojeće + prošireno)

- Prati Narodne novine, FINA obavijesti, ePorezi
- Kad se promijeni zakon: automatski kreira `ComplianceWatchItem` za sve pogođene firme
- Marija dobiva: "Promjena Zakona o PDV-u. Pogođeno 23 tvojih klijenata. Klikni za detalje."

### Razina 4: Prediktivna analitika (Sonnet, tjedna)

- Cash flow prognoza 30 dana po firmi
- "Ova firma ide prema blokiranju — neplaćeni 84.000 HRK, rok 15 dana"
- Prijedlog akcije s jednim klikom (pošalji opomenu, blokiraj isporuku)

---

## STUP 4: ONLINE ODGOVORNOST — DIGITALNI POTPIS SVAKE AKCIJE

### Svako knjiženje nosi:

```python
BookingSignature:
  - action_type        # "invoice_create" / "storno" / "pdv_submit" / etc.
  - performed_by       # User (Marija)
  - on_behalf_of       # Company (komitent)
  - client_ip          # za forenziku
  - device_fingerprint # browser/OS
  - timestamp          # UTC, nepromjenjiv
  - data_hash          # SHA-256 stanja podatka u momentu akcije
  - ai_validated       # je li AI prošao provjeru (bool)
  - ai_notes           # što je AI primijetio (ako išta)
  - signature_chain    # hash prethodnog zapisa (blockchain-lite)
```

### Zakonska valjanost:
- 11 godina retencija (Zakon o računovodstvu, ZOR čl. 10)
- Export: XML sa digitalnim potpisom za FINA/poreznu inspekciju
- Read-only view za inspektora (InstitucionalAccess model već postoji)

### Audit trail komitent može vidjeti (po planu):
- Starter+: "Tko je, kad, što napravio na mojim podacima"
- Professional+: puni detalj s IP i device info
- Enterprise: API export audit loga

---

## STUP 5: "MOBILIZACIJA KNJIGOVODSTAVA" — GO-TO-MARKET

### Zašto ovo pobjeđuje Synesis/Minimax/ostale:

```
Konkurencija:       LIMIT Connect:
Desktop-first   →  Mobile-first
Pasivni alat    →  AI asistent 24/7
Računovođa radi →  AI radi, računovođa odobrava
Per-user naplata→  Per-firma naplata
Bez audit trail →  Zakonski validan potpis svake akcije
Bez klijent portal→ Klijent vidi sve u realnom vremenu
```

### Model distribucije:

```
1 Marija (računovođa) → 80 firmi → 80 pretplatnika
Marija plaća: Enterprise plan (149 EUR/mj)
Svaki komitent plaća: 9-49 EUR/mj direktno Limit-u
Marija dobiva: Distributersku proviziju (10-20%)

Matematika:
80 firmi × prosječno 25 EUR/mj = 2.000 EUR/mj prihod od Marijinih klijenata
Marija komisija: 200-400 EUR/mj
Marija trošak za Limit Connect: 149 EUR/mj
Net za Limit: ~1.800 EUR/mj od 1 Marije
```

### Replikacija Marija-modela:
- Svaki računovođa koji vodi 10+ firmi = potencijalni distributor
- HGK procjena: 3.200+ računovodstvenih servisa u HR
- Target Y1: 50 računovođa × 20 firmi prosjek = 1.000 firmi
- Prihod Y1 potencijal: 25.000 EUR/mj od klijentskog sloja

---

## ARHITEKTURA — ŠTO SE GRADI (tehničko)

### Novi modeli:

```python
# Već postoji osnova — proširujemo

AccountantProfile:
  - user (FK) — računovođa
  - managed_companies (M2M Company)
  - distributor_code (str, unique)
  - commission_rate (Decimal)
  - cockpit_preferences (JSONField)

ClientPortalAccess:
  - company (FK)
  - granted_to (FK User) — komitent korisnik
  - access_level (choices: view_only / submit_docs / full_read)
  - plan_snapshot (JSONField) — što je plan dozvoljavao u momentu grant-a

BookingSignature:        # NOVO — digitalni potpis
  - action_type (str)
  - performed_by (FK User)
  - on_behalf_of (FK Company)
  - client_ip (str)
  - timestamp (datetime, auto, nepromjenjiv)
  - data_hash (str, SHA-256)
  - ai_validated (bool)
  - ai_risk_score (0-100)
  - ai_notes (TextField)
  - signature_chain (str) — hash prethodnog

NightlyAuditReport:      # NOVO
  - company (FK)
  - report_date (date)
  - status (ok/warnings/errors)
  - issues (JSONField)
  - generated_by ('gemini')
  - sent_to_accountant (bool)
  - sent_at (datetime)

AccountantCockpitAlert:  # NOVO
  - accountant (FK User)
  - company (FK)
  - severity (red/yellow/green)
  - message (str)
  - action_url (str)
  - resolved (bool)
  - created_at, resolved_at
```

### Nove views/routes:

```
/racunovodja/                     → Accountant cockpit (80 firmi dashboard)
/racunovodja/firma/<id>/          → Brzi panel po firmi (Shell right)
/racunovodja/pdv-batch/           → Masovni PDV-S
/racunovodja/joppd-batch/         → Masovni JOPPD
/portal/                          → Komitent portal (per plan)
/portal/dokumenti/                → Upload dokumenata
/portal/stanje/                   → Konto pregled (read)
/portal/ai-cockpit/               → AI jutarnji izvještaj
/audit/trail/                     → Audit log (per firma, per plan)
/audit/export/                    → XML export za inspekciju
```

---

## REDOSLJED IMPLEMENTACIJE

### FAZA 0 — Odmah nakon 15.04. (CC Code, 3-5 dana)
- BookingSignature model + migration
- Hookati na sve postojeće `save()` akcije (signal post_save)
- AccountantCockpitAlert model
- Basic accountant dashboard (lista firmi + semafor)

### FAZA 1 — Tjedan 1 (CC Code + Gemini, 1 tjedan)
- Accountant cockpit — full Shell panel per firma
- ClientPortalAccess model + per-plan gating
- Komitent portal basic (Starter: konto read, fakture)
- NightlyAuditReport — Gemini task

### FAZA 2 — Tjedan 2 (sve trojstvo, 1 tjedan)
- AI real-time validacija u unos (Razina 1)
- Masovni PDV-S i JOPPD batch
- Distributor model + komisija tracking
- WhatsApp integration za alert/cockpit

### FAZA 3 — Tjedan 3-4 (Sonnet + Gemini)
- Compliance watchdog proširenje (HR + DE zakoni)
- Prediktivna analitika (cash flow 30 dana)
- Audit XML export (FINA format)
- Go-to-market materijali (landing page za računovođe)

---

## TASK FAJLOVI ZA TIM

Po završetku plana generirati:
- `CC_TASK_BOOKING_SIGNATURE.md`       — digitalni potpis svake akcije
- `CC_TASK_ACCOUNTANT_COCKPIT.md`      — računovođa dashboard + Shell
- `CC_TASK_CLIENT_PORTAL.md`           — komitent portal per platnom planu
- `GEMINI_TASK_NIGHTLY_AUDIT.md`       — noćni audit svih knjiženja
- `GEMINI_TASK_COMPLIANCE_EXPANSION.md` — proširenje watchdog-a

---

## MJERILA USPJEHA (KPI)

```
Y1 ciljevi:
✓ 50 računovođa aktivnih (Marija-model)
✓ 500+ komitenata s portal pristupom
✓ 90%+ automatizacija rutinskog knjiženja (AI)
✓ <0.1% greška u knjiženjima (AI nadzor)
✓ 25.000 EUR/mj MRR od klijentskog layera
✓ 0 uspješnih inspekcijskih nalaza (audit trail)

Kratkoročno (30 dana):
✓ Marija: 80 firmi u cockpitu, sve zelene
✓ BookingSignature: svaka akcija potpisana
✓ Noćni audit: 0 neotvorenih upozorenja
```

---

## ODOBRAVA: Ivan Brtan
## IZVRŠAVA: CC Code (Faza 0-1) + Gemini (Audit) + Sonnet (koordinacija)
## PILOT: Marija Brtan — Konjik d.o.o. — 80 firmi
