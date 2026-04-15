# FENIX PORTAL — STATUS NAPRETKA
> Zadnji update: 2026-04-15 (Dan 49), commit fb6addad — PLAY.EU 23 modela, 237 sadrzaja

---

## SESIJA LOG

| Datum | Agent | Fokus | Rezultat | Commit |
|-------|-------|-------|----------|--------|
| 2026-04-14 | Sonnet+CC | Korak 1-7 | Inventura, audit, standardi, test coverage | 5ea4e6f1 |
| 2026-04-14 | Sonnet+CC | Korak 8 | Load test: 50VU, P95=850ms, 0 failures | f46bd567 |
| 2026-04-14 | Sonnet+CC | Umbrella patch | CompanyMiddleware — 30+ modula popravljeno | a5e021e2 |
| 2026-04-14 | CC Code | Korak 9 | Security: Django 5.1.15, rate limit, GDPR audit log | b04ec43a |
| 2026-04-14 | CC Code | Korak 10 | 9 bugova, 21/21 smoke testovi ✅ | c74c539f |
| 2026-04-14 | Sonnet | Korak 11 + Arhiva | Beta Konjik. OCR 100%. Arhiva HR-DE plan. Memio kontekst. | c74c539f |
| 2026-04-14 | Opus CC | ARHIVA-1 | ScanToken model+views+UI+tests, 9/9 pass, LIVE | 8327b5ad |
| 2026-04-15 | Opus CC | ARHIVA-2 | ArhivaAccessToken, portal, bulk generator, 17/17 tests | 2f2699bf |
| 2026-04-15 | Opus CC | PLAY.EU A-D | 3 core + 4 quiz modela, Europeana API, 70 items, 20 bajki, 40 kartica | fdbd2e49→4a8fda1f |
| 2026-04-15 | Opus CC | Kurikulum 2.0 | 23 puta ucenja, 10 mudrosti, 9 sigurnosnih tema, prometni znakovi | 7394a16a |
| 2026-04-15 | Opus CC | Growth Engine | TalentRadar, BuddySystem, FamilyQuest, SpacedRepetition, PetBridge | d542d1cf |
| 2026-04-15 | Opus CC | Comfort Engine | DreamGuard, ComfortCard, JokeBox, LegalCompliance | fb6addad |
| 2026-04-15 | Opus CC | DeepSeek Patrol | Fix autodiscovery, Celery Beat registered, nocni run 02:45 | 5cf29da6 |

### KONTEKST ZA SLJEDEĆU SESIJU
```
Aktivni frontovi (paralelni, svi idu istovremeno):
  1. ARHIVA-1  → CC Code ima task (CC_TASK_ARHIVA1_MOBILE_SCAN.md)
  2. memio.pet → živi primjer, gateway ka memio.world
  3. memio.world → EU knjižnica/čitaonica (vanjski suradnik: Marija Čačić)
  4. POS free tier → Marija Čačić čeka (obrt kod kuće, Slavonija)

Filozofija: "Kod vukova starci idu prvi i diktiraju tempo čopora."
  Ivan = coordinator, ne executor. Agenti = čopor. Polako, redom, temeljito.

Ivan status: fasada (Nufringen) + bolovanje plan (6tj + AOK 70%)
Antonio: na terenu s Ivanom (DE)
Dragan: agent DE tržište, pilot Steuerberater
Marija Brtan: Konjik admin, aktivna, beta testira arhivu
Marija Čačić: vanjski suradnik memio.world (EU knjižnica), čeka POS free tier
```

---

## RAZVOJNA PRAVILA

### PRAVILO 1 — Nema zakrpa, samo pravi fix
Globalni CSS → `fenix-ui.css` | Python → shared util/middleware/mixin | Zakrpa = žuti karton

### PRAVILO 2 — Settings i model choices sinkronizirani
`settings.LANGUAGES` = `preferred_language choices`. Kršenje = migration bug.

