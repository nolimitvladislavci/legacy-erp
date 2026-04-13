# FENIX_MASTER_PLAN_15_APRIL.md
# Status: AKTIVAN — Ivan Brtan odobrio 30.03.2026.
# Koordinator: Sonnet | Executor: 2× CC Code | Revisor: Gemini
# Rok: 15.04.2026. — FIKSAN
# Zadnje ažuriranje: 30.03.2026. 23:35 | git: 69da6edd

---

## VERIFIKACIJA — STANJE NA SERVERU UPRAVO SAD

| Komponenta | Status |
|---|---|
| Server | Hetzner CCX13 4/8GB, uptime 13 dana, load 0.13 ✓ |
| Baza | PostgreSQL 16, 866MB, 15.327 faktura, 33.299 partnera ✓ |
| FAL | 68 permissions, 6 rola, 38 UserRoles ✓ |
| Superuseri | Točno 3: ivan, dragan, superadmin ✓ |
| MRR | 2.438 EUR (14 plaćajućih) |
| Ghost firme | 71 Konjik klijent — ima podatke, nema pristup |
| Mandate model | POSTOJI u bazi, 0 zapisa ✓ |
| SmartEntry /pocni/ | NE POSTOJI — gradi CC #1 |
| Claim Your Business | NE POSTOJI — gradi CC #1 |
| WhiteLabel model | NE POSTOJI — gradi CC #2 |
| LicenseToken | NE POSTOJI — gradi CC #2 |
| Mandate wire | NE POSTOJI — gradi CC #2 |

---

## SERVERI — AKCIJA IVAN 01.04.

```
SERVER 1 — Ivan (postoji: 37.27.248.86)
  Ostaje kao: Redis + Celery workers
  Trošak: 51 EUR/mj (već plaća)

SERVER 2 — Marija (naručiti: Hetzner CCX33)
  Postaje: Nginx + Gunicorn (App layer)
  Trošak: 131 EUR/mj
  Narudžba: 01.04. → isporuka isti dan

SERVER 3 — Kruljac (naručiti: Hetzner CCX33)
  Postaje: PostgreSQL dedicated
  Trošak: 131 EUR/mj
  Narudžba: 01.04. → isporuka isti dan

UKUPNO: 313 EUR/mj = 0.2% ciljanog MRR-a
KAPACITET: 3.000+ firmi, 720 simultanih korisnika
```

---

## TRACK A — "ODIJELO" (CC Code #1)
### Svaki zadatak je nezavisan i deployable sam

---

### A1. Claim Your Business ← POČNI ODMAH
**Task:** CC_TASK_CLAIM_YOUR_BUSINESS.md
**Rok:** 02.04.

71 Konjikova klijenta ima fakture, partnere i journale — ali nema pristup.
Svaki vlasnik koji pokuša registraciju udari u zid (OIB postoji → dead end).

**Što graditi:**
- `CompanyClaimRequest` model (registration/models.py)
- `/firma/preuzmi/<id>/` — vlasnik traži pristup (PUBLIC)
- `/firma/aktiviraj/<token>/` — vlasnik klikne link, postavi lozinku (PUBLIC)
- `/firma/odobri/<id>/` — Marija odobrava iz WhatsApp linka (LOGIN)
- `/firma/zahtjevi/` — Marija vidi sve pending zahtjeve (LOGIN)
- `bulk_invite_ghost_firms` management command — batch za sve 71
- OIB lookup fix: "Firma postoji" → can_claim=True za firme bez vlasnika

**Kritični detalj:** novi User se veže na POSTOJEĆU firmu — vlasnik odmah vidi sve stare podatke.

**MRR potencijal:** 71 × 55 EUR = +3.905 EUR/mj

---

### A2. SmartEntry /pocni/ ← ODMAH NAKON A1
**Task:** CC_TASK_SMART_ENTRY_I_POSREDNIK.md (Faza A)
**Rok:** 04.04.

Jedina ulazna točka. Email → detect → pravi flow, bez greške.
?ref=REF-MARIJA-2026 automatski veže klijenta uz agenta.

**Što graditi:**
- `detect_email` API — NEW_USER ili EXISTING_USER (PUBLIC)
- `smart_entry_magic` API — šalje magic link (PUBLIC)
- `smart_entry_page` view — render stranice (PUBLIC)
- `/pocni/` URL (bez i18n prefiksa — WhatsApp linkovi!)
- `MagicToken` tip 'entry' dodan
- Template: email → stanje → akcija = MAX 3 klika

---

### A3. Agent Dashboard ← ODMAH NAKON A2
**Task:** CC_TASK_SMART_ENTRY_I_POSREDNIK.md (Faza B+C)
**Rok:** 07.04.

Marija i Kruljac vode klijente. Trebaju vidjeti SVOJE firme i slati invite linkove.

