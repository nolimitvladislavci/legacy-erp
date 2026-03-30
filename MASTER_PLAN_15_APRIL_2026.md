# MASTER_PLAN_15_APRIL_2026.md
# Cilj: LIMIT Connect = #1 ERP+AI platforma u HR, infrastruktura za 3.000+ firmi
# Rok: 15.04.2026.
# Tim: 2× CC Code (paralelno), Sonnet (koordinator), Gemini (revisor)
# Serveri: Ivan + Marija + Kruljac (po 130 EUR/mj svaki)
# Status: ACTIVE — Ivan Brtan odobrio 30.03.2026.

---

## SERVERSKA ARHITEKTURA DO 15.04.

### Tri servera — tri osobe plaćaju

```
SERVER 1 — Ivan (trenutni, ostaje)
  Hetzner CCX13: 4 vCPU, 8GB RAM, 150GB NVMe
  Uloga: Redis + Celery workers + backup node
  Cijena: 51 EUR/mj (već plaća)

SERVER 2 — Marija (novi, naručiti odmah)
  Hetzner CCX33: 8 vCPU, 32GB RAM, 240GB NVMe
  Uloga: App server (Nginx + Gunicorn + Django)
  Cijena: 131 EUR/mj
  Rok narudžbe: 01.04.2026.

SERVER 3 — Kruljac (novi, naručiti odmah)
  Hetzner CCX33: 8 vCPU, 32GB RAM, 240GB NVMe
  Uloga: PostgreSQL dedicated database
  Cijena: 131 EUR/mj
  Rok narudžbe: 01.04.2026.

UKUPNO: 313 EUR/mj za infrastrukturu koja nosi 3.000+ firmi
```

### Migracija do 15.04. (CC Code Task — vidi TRACK B)

```
Sadašnje: sve na Serveru 1 (monolit)
Ciljano:
  Server 1: Redis (6379) + Celery (4 workers) + Backup cron
  Server 2: Nginx + Gunicorn (12 workers) + Django app
  Server 3: PostgreSQL 16 (shared_buffers=8GB) + PgBouncer
  
Promjena u kodu: NULA LINIJA
Promjena u konfiguraciji: 3 env varijable
  DB_HOST=<Server3_IP>
  REDIS_URL=redis://<Server1_IP>:6379/0
  ALLOWED_HOSTS=limit-connect.com,<Server2_IP>
```

---

## TRACK A — "ODIJELO" (CC Code #1)
### Cilj: Platforma koja radi za SVAKOG korisnika, bez dead enda
### Rok: 15.04.2026.
### Prioritet redoslijed: 1→2→3→4

---

### A1. Claim Your Business (P0 — ODMAH)
**Fajl:** CC_TASK_CLAIM_YOUR_BUSINESS.md
**Rok:** 02.04.2026.

71 Konjikova klijenta ima prave podatke ali ne može pristupiti.
Svaki vlasnik koji pokuša registraciju udari u zid.

**Rezultat:**
- `/firma/preuzmi/<id>/` — vlasnik traži pristup
- `/firma/aktiviraj/<token>/` — vlasnik klikne link od Marije, postavi lozinku
- `bulk_invite_ghost_firms` — Marija šalje invite svim 71 firmama odjednom
- Vlasnik odmah vidi SVE stare fakture i podatke

**MRR potencijal po završetku:** +3.905 EUR/mj (71 × 55 EUR)

---

### A2. SmartEntry — nema više dead endova (P0)
**Fajl:** CC_TASK_SMART_ENTRY_I_POSREDNIK.md (Faza A)
**Rok:** 04.04.2026.

Svaki korisnik koji dođe na sustav završi na `/pocni/`.
Email → detect → NEW_USER ili EXISTING_USER → pravi flow, bez greške.

**Rezultat:**
- `/pocni/` — jedna ulazna točka za sve
- Email postoji → magic link, ne dead end
- OIB postoji → "Možete preuzeti firmu", ne ERROR 500
- Rate limit → lijepa stranica s odbrojačem (već napravljeno)
- `?ref=REF-MARIJA-2026` → automatski veže klijenta uz agenta

---

### A3. Agent Dashboard — Marija i Kruljac vode klijente (P1)
**Fajl:** CC_TASK_SMART_ENTRY_I_POSREDNIK.md (Faza B+C)
**Rok:** 07.04.2026.