### PRAVILO 3 — Template promjene = gunicorn reload
`cached.Loader` aktivan. CI/CD automatski, ručni deploji ne smiju zaboraviti.

### PRAVILO 4 — `--preload` zabranjeno
Zamijenjen s `ExecReload=SIGHUP` + graceful reload.

### PRAVILO 5 — Nikad conditional import unutar try/except
```python
from companies.models import Company  # uvijek na vrhu, ne conditional
```

### PRAVILO 6 — QR kodovi uvijek kroz /qr/ endpoint
`GET /qr/?data=URL&size=200` — nikad vanjski servisi.

### PRAVILO 7 — Svaka nova javna ruta u RouteRegistry
PUBLIC ili AUTHENTICATED — nikad zaboraviti. Propust = 302 bez log greške.

### PRAVILO 8 — OIBi u testovima validni (ISO 7064 Luhn-10)
Validni: 12345678903, 98765432106, 11111111119, 22222222226, 55555555551, 66666666664

### PRAVILO 9 — Bez datuma izvršenja, samo redoslijed
Datum kreiranja ✓ | Redoslijed ✓ | Datum izvršenja ✗

---

## DASHBOARD
```
=== CODE ===             === ARHIVA ===                === MEMIO ===
Python LoC:  ~299K       Konjik komitenti:  75         memio.pet:   LIVE ✅
Tests:       2,340       Arhiva dok.:     5.874        memio.world: Temelj ✅ (čeka views)
Commits:       952       OCR točnost:      100%        memio.farm:  SyncLink ✅
Coverage:    40.3%       WhatsApp send:      ✅        No-limit:    NGO portal ✅

=== QUALITY ===          === SECURITY ===
Ruff errors:    0        csrf_exempt:   45 (bilo 147)
Django check:   0        Sentry:        LIVE
mypy:      clean         pip-audit:     2 CRITICAL preostala
```

---

# ZLATNI KOD — PLAN PRODUKCIJE

## KORACI 1-10 ✅ GOTOVO

## KORAK 11 — BETA: KONJIK D.O.O. 🔄 AKTIVAN (10%)
```
Firma:    Konjik d.o.o. — računovodstveni ured, 75 komijenata, 5.874 dok.
Knjigov.: Marija + Ljiljana + Nikolina + Silvija + Anita
Cilj:     Marija kaže "ovo radi, mogu pokazati klijentima"
Blokeri:  ARHIVA-1 mora biti live
```

## KORAK 12 — EU KAMPANJA ⏳ (čeka ARHIVA 1-5)

## GORIVO
| Što | Status | % |
|-----|--------|---|
| Koraci 1-10 | ✅ | 100% |
| Korak 11 Beta | 🔄 | 10% |
| **ARHIVA-1** Mobile Scan | ✅ LIVE | 95% |
| ARHIVA-2 Magic Link | ✅ LIVE | 100% |
| ARHIVA-3 Network Disk | ⏳ | — |
| ARHIVA-4 WhatsApp Share | ⏳ | — |
| ARHIVA-5 WhatsApp-IN | ⏳ | — |
| ARHIVA-6 DE Steuerberater | ⏳ | — |
| ARHIVA-7 DATEV Export | ⏳ | — |
| ARHIVA-8 Porezna Prijava DE | ⏳ | — |
| ARHIVA-9 Synesis Retroaktiv | ⏳ | — |
| ARHIVA-10 Billing | ⏳ | — |
| **POS free tier** (Marija Čačić) | ⏳ | — |
| **PLAY.EU Sprint 1** | ✅ DONE | 100% (23 modela, 237 sadrzaja) |
| PLAY.EU Frontend (Faza E) | ⏳ | — |
| memio.pet booking | ⏳ | — |
| Korak 12 EU Kampanja | ⏳ | — |

---

# OPERACIJA: ARHIVA HR-DE
**Cilj: #1 digitalna arhiva za računovodstvo u HR i DE | Nema konkurencije u EU**