**Što graditi:**
- Seed: Marija (REF-MARIJA-2026) i Kruljac (REF-KORPAŠ-2026) kao agenti
- `/moji-klijenti/` — lista klijenata, zarada, invite linkovi
- Copy-to-clipboard invite URL
- Sidebar badge samo za agente (context processor `user_is_agent`)
- `AgentReferral` + `CompanySubscription.referral` FK
- `register_step4` auto-kreira AgentReferral iz ref koda

---

### A4. FAL Faza 4 + Redis Caching
**Task:** CC_TASK_FAL_FENIX_ACCESS_LAYER.md (Faza 4)
**Rok:** 10.04.

AccessAuditLog — svaki GRANT/DENY se logira.
Redis caching — permissions, WhiteLabel, session iz Redis (hit rate: 52% → 95%+).
Audit log fix — isključiti konto.LedgerLine (806k redaka/mj za 14 klijenata!).

---

## TRACK B — "KRUNA" (CC Code #2)
### Posrednička infrastruktura

---

### B1. Server Migracija 3-node ← POČNI ODMAH (čeka IP adrese)
**Task:** CC_TASK_SERVER_MIGRACIJA_3NODE.md
**Rok:** 08.04. (ovisi o narudžbi Marija+Kruljac: 01.04.)

Ansible playbooks za 3-node setup.
Zero downtime migracija baze.
Jedine promjene u kodu: 3 env varijable (DB_HOST, REDIS_URL, ALLOWED_HOSTS).

**Što graditi:**
- `ansible/inventory/production.ini` (placeholder, Ivan popunjava IP-ove)
- `ansible/playbooks/setup_db.yml` — PostgreSQL + PgBouncer na Server 3
- `ansible/playbooks/setup_app.yml` — Nginx + Gunicorn na Server 2
- `ansible/playbooks/setup_cache.yml` — Redis + Celery na Server 1
- `zero_downtime_db_migration.sh` — pg_dump → scp → pg_restore
- `.env.production.template`

---

### B2. Mandate Wire + Posrednički UI ← KLJUČNI TASK
**Task:** CC_TASK_POSREDNIK_MANDATE_WIRE.md
**Rok:** 05.04.

`Mandate` model POSTOJI (einvoice/models/mandate.py) — nikad nije spojen.
Ovo je TEHNIČKA PODRŠKA za 30+ distributera pod jednim certifikatom.

**Arhitektura:**
```
Konjik d.o.o. (registrirani posrednik) — JEDAN certifikat
    ↓ Mandate (punomoć)
71 Konjik klijenata + klijenti svakog distributera
    ↓
Konjik šalje e-račune ZA SVE s jednim certifikatom
Distributer iz Splita = prodajni agent, NE treba vlastiti ISO 27001
```

**Što graditi:**
- Wire: `PosrednikService.get_config()` provjerava aktivan Mandate
- Wire: `send()` prosljeđuje `on_behalf_of_oib` u UBL XML
- View: `/eracun/mandati/bulk-umbrella/` — jednim klikom za sve 71
- URL registracija mandata u `eracun/urls.py`
- Mandate stats badge u agent dashboardu

---

### B3. WhiteLabel Engine
**Task:** CC_TASK_LICENSING_ENGINE.md
**Rok:** 05.04.

Svaki distributer ima vlastiti brand i URL.
`konjik.limit-connect.com`, `korpas.limit-connect.com`, `split.limit-connect.com`

**Što graditi:**
- `WhiteLabelConfig` model (company, brand_name, subdomain, fiscal_system)
- `WhiteLabelMiddleware` — detektira brand iz domene
- Context processor (WL_NAME, WL_LOGO, WL_PRIMARY u svim templateovima)
- CSS override u base.html
- `CompliancePackage` seed: HR/DE/AT/SI

---

### B4. LicenseToken + Heartbeat
**Task:** CC_TASK_LICENSING_LEGAL_SHIELD.md (Dio A)
**Rok:** 08.04.

JWT-based license za WhiteLabel korisnike.
Ne plati → grace → read-only → suspended. GDPR compliant — podaci uvijek dostupni.

**Što graditi:**
- `LicenseToken` model (status, valid_until, heartbeat)
- `LicenseCheckMiddleware` — samo za WhiteLabel firme
- Celery beat: provjera svakih 6h
- Sidebar warning
- 402 Payment Required (ne 403)
- WhatsApp alert na degradaciju

---

### B5. Distributer Onboarding + Pricing
**Rok:** 12.04.

- `/postani-distributer/` landing stranica
- Kalkulator: koliko firmi × cijena = zarada
- Pricing stranica: Distributer track odvojen od SaaS tracka
- Ivan odobrava iz cockpita → auto-setup (subdomain + WhiteLabel + InviteCode)

---

## VREMENSKI PLAN