Marija ima 71+ klijenta. Kruljac ima Korpaš umbrella.
Oba trebaju vidjeti SVOJE klijente i slati invite linkove.

**Rezultat:**
- `/moji-klijenti/` — lista klijenata, zarada, invite linkovi
- Copy-to-clipboard: `https://limit-connect.com/pocni/?ref=REF-MARIJA-2026`
- QR kod za printanje i stavljanje u ordinaciju/ured
- Sidebar link koji se prikazuje samo agentima

---

### A4. FAL Faza 4 — Audit + Superadmin Dashboard (P2)
**Fajl:** CC_TASK_FAL_FENIX_ACCESS_LAYER.md (Faza 4)
**Rok:** 10.04.2026.

Svaka access decision je logirana. Ivan vidi tko što radi.
"Simulate access" — Ivan može provjeriti što bi Marija vidjela.

**Rezultat:**
- AccessAuditLog model — svaki GRANT i DENY se logira
- `/superadmin/access-log/` — real-time DENY lista
- AI violations posebno označene
- Simulate access gumb

---

### A5. Redis Caching — 52% hit rate → 95%+ (P2)
**Nije poseban task — ugradi u A3/A4**
**Rok:** 10.04.2026.

Permisije, WhiteLabel config, session data — sve u Redis.
Svaki request koji ne ide u SQL je brži za 10-50×.

**Konkretno:**
```python
# Permissions cache (svaki request provjerava)
cache.set(f'perms:{user.pk}:{company.pk}', result, timeout=300)

# WhiteLabel config (ista domena = isti config)  
cache.set(f'wl:{host}', config, timeout=3600)

# UserRole (ne mijenja se često)
cache.set(f'role:{user.pk}', role, timeout=600)
```

---

### A6. Audit Log Fix — 641MB → kontrolirano (P1)
**Nije poseban task — ugradi u A1**
**Rok:** 02.04.2026.

`konto.LedgerLine` generira 806.918 redaka/mj za 14 klijenata.
Za 3.000 firmi = 170 milijuna redaka/mj = katastrofa.

**Konkretno:**
```python
# U konto/models.py — isključi audit za immutable modele
class LedgerLine(AuditableModel):
    class Meta:
        # LedgerLine je immutable — samo se kreira, nikad ne mijenja
        # Audit je besmislen i ubija performanse
        audit_log = False
```

---

## TRACK B — "KRUNA" (CC Code #2)
### Cilj: Platforma za distributere — #1 u HR, širi se u EU
### Rok: 15.04.2026.
### Prioritet redoslijed: 1→2→3→4

---

### B1. Server Migracija — 3 servera (P0 — ODMAH)
**Novi task — vidi specifikaciju ispod**
**Rok:** 08.04.2026.

Ovo je infrastrukturalni zadatak koji ne ovisi o kodu.
Može početi čim Marija i Kruljac naruče servere.

**Rezultat:**
- Server 2: App server live, Nginx radi
- Server 3: PostgreSQL migiran, PgBouncer konfiguriran
- Server 1: Redis + Celery workers
- Zero downtime migracija (stari server ostaje backup)
- `.env` promjena = 3 varijable

**Ansibleom ili ručno (Ansible je bolje za ponovljivost):**
```bash
# Ansible playbook struktura (CC Code kreira)
ansible/
  inventory.ini          # 3 servera
  playbooks/
    setup_app.yml        # Server 2: Nginx + Gunicorn
    setup_db.yml         # Server 3: PostgreSQL + PgBouncer  
    setup_cache.yml      # Server 1: Redis + Celery
    migrate_db.yml       # Zero-downtime DB migracija
  roles/
    common/              # Base setup za sve servere
    app/                 # Django app specifičnosti
    database/            # PostgreSQL tuning
    cache/               # Redis konfiguracija
```

---

### B2. WhiteLabel Engine — svaki distributer ima vlastiti brand (P0)
**Fajl:** CC_TASK_LICENSING_ENGINE.md
**Rok:** 05.04.2026.

Marija dobiva `konjik.limit-connect.com` s Konjik logom i bojama.
Kruljac dobiva `korpas.limit-connect.com` s Korpaš brendom.
Budući distributer iz Splita dobiva `split-erp.limit-connect.com`.

