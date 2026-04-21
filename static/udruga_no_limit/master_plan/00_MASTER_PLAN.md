# NO LIMIT — MASTER PLAN

**Datum kreiranja**: 21. travnja 2026.
**Predsjednik**: Ivan Brtan
**Verzija**: v1.0
**Javni URL**: https://no-limit.world/static/udruga_no_limit/master_plan/

---

## SVRHA OVOG DOKUMENTA

Sav kontekst koji je danas „u glavi" sada je na disku. **Bilo koji budući AI agent (Sonnet, Opus, Gemini, GPT) ili ljudski suradnik može preuzeti rad** kroz ovaj plan, bez sjećanja na prethodni razgovor.

**Pravilo agentske paralelizacije**: 8 traka, svaki ima vlastite fajlove i jasne granice. Dva agenta NIKAD ne diraju isti fajl ni isti Django app istovremeno.

---

## TRAKE (8 paralelnih, file-isolated)

| # | Trak | Vlasnik | File područje | Cilj |
|---|---|---|---|---|
| **A** | **Backend / Database** | Backend AI agent | `accounts/`, `companies/`, `invoicing/`, `core/searchable/` (novi), migracije | Searchable mixin (tags + FTS + embedding + summary), Redis L1 cache, intent registry |
| **B** | **Frontend / UI** | Frontend AI agent | `templates/cmd/`, `templates/pos/cmd/`, statički JS | Universal Command Surface, POS Command Mode, adaptive 3-tier layout |
| **C** | **AI / Resolver / Intent** | AI agent | `core/resolver/` (novi), `core/intent_compiler/` | Lightweight intent classifier (sklearn LR), regex slot filling, Haiku fallback |
| **D** | **Patent + Pravno** | Sadržajni agent (Opus) | `static/udruga_no_limit/patent/`, `static/udruga_no_limit/genesis/`, OPP versije | Genesis #1 Forensic DNA, OPP v1.2 + Poison Pill, Sponsor Agreement template |
| **E** | **Marketing / Outreach** | Ivan + ljudi | sastanci, pisma, pozivi | Trust Anchor sastanci (bilježnik, HOK, Pravni fakultet), prvi 10 OPP partneri |
| **F** | **Pilot + Operativno** | Pilot agent | `core/pilot/`, integracije s vanjskim partnerima | memio.world Triple DNA, Caritas Program DOM, javni bilježnik pilot |
| **G** | **QA / DevOps** | QA agent | `qa_lab/`, `.github/workflows/`, monitoring | Oracle, Time Machine, Mutant, Bunker, CI/CD (LIVE od 20.04.) |
| **H** | **Udruga registracija** | Ivan offline | papirologija, predaja u Osijek | Marija Brtan podaci, predaja, OIB, TR, pečat |

---

## FAZE I MILESTONES

### FAZA 0 — TRENUTNO STANJE (21.04.2026.)

✅ **Završeno:**
- Statut v5 (41 članak) + 9 ostalih pravnih dokumenata generirano
- Genesis Block #0 (SHA-256: `6187541b2178a2baaaa04c759f6674faa56b35a0c672682447fa50f890a19658`)
- Patent paket (6 PDF-ova) za DZIV — spreman za odvjetnika
- OPP v1.1 s čl. 27 Reciprocitet
- Future 3 + Strategic Moves dokumentirani
- QA Lab v1 LIVE (Oracle + Time Machine + Mutant + Bunker + Dashboard `/qa/`)
- 3 loga (Beskonačni krug, Mreža Europe, Otvoreni svitak) + EVE jaje varijante

⏳ **U tijeku:**
- 110+ firmi čeka na vratima Fenix V3 (bunker login problem)
- Marija Brtan podaci nedostaju za finalizaciju Popisa osnivača
- Patent odvjetnik nije izabran

### FAZA 1 — STABILIZACIJA (T1–T2, 22.04.–05.05.2026.)

**Cilj**: 110 firmi može ući. Udruga upisana u Registar.

| Trak | Akcija | Done kad |
|---|---|---|
| G (QA) | Bunker dijagnoza + popravak login flow | 110 firmi može ući |
| H (Udruga) | Marijini podaci + predaja u Osijek | Potvrda upisa u Registar |
| A (Backend) | Searchable mixin sprint 1 (Company model, 3 polja) | `migrate` prošao |
| D (Patent) | Genesis #1 Forensic DNA dokument | Javan na URL-u |