```
DAN        TRACK A (CC #1)                  TRACK B (CC #2)
──────────────────────────────────────────────────────────────
31.03 pon  A1: CompanyClaimRequest model    B1: Ansible struktura
01.04 uto  A1: Views + URLs                 B1: App server setup (čeka IP)
           ← IVAN: Naruči Server 2 + Server 3 →
02.04 sri  A1 ✓ + bulk_invite pokretanje    B1: DB server setup
           A2: SmartEntry detect-email      B2: Mandate wire start
03.04 čet  A2: /pocni/ URL + template       B2: PosrednikService.get_config()
           ← MARIJA: Šalje invite svim 71 firmama →
04.04 pet  A2 ✓                             B2: Mandate bulk-umbrella view
05.04 sub  A3: Agent seed (Marija/Kruljac)  B2 ✓ + B3: WhiteLabel model
06.04 ned  A3: /moji-klijenti/ view         B3: Middleware + context proc.
07.04 pon  A3 ✓ + invite linkovi            B3 ✓ + base.html integracija
08.04 uto  A4: AccessAuditLog               B1 ✓: DB migracija live
           ← 3-server arhitektura aktivna →
09.04 sri  A4: Superadmin dashboard         B4: LicenseToken model
10.04 čet  A4 ✓ + Redis caching + A.L.fix  B4 ✓: Middleware + Celery
11.04 pet  ← Verifikacija + bugfix sprint →
12.04 sub  ← Load test: 200 simultanih →    B5: Distributer form
13.04 ned  ← Buffer popravci →              B5 ✓ + Pricing page
14.04 pon  ← Finalni deploy + FENIX_STATUS ažuriranje →
15.04 uto  🎯 PLATFORMA LIVE — #1 HR ERP+AI
```

---

## IVAN — AKCIJE (paralelno s CC)

```
01.04 (uto): Naruči Hetzner CCX33 × 2
             → jedan na Marijino ime, jedan na Kruljacovo
             → Pošalji IP adrese Sonnet-u čim stignu

03.04 (čet): Marija pokreće bulk invite za 71 firmu
             → /eracun/mandati/bulk-umbrella/ (CC mora isporučiti do 02.04.)
             → bulk_invite_ghost_firms command

05.04 (pet): Kontaktiraj odvjetnika
             → DPA template (CC_TASK_LICENSING_LEGAL_SHIELD.md Dio B)
             → SLA: 5h/mj + 80 EUR/h, Event of Default definicija

10.04 (čet): Marija testira WhiteLabel na konjik.limit-connect.com
             Kruljac testira Korpaš umbrella view

14.04 (pon): Finalni pregled + odobrenje deploymenta
```

---

## GEMINI — AKCIJE (autonomno)

```
01.04: EU strateška analiza (GEMINI_TASK_POSREDNIK_EU_ANALIZA.md)
03.04: Partner onboarding materijali (sales one-pageri HR + EU)
08.04: Adversarial review Mandate implementacije
12.04: Load test interpretacija + tuning preporuke
```

---

## METRIKE USPJEHA 15.04.

| Metrika | Sada | Cilj |
|---|---|---|
| Plaćajuće firme | 14 | 50+ |
| MRR | 2.438 EUR | 5.000+ EUR |
| Ghost firme aktivirane | 0 | 50+ od 71 |
| Distributeri registrirani | 0 | 3 (Marija, Kruljac, +1) |
| Mandate (punomoći) | 0 | 71+ |
| Server arhitektura | 1 monolit | 3 odvojena sloja |
| Redis hit rate | 52% | 90%+ |
| p95 response time | ~300ms | <500ms |

---

## ŠTO JE POSREDNIČKI MODEL (za Mariju ako pita)

```
Konjik d.o.o. dobiva ISO 27001 + PU certifikat = registrirani posrednik.
UN CERTIFIKAT pokriva SVE klijente koji daju punomoć.
Distributer iz Splita = prodajni agent, NE treba vlastitu licencu.
Klijent potpisuje punomoć jednom → FINA evidentira → Konjik šalje za njega.

Može li se izgubiti račun? NE.
SHA-256 hash + deletion_protected_until + is_locked = 3 sloja zaštite.
Svih 15.327 računa u bazi ima sve tri zaštite.
```

---

## BORG DNEVNA RUTINA (nastavlja se paralelno)

```
02:00 — backup (lc_backup.sh, 89MB, 127.0.0.1 fix aktivan)
02:30 — AI WorkTime patrol
06:00 — auto-book high confidence dokumenti
07:30 — WhatsApp jutarnji izvještaj
Svakih 6h — license check (po implementaciji B4)
```

---

## STATUS: ACTIVE
## Commit: 69da6edd | 30.03.2026. 23:35
## Sljedeći korak: CC Code počinje A1 i B1 sutra ujutro