## ZAŠTO NITKO U EU NEMA OVO
```
Synesis (HR):       Nema arhivu. ZOR = 11 god. obaveza. Mi imamo.
DATEV (DE):         Monopol, skup, nema mobile OCR, nema WhatsApp-IN
Taxfix/Steuerbot:   Samo fizičke osobe, 1 firma, nema umbrella
Minimax/4D:         Web ERP bez mobile-first arhive
Naš edge:           Mobile-first + WhatsApp-in + AI OCR + umbrella (1 ured → 75 firmi)
```

## OCR BENCHMARK (live test, 2026-04-14)
```
4 računa: INA Čepin ×2, Petrol Osijek, Petrol Ljubljana (SI)
Točnost:  100% — dobavljač, datum, iznos, JIR/ZKI
Ukupno:   73.14€ | PDV: 14.43€
```

---

## ARHIVA-1 — MOBILE SCAN PORTAL 🔄 CC Task zapisan
**Link → mobitel → kamera → arhiva. Bez logina. Bez instalacije.**
```
[x] ScanToken model + migracija ✅
[x] /scan/{token}/ PUBLIC ruta ✅
[x] Mobile UI — 1 gumb, zlatni, kamera ✅
[x] Token generator za Mariju u panelu ✅
[x] QR kod za token ✅
[x] 9 pytest testova ✅
Test: Marija → token → Gašić Ivan slika → pojavi se u arhivi
```

## ARHIVA-2 — MAGIC LINK PRISTUP ⏳
**Marija 1 klik → komitent dobije pristup svojoj arhivi.**
```
[ ] Bulk magic link generator u umbrella dashboardu
[ ] Za komitente bez emaila: scan token direktno
[ ] Welcome page: "Imate X dokumenata. ZOR 11 godina."
```

## ARHIVA-3 — NETWORK DISK ⏳
**rclone → OneDrive. Paralelna kopija na Marijinom disku.**
```
[ ] 'network' backend u StorageConfig
[ ] NetworkDiskBackend (rclone mount)
[ ] Celery async sync task
[ ] Monitoring: ako mount pao → Sentry, ne blokira upload
Preporuka: OneDrive/SharePoint (M365 Business)
```

## ARHIVA-4 — WHATSAPP SHARE LINK ⏳
**Knjigov. šalje link, komitent skine dokument s mobitela.**
```
[ ] TemporaryShareLink model (token, expires 7d, download_count)
[ ] /arhiva/share/{token}/ PUBLIC
[ ] Gumb "Pošalji WhatsApp" na svakom dokumentu
[ ] Bulk: "Sve za 2026" → ZIP + WhatsApp link
```

## ARHIVA-5 — WHATSAPP-IN ⏳
**Komitent šalje sliku na WhatsApp Konjika → automatska arhiva.**
```
[ ] WAHA webhook inbound
[ ] Phone → Company mapping
[ ] OCR → ArhivaEntry → WhatsApp potvrda: "✅ INA 23.09€ arhivirano"
[ ] Jutarnji digest za Mariju
DIFFERENCIATOR: Invisible UI. Nema instalacije, nema logina.
```

## ARHIVA-6 — DE STEUERBERATER PAKET ⏳
```
[ ] DE document tipovi (Rechnung, Fahrtkosten, Bewirtungsbeleg...)
[ ] MwSt 19%/7% u OCR logici
[ ] role='steuerberater' u UserProfile
[ ] Dragan = pilot DE Steuerberater
```

## ARHIVA-7 — DATEV EXPORT ⏳
```
[ ] DATEV CSV (Buchungsstapel format)
[ ] SKR03 konto mapping (gorivo→4530, restoran→4650...)
[ ] DATEV EXTF header
[ ] Testirati u DATEV Unternehmen Online
```

## ARHIVA-8 — POREZNA PRIJAVA DE ⏳
```
Phase 1: PDF "Podloge za Steuererklärung" → Steuerberater uzme i unese
Phase 2: Elster XML (direktna e-prijava) — nije prioritet
```