### FAZA 2 — COMMAND SURFACE MVP (T3–T6, 06.05.–02.06.2026.)

**Cilj**: Universal Command Surface LIVE na `https://limit-connect.com/`.

| Trak | Akcija | Done kad |
|---|---|---|
| B (Frontend) | Command Surface UI (text + voice + kamera + file input) | UI radi, prazno bez AI |
| C (AI) | Intent classifier + Resolver | 95% upita bez AI fallback |
| A (Backend) | pgvector + multilingual MiniLM embeddings | Semantic search radi |
| F (Pilot) | memio.world prvi pilot — Triple DNA na 10 diploma | Demo video |

### FAZA 3 — POS + AMBIENT AI (T7–T10, 03.06.–30.06.2026.)

**Cilj**: POS Command Mode + proaktivni AI suggestions.

| Trak | Akcija | Done kad |
|---|---|---|
| B (Frontend) | POS adaptive 3-tier (mobile/tablet/desktop) | Test na mobile POS-u |
| C (AI) | Ambient AI (3 suggested actions na dashboardu) | Pokazuje preporuke pri otvaranju |
| A (Backend) | Conversation memory + materialized views | Semantic recall radi |
| E (Marketing) | Trust Anchor — prvi sastanci | 1 pismo namjere s bilježnikom |

### FAZA 4 — PATENT FILE + PROIZVODNI LAUNCH (T11–T12, 01.07.–14.07.2026.)

**Cilj**: DZIV patent prijavljen, sustav u produkciji.

| Trak | Akcija | Done kad |
|---|---|---|
| D (Patent) | DZIV prijava preko odvjetnika | Potvrda primitka |
| F (Pilot) | Caritas Osijek + Program DOM pilot | Memorandum potpisan |
| G (QA) | SLA + monitoring + uptime > 99.5% | 30 dana bez kritičnog incidenta |
| E (Marketing) | Pravilnik o prijateljstvu LIVE | Prvi 100 prijatelja |

### FAZA 5 — RAST (T13+, srpanj 2026.+)

- Horizon Europe grant prijava
- 1.000 prijatelja → 10.000 do kraja 2026.
- POS Command Mode na 50 mjesta (kafići, pekare, autoservisi)
- Patent EPO ekspanzija (12 mj nakon DZIV)

---

## SINKRONIZACIJSKE TOČKE