**Rezultat:**
- `WhiteLabelConfig` model (brand, subdomain, fiscal_system)
- `WhiteLabelMiddleware` (detektira brand iz domene)
- Context processor (WL_NAME, WL_LOGO, WL_PRIMARY u svim templateovima)
- CSS override u `base.html`
- `/pocni/?ref=KOD` → prikazuje brand agenta
- `CompliancePackage` seed: HR, DE, AT, SI

---

### B3. LicenseToken + Heartbeat (P1)
**Fajl:** CC_TASK_LICENSING_LEGAL_SHIELD.md (Dio A)
**Rok:** 08.04.2026.

Svaki Distributer ima licencu koja se obnavlja plaćanjem.
Ne plati → grace period → read-only → suspended.
Ivan dobiva WhatsApp alert. Uvijek ostaje pristup za export (GDPR).

**Rezultat:**
- `LicenseToken` model (status, valid_until, heartbeat)
- `LicenseCheckMiddleware` (samo za WhiteLabel firme)
- Celery beat: provjera licenci svakih 6h
- Sidebar warning kada ističe
- `402 Payment Required` umjesto grubog blokada

---

### B4. Distributer Onboarding Flow (P1)
**Fajl:** CC_TASK_SMART_ENTRY_I_POSREDNIK.md + GEMINI_TASK_PARTNER_ONBOARDING_WORKFLOW.md
**Rok:** 10.04.2026.

Netko iz Splita želi biti distributer.
Ide na `/postani-distributer/`, popunjava formu, Ivan dobiva WhatsApp.
Ivan odobrava → Distributer odmah dobiva subdomain, invite kodove, dashboard.

**Rezultat:**
- `/postani-distributer/` — landing stranica
- Onboarding forma (naziv firme, grad, planirana klijentela)
- Ivan odobrava iz cockpita
- Auto-setup: subdomain + WhiteLabel + InviteCode + LicenseToken
- Welcoming email s invite linkom i kratkim uputama

---

### B5. EU Compliance Paketi — priprema za EU (P2)
**Fajl:** CC_TASK_LICENSING_ENGINE.md (Korak C2)
**Rok:** 13.04.2026.

DE, AT, SI firm koji se registrira automatski dobiva pravi compliance paket.
KassenSichV za DE, RKSV za AT, FURS za SI.

**Rezultat:**
- `CompliancePackage` model seeded (HR/DE/AT/SI)
- Billing addon automatski kada firma odabere DE compliance
- EU firma redirect na pravi fiskalni flow
- Osnova za prvu EU licencu

---

### B6. Pricing Stranica — Distributer Track (P2)
**Novi task**
**Rok:** 14.04.2026.

Trenutna pricing stranica govori s pekarnicama.
Dodati drugi track: "Postanite distributer u vašem gradu."

**Rezultat:**
- Dvije sekcije: "Za tvrtke" i "Za distributere / posrednike"
- Kalkulator: koliko firmi × cijena = tvoja zarada
- "Slobodna područja" karta (vizualno koje gradove nitko nema)
- CTA: "Postanite prvi u Splitu / Rijeci / Varaždinu"

---

## VREMENSKI PLAN (paralelno)

```
DAN/DATUM    TRACK A (CC #1)              TRACK B (CC #2)
─────────────────────────────────────────────────────────
31.03 (pon)  A1 start: Claim model        B1 start: Ansible setup
01.04 (uto)  A1: Views + URLs             B1: Server 2 konfiguracija
             ← Marija i Kruljac naručuju servere →
02.04 (sri)  A1 DONE + bulk invite        B1: Server 3 PostgreSQL
             A2 start: SmartEntry         B2 start: WhiteLabel model
03.04 (čet)  A2: detect-email API         B2: Middleware + context proc.
04.04 (pet)  A2 DONE /pocni/ live         B2: base.html integracija
             ← Marija šalje bulk invite svim 71 firmama →
05.04 (sub)  A3 start: Agent dashboard    B2 DONE: WhiteLabel live
06.04 (ned)  A3: moji-klijenti view       B3 start: LicenseToken
07.04 (pon)  A3 DONE + invite linkovi     B3: Middleware + Celery
08.04 (uto)  A4 start: AccessAuditLog     B1 DONE: DB migracija
             ← Server migracija aktivna →
09.04 (sri)  A4: Superadmin dashboard     B3 DONE: LicenseToken live
             A5: Redis caching            B4 start: Distributer form
10.04 (čet)  A5+A6 DONE                  B4: Onboarding + WhatsApp
11.04 (pet)  ← Verifikacija + bugfix sprint →
12.04 (sub)  ← Load test: simul 200 istovremenih korisnika →
13.04 (ned)  ← Buffer za popravke →       B5: EU Compliance paketi
14.04 (pon)  ← Finalni deploy + FENIX_STATUS update →
15.04 (uto)  🎯 FENIX ODIJELO OBUČENO — PLATFORMA JE LIVE
```