## ARHIVA-9 — RETROAKTIVNI SYNESIS IMPORT ⏳
```
[ ] Analiza Synesis PDF export
[ ] Batch scan session (gomila papira → AI matchanje)
[ ] Gap report: "Za 2023. Gašić Ivan ima 48 stavki ali samo 12 skenova"
```

## ARHIVA-10 — BILLING ⏳
```
Starter:         besplatno, 50 dok/mj, 1 firma
Računovotkinja:  19€/mj, 15 firmi, WhatsApp-IN, DATEV
Ured:            49€/mj, neograničeno, sve
Enterprise:      ugovor, white-label, Elster
```

## REDOSLIJED
```
1. ARHIVA-1+2 → CC Code odmah
2. Beta: Marija testira
3. ARHIVA-4+3 → paralelno
4. ARHIVA-5 → WhatsApp-IN
5. ARHIVA-6+7 → Dragan dovodi DE klijenta
6. ARHIVA-8+9 → kad je baza stabilna
7. ARHIVA-10 → kad 5+ Tier 2 klijenata
8. Korak 12 EU Kampanja
```

---

# MEMIO EKOSISTEM

## FILOZOFIJA
```
memio.pet → živi dokaz digitalizacije (ljubimci)
         → isti model za djecu (memio.world)
         → isti model za heritage (memio.world)
"Zašto ne i djece — a koliko je daleko — vidjet ćemo"
```

## memio.pet — LIVE ✅
```
Domena:      memio.pet LIVE
Rute:        22 whitelistane za memio.pet domenu
Testovi:     12/12 E2E zeleni
Baza:        2 životinje, 13 profila
Booking:     ⏳ sljedeći korak
Uzgajivači:  https://memio.pet/registracija/
```

## memio.world — TEMELJ ✅, MVP ⏳
```
Vizija:       EU projekt knjižnice i čitaonice
Suradnik:     Marija Čačić (vanjski) — čeka memio.world MVP + POS free tier
Modeli:       7 (ChildProfile, TimeCapsule, MemoryVault, FamilyStory,
              MemoryEntry, Milestone, WaitlistEntry)
Enkripcija:   ✅ WorldEncryptedField na sadržaju
Waitlist:     6 prijava
Što nedostaje: SVE view-e i template-e za CRUD
MVP plan:     ChildProfile + MemoryEntry + foto upload + PDF album (9.99€/god)
Blokira:      POS free tier za Mariju Čačić
```

## POS FREE TIER — Marija Čačić ⏳
```
Tko:    Marija Čačić, obrt kod kuće, Slavonija
Što:    Besplatni POS za mali obrt (ili simbolično 0€)
Blokira: memio.world suradnju
Plan:   Konfigurirati existing POS za njen obrt, special free plan
```

## memio.farm — SyncLink ✅
```
farm_animal_uuid:   UUID ref na memio_farm bazu
memio_pet_profile:  UUID ref na memio_pets bazu
Pilot:  OPG Kruljac Slađana (~60 goveda)
```

## memio.world MVP redoslijed
```
1. POS free tier za Mariju Čačić → ona počne koristiti portal
2. ChildProfile CRUD + foto upload
3. MemoryEntry (knjiga uspomena)
4. PDF album export (prodajni trenutak)
5. Landing page s vizijom (pitching material za EU knjižnice)
```

---

# STANJE BAZE I SERVERA
```
Server:          37.27.248.86 (Hetzner)
Aktivnih firmi:  101 | Umbrella djece:  81
Korisnika:        56 | Faktura:     15,330
Arhiva dok.:   5.874 | Commits:       970+
Journal:      10,732 | Workspaces:      36
Konjik top:        Glazbeni Centar Mai 1.688 dok.
```

## AI SERVISI
```
DeepSeek:   AKTIVAN ✅ (uplata $5.30, 2026-04-14)
Bedrock:    AKTIVAN ✅ (eu-central-1, reset 15.04. ponoć)
Anthropic:  AKTIVAN ✅ (API key u settings)
```