Točke gdje se trakovi spajaju (tu se događa „handover"):

| # | Točka | Tko spaja s kim | Što se predaje |
|---|---|---|---|
| **S1** | Searchable mixin gotov | A → C | Embedding kolone su spremne, AI može graditi resolver |
| **S2** | Command Surface UI gotov | B → C | UI šalje payload, AI vraća odgovor |
| **S3** | Bunker fix gotov | G → H | 110 firmi ulazi, Udruga može pokazati funkcionalan sustav |
| **S4** | DZIV prijava gotova | D → F | Patent pending status omogućuje pilot s institucijama |
| **S5** | Pilot pokrenut | F → E | Live primjer omogućuje marketing pristup |
| **S6** | Pravilnik o prijateljstvu gotov | D → B → E | Pravna osnova → UI → outreach |

---

## KAKO NOVI AGENT PREUZIMA

1. **Pročitaj ovaj dokument** (`00_MASTER_PLAN.md`)
2. **Otvori svoj trak** (`01_TRACK_A_BACKEND.md` — `08_TRACK_H_UDRUGA.md`)
3. **Pogledaj „Zadnja izmjena"** u tvom traku — to je posljednje stanje
4. **Pogledaj „Sljedeća akcija"** — nastavi odande
5. **Ažuriraj „Zadnja izmjena"** kad završiš svoju akciju
6. **NE diraj fajlove drugih traka** — samo svoje područje

**Sinkronizacijske točke (S1–S6)**: zahtijevaju da se javiš Ivanu ili koordinatoru prije nego što kreneš.

---

## ARHITEKTURNA NAČELA (NEPROMIJENJIVA)

1. **OPP v1.1+** je obvezna licenca za sve novo
2. **PostgreSQL je jedna baza** (ne ElasticSearch, ne Pinecone)
3. **YAGNI** — gradi minimalno, dodaj kad treba (ne 7 modela odjednom)
4. **Sve u Fenix V3 stack-u** (Django + Celery + Redis + pgvector)
5. **OPP filozofija**: tehnologija besplatna, usluge se naplaćuju (B+C hibrid)
6. **Triple DNA u svakom novom entitetu** (L1 + L2 + L3 polja na save())
7. **ChainBlock POE log** za svaki strateški event
8. **Privacy-first** (Whisper lokalno, ne OpenAI; embeddings lokalno)
9. **Multilingual** od dana 1 (HR + DE + EN, kasnije SI + HU)
10. **Open Patent Promise zauvijek** — nikakvi monopoli, čak ni naši
11. **Stare funkcije ostaju na snazi** — AI je nadogradnja, klasični UI uvijek dostupan (vidi Načelo #11 niže)
## ARHITEKTONSKO NAČELO #11 — STARE FUNKCIJE OSTAJU NA SNAZI (graceful degradation)

**Najvažnije pravilo**: AI sloj je **nadogradnja**, NE zamjena. Klasični Fenix V3 UI ostaje 100 % funkcionalan zauvijek.

### 5-razinski fallback stack

```
RAZINA 1 — AI Augmented (Haiku/Gemini, ~1.5s u autu, ~300ms na fiksnoj)
       ↓ fail (5s timeout / API down / no internet)
RAZINA 2 — Lokalni SLM (Phi-3 mini ili Llama 3.2 3B, ~200ms, offline OK)
       ↓ ako nema lokalnog modela ili predugo
RAZINA 3 — Regex intent matcher (50ms, deterministic, jezgra Trak C)
       ↓ ako intent nije prepoznat
RAZINA 4 — KLASIČNI UI Fenix V3 (uvijek dostupan, postojeći moduli)
       ↓ ako nema interneta
RAZINA 5 — Offline PWA (Service Worker cache + Background Sync)
```

**Garancija**: 110 firmi NIKAD ne ostaje zaglavljeno. Klasični Fenix V3 UI je *zauvijek* dostupan na `/classic/` rutama (npr. `/classic/invoicing/`, `/classic/pos/`).

### U autu / loša mreža

- Auto-detekcija: ako 3 uzastopna AI poziva > 1500ms → automatski prebaci na klasični mode
- Pre-cached kritične rute kroz Service Worker (POS, login, top fakture, top firme)
- Background Sync za izmjene koje idu kad mreža ojača
- Korisnik dobiva toast: "Mreža je spora — privremeno klasični mod aktivan"

### Mode toggle (uvijek vidljiv u settings-u)

| Mode | Ponašanje |
|---|---|
| **Auto** | AI prvo, fallback na klasični (preporuka) |
| **Klasični** | Direktno klasični UI, AI nikad — za stare korisnike, slabu mrežu |
| **Command-only** | Samo AI, bez fallback — za napredne korisnike |

**Default**: Auto za nove korisnike, postojećih 110 firmi ostaje na **Klasični** dok ne kliknu opt-in u Auto.



---

## KLJUČNI BROJEVI / KONTAKTI / URL-OVI

| | |
|---|---|
| Predsjednik Udruge | Ivan Brtan, OIB 70086599476, viskovic.bau@gmail.com |
| Sjedište Udruge | Kralja Tomislava 291, 31404 Vladislavci |
| Konjik d.o.o. | Kralja Tomislava 1a, 31431 Čepin |
| Server | 37.27.248.86, ssh -p 2222 |
| Fenix V3 | https://limit-connect.com (port 8001, gunicorn-fenix-v3) |
| NO LIMIT | https://no-limit.world (Django no_limit app) |
| QA Dashboard | https://limit-connect.com/qa/ (staff-only) |
| Genesis #0 SHA-256 | `6187541b2178a2baaaa04c759f6674faa56b35a0c672682447fa50f890a19658` |
| WhatsApp Ivan | +49 157 71998747 |
| WhatsApp WAHA API | http://localhost:3000, key `1a64e68ed45d4b07952430334631caca` |

---

## VERSION LOG

| Datum | Izmjena | Autor |
|---|---|---|
| 21.04.2026. | Prva verzija | Opus 4.7 + Ivan Brtan |