---

## LOAD TEST PLAN (12.04.)

Prije nego objavimo "spremi za 3.000+", verificiramo:

```bash
# Locust ili k6 test na Serveru 2
# Scenarij: 200 korisnika istovremeno, 10 minuta
# Svaki korisnik: login → dashboard → fakture → POS → logout

# Prihvatljiv rezultat:
#   p95 response time < 2s
#   Error rate < 0.1%
#   CPU < 60% na peaku
#   RAM < 70% na peaku

# Ako ne prođe: skaliramo gunicorn workers
# Svaki worker košta ~150MB RAM — na 32GB servera ima ih bezbroj
```

---

## ŠTO IVAN RADI (paralelno s CC)

```
01.04:  Naruči Server 2 (Hetzner CCX33) — za Mariju
        Naruči Server 3 (Hetzner CCX33) — za Kruljac
        Kontaktiraj odvjetnika: DPA + SLA ugovor

03.04:  Pošalji Mariji login podatke za novi server
        Pošalji Kruljac-u login podatke za novi server

04.04:  Marija pokreće bulk invite za 71 firmu
        (CC Code mora isporučiti A1 do ovog datuma)

07.04:  Marija testira /moji-klijenti/ dashboard
        Kruljac testira Korpaš umbrella view

10.04:  Odvjetnik šalje prvi nacrt DPA ugovora
        Ivan pregleda i šalje Mariji/Kruljac-u na potpis

14.04:  Sve testirano, DPA u procesu potpisa
        Objava na Facebooku/Instagramu/LinkedIn

15.04:  🎯 Platforma objavljena za javnost
        Distributeri iz HR mogu se prijaviti
```

---

## ŠTO GEMINI RADI (autonomno, bez pitanja)

```
01.04:  EU strateška analiza (GEMINI_TASK_POSREDNIK_EU_ANALIZA.md)
        Output: dokument za EU partner razgovor

03.04:  Partner onboarding workflow (GEMINI_TASK_PARTNER_ONBOARDING_WORKFLOW.md)
        Output: sales materijali za HR i EU distributere

08.04:  Adversarial review Track A i Track B
        Uloga: pokušaj pronaći što je CC Code napravio loše

12.04:  Load test analiza i preporuke za optimizaciju
        Uloga: interpretira rezultate, predlaže tuning
```

---

## METRIKE USPJEHA — 15.04.

| Metrika | Danas | Cilj 15.04. |
|---|---|---|
| Plaćajuće firme | 14 | 50+ |
| MRR | 2.380 EUR | 5.000+ EUR |
| Ghost firme aktivirane | 0 | 50+ od 71 |
| Distributeri registrirani | 0 | 3+ (Marija, Kruljac, 1 novi) |
| p95 response time | ~300ms | <500ms |
| Redis hit rate | 52% | 90%+ |
| Serveri | 1 (monolit) | 3 (razdvojeni slojevi) |
| `#1 HR ERP+AI` | Ne | Jedini koji ima ovu kombinaciju |

---

## BORG IZJAVA

Platforma već ima:
- 15.327 faktura, 33.299 partnera u bazi
- FAL (Fenix Access Layer) s Default Deny
- Multi-tenant izolacija (242 modela, CompanyManager)
- KassenSichV adapter (DE), XRechnung u razvoju (EU)
- Celery + Redis + PgBouncer
- 106/106 BORG simulacija prolazi

Nedostaje:
- "Odijelo" (Track A) — pristup za 71 klijenta
- "Kruna" (Track B) — distributer infrastruktura

Do 15.04. — oboje je obučeno.

---

## STATUS: ACTIVE
## Koordinator: Sonnet
## Executor: 2× CC Code (paralelno)
## Revisor: Gemini
## Rok: 15.04.2026. — FIKSAN