---

# BACKLOG

| # | Nalaz | Ozbiljnost | Uvjet |
|---|-------|------------|-------|
| B-01 | user_edit company isolation | SREDNJE | company_admin self-service |
| B-02 | trojstvo_task suggestion_id type guard | NIZAK | kad se dotakne trojstvo |
| B-03 | user_edit company scope | SREDNJE | isti kao B-01 |
| B-04 | StorageConfig 'network' backend | SREDNJE | ARHIVA-3 |
| B-05 | WhatsApp-IN nepoznati pošiljatelji | NIZAK | ARHIVA-5 |
| B-06 | DATEV header verifikacija | VISOK | ARHIVA-7 |
| B-07 | POS free tier konfiguracija za Mariju Čačić | SREDNJE | memio.world MVP |

---

## EU FUNDING STRATEGIJA — PLAY.EU (Dan 48)

### Konzorcij:
```
NO LIMIT udruga (HR)        → koordinator (registracija u tijeku)
Konjik d.o.o. / LIMIT (HR)  → tech partner, platforma
Marija Čačić / čitaonica (HR)→ kultura/edukacija
DE partner                   → Viskovic Bau / knjižnica Herrenberg
Nordijski partner            → Erasmus mreža
```

### Bonus: Ivica Kruljac (agro), Antonio (mladi osnivač)

### Ciljani program: Creative Europe Small Cooperation (€60K-200K)
### Projekt: "PLAY.EU — Digitizing Europe's Intangible Heritage Through Children's Games"

### memio.world MVP stanje:
```
Modeli:  14 tablica (ChildProfile, TimeCapsule, MemoryVault, FamilyStory,
         StoryBook, TraditionalGame, LearningModule, Spomenar, SpomenarEntry,
         Event, Milestone, MemoryEntry, WaitlistEntry)
Seed:    Mlin (kompletna pravila), Čovječe, Školica, priča "Zvjezdice i Mjesec",
         lekcija "Učimo slova A,B,C"
Enkripcija: WorldEncryptedField (AES, zaseban ključ)
```

### Koraci dok registracija traje:
1. Vizija NO LIMIT na papiru (1 A4)
2. Letter of Intent od Marije Čačić
3. Kontakt Creative Europe Desk Zagreb
4. memio.world demo za prezentaciju

---

## MEMIO.WORLD — KOMPLETNA ARHITEKTURA (Dan 48, finale)

### 44 tablica (21 originalne + 23 PLAY.EU novih)

```
TEMELJ (7):
  WaitlistEntry, ChildProfile, MemoryEntry, Milestone,
  TimeCapsule, MemoryVault, FamilyStory

SADRŽAJ (6):
  StoryBook (4 priče, 3 jezika)
  TraditionalGame (11 igara, 9 EU zemalja, 5000 godina)
  LearningModule (slova, brojevi)
  Spomenar + SpomenarEntry
  Event (rođendani, izleti, škola)

INOVACIJE (5):
  VoiceLegacy          — glas bake/djeda, SHA-256, biometrija, dijalekt
  EthicalSession       — anti-dopaminski tracker
  NightProtocol        — audio-only mod, max priča, uspavanka
  MemoryGuard          — pravo na zaborav, 30d cooling, GDPR Art.17

JOKER + 2 ASA (3):
  DialectMap           — semantička mreža (8 riječi, 4 dijalekta)
  LullabySession       — adaptivna uspavanka, tempo → tišina
  HeritageOracle       — Mapa Porijekla, cross-platform (world+pet+farm)
```

### Seed Data:
- 11 igara: Mlin(HR), Čovječe(DE), Školica(HR), Mensch(DE), Mölkky(FI),
  Bocce(IT), Petteia(GR), Kubb(SE), Hurling(IE), Mangala(TR), Klasy(PL)
- 4 priče: Zvjezdice(HR), Der Mond(DE), Little Star(EN), Jež(HR/Slavonija)
- 1 lekcija: Slova A,B,C
- 8 dijalektnih riječi: šogor, gemišt, gomboc, zakaj, hiža,
  Maultasche, Grüß Gott, ćakula

### Enkripcija:
- MEMIO_WORLD_FERNET_KEY (zaseban od ERP i pets)
- WorldEncryptedField na: poruke, opisi, priče, otisci

### 15 Opasnih Riječi (Manifest):
1.Besmrtnost 2.Bez granica 3.Nježnost 4.Sjeme 5.Glas
6.Most 7.Čuvari 8.Neizbrisiво 9.Igra 10.Sloboda
11.Tišina 12.Krug 13.Otisak 14.Korijen 15.Zagrljaj

### EU Projekt: "PLAY.EU"
- Konzorcij: NO LIMIT(HR) + LIMIT(HR) + Čačić(HR) + DE + Nordic
- Cilj: Creative Europe Small Cooperation (€60K-200K)
- Adut: digitalizacija 5000 godina EU kulturne baštine za djecu

---

## PLAY.EU — SPRINT 1 STANJE (15.04.2026)

### Faze:
```
Faza A: Modeli + Migracije          ✅ DONE (0007)
Faza B: Europeana API               ✅ DONE (70 items, client + sync)
Faza C: Sadrzaj                     ✅ DONE (20 bajki, 40 kartica, DeepSeek prijevodi)
Faza D: Quiz Engine                 ✅ DONE (4 modela, 40 pitanja)
Kurikulum 2.0                       ✅ DONE (23 puta, 10 mudrosti, 9 sigurnosti)
Growth Engine                       ✅ DONE (7 modela: Talent, Buddy, Family, Spaced, Pet)
Comfort Engine                      ✅ DONE (4 modela: Dream, Comfort, Joke, Legal)
Faza E: Frontend UI                 ⏳ SLJEDECA (PWA shell + 3 demo scenarija)
```

### Modeli (23 novih u memio_world bazi):
```
CORE:       EuropeanaItem, ParallelStory, HeritageCard
QUIZ:       Quiz, QuizQuestion, QuizAnswer, QuizAttempt
KURIKULUM:  LearningPath, LifeLesson, WisdomEntry, SafetyTopic, ContentLink
GROWTH:     TalentProfile, RealWorldVenue, BuddyPair, FamilyQuest,
            FamilyQuestCompletion, SpacedRepetitionCard, PetBridgePost
COMFORT:    DreamGuard, ComfortCard, JokeEntry, LegalCompliance
```

### Sadrzaj u bazi: 237
```
70  Europeana items (8 kategorija)
20  paralelnih prica (10 s tekstom HR+DE+EN)
40  Heritage kartica (30 slovarica + 10 bestijarij)
2   kviza, 40 pitanja
23  putova ucenja (5 dobnih skupina)
10  bakinih mudrosti
9   sigurnosnih tema (promet, internet, pozar)
10  obiteljskih izazova
5   dream guard zapisa
5   comfort kartica
25  sala/zagonetki/brzalica
```

### DeepSeek Code Patrol:
```
Status:    FIX DEPLOYIRAN — autodiscovery dodano u celery.py
Nocni run: 02:45 na heavy queue
Root cause noci 14→15.04: unregistered task (celery.py autodiscovery missing)
```

### Sljedeca sesija — Faza E Frontend:
```
1. PWA shell (mobile-first, offline, parchment stil)
2. 3 demo scenarija:
   a) Dijete bira bajku → cita HR → prebacuje DE → slusa audio
   b) Ucitelj kreira kviz iz bestijarij kartica → ucenici igraju memory
   c) Roditelj gleda napredak → vidi interese → predlozeni klubovi
3. DreamGuard nocni UI (topla zuta, veliki font, audio-only opcija)
4. JokeBox daily widget (svakog jutra nova sala)
5. ComfortCard UI (dijete bira emociju → baka tjesi)
```

### Creative Europe deadline: 2026-05-07
