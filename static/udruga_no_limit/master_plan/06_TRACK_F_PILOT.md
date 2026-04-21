# TRAK F — PILOT + OPERATIVNO

**Vlasnik**: Pilot agent (može biti Sonnet za implementaciju, ljudi za odnose)
**File područje**: `core/pilot/` (NOVO), `pilots/memio_world/` (NOVO), `pilots/notary/` (NOVO), `pilots/caritas/` (NOVO)
**NE diraj**: drugi moduli osim njihove API integracije

---

## CILJ

Pretvoriti tehnologiju u **stvaran rad za stvarne ljude**. Bez pilot-a, Future 3 + Strategic Moves su papir.

---

## PILOT #1 — memio.world (T2–T4) — NAJBRŽI WIN

**Status**: Naša vlastita platforma, 100 % kontrola.

### Cilj
Svaki diploma izdana kroz memio.world dobiva **Triple DNA pečat** + ChainBlock POE Block.

### Plan
1. **T2**: Backend integracija (memio.world Django app) — koristi `core/searchable/` (Trak A) za embedding diploma
2. **T2**: Frontend — pri izdavanju diplome generira PDF s SHA-256 + QR + ChainBlock blok
3. **T3**: Izdaj prvih 10 testnih diploma (npr. „Digitalna pismenost — osnovna razina")
4. **T3**: Generiraj video demo (1 min) — kako se diploma izdaje + verificira
5. **T4**: Press release: „Prva diploma na svijetu sa Triple DNA pečatom"

### Trošak
0 EUR (sve postojeća infrastruktura).

### Output
- Javni URL: `https://memio.world/diplome/[broj]`
- Video demo: `https://no-limit.world/pilot/memio-world/`
- 10 stvarnih diploma u POE-u

---

## PILOT #2 — Javni bilježnik Osijek (T4–T8)

**Status**: zahtijeva sastanak (Trak E) + Trust Anchor pismo (Trak D).

### Cilj
Javni bilježnik koristi Triple DNA za potvrdu autentičnosti dokumenta koji potpisuje.

### Plan
1. **T4**: Sastanak s bilježnikom (Trak E)
2. **T5**: Tehnička integracija — REST API koji prima upload PDF-a i vraća Triple DNA + URL za verifikaciju
3. **T6**: Pilot testovi (10 dokumenata)
4. **T7**: Pravna analiza — može li bilježnik službeno koristiti?
5. **T8**: Memorandum potpisan, javno priopćenje

### Trošak
0 EUR (besplatna integracija u zamjenu za pilot status).

### Output
- API endpoint: `https://api.no-limit.world/notary/v1/seal`
- Bilježničko priopćenje: „Prvi javni bilježnik u RH koji koristi Triple DNA"

---

## PILOT #3 — Caritas Osijek + Program DOM (T6–T10)

**Status**: zahtijeva memorandum (Trak D + Trak E).

### Cilj
Caritas pronalazi prvu obitelj koja treba **Program DOM**. NO LIMIT financira materijal, volonteri grade, sve dokumentirano u POE.

### Plan
1. **T6**: Memorandum s Caritas Osijek
2. **T7**: Caritas predlaže 3 kandidate (kriteriji prema Statutu čl. 29)
3. **T8**: Skupština NO LIMIT bira 1 obitelj (ili Predsjednik privremeno)
4. **T9**: Otvaranje posebnog TR za Program DOM, uplata prvih 5.000 EUR (Konjik sponzor)
5. **T10**: Početak gradnje — sve fotografirano, dokumentirano, javno

### Trošak
~10.000 EUR za prvi projekt (Konjik d.o.o. sponzor + crowdfund).

### Output
- Stvaran dom za stvarnu obitelj
- Mjesečno javno izvješće na `https://no-limit.world/program-dom/`
- Press potencijal: HRT, Slobodna, Glas Slavonije

---

## PILOT #4 — Mali POS pilot (T8–T10) — paralelno s F #2/3

**Status**: zahtijeva POS Command Mode (Trak B Sprint 7-9).

### Cilj
Jedna postojeća mala trgovina/kafić koristi POS Command Mode na mobilnom uređaju.

### Kandidati (Ivan zna)
- Pekara u Vladislavcima
- Kafić u Osijeku
- Autoservis (nije POS, ali Voice Queue je perfect)
- Marija Čačić — pedagog (uredovni rad)

### Plan
1. **T8**: Instalacija na njihov uređaj (tablet ili telefon)
2. **T9**: 1 tjedan promatranja, A/B vs klasični POS
3. **T10**: Iteracija na osnovu feedback-a, dokumentacija slučaja

---

## PILOT #5 — eValidator SaaS (T10–T12)

**Status**: nakon što su pilot 1-3 dali kredibilitet.

### Cilj
Javni eValidator API + UI gdje bilo tko može:
- Učitati dokument
- Dobiti Triple DNA pečat
- Dijeliti link za verifikaciju

### Plan
1. **T10**: API endpoint + UI na `https://validator.no-limit.world/`
2. **T11**: Stripe pretplata (free / pro / enterprise tier)
3. **T12**: Launch + first 10 plaćenih korisnika

### Trošak / prihod
- Trošak: ~500 EUR (server, SSL, Stripe taxes)
- Prihod: 49 EUR × 5–20 pretplatnika = 245–980 EUR/mj nakon 1 mj

---

## SLJEDEĆA AKCIJA

→ **Pilot #1 (memio.world)** — može početi ODMAH, paralelno s ostalima.

## ZADNJA IZMJENA

| Datum | Tko | Što | Sljedeći korak |
|---|---|---|---|
| 21.04.2026. | Opus design | Plan napisan | Krenuti memio.world integracija |

## DEPENDENCIES

- **Pilot #1**: nema (memio.world je naš)
- **Pilot #2-3**: čeka Trak E (sastanci) + Trak D (memorandum)
- **Pilot #4**: čeka Trak B Sprint 7-9 (POS UI)
- **Pilot #5**: čeka Pilot #1-3 (kredibilitet)
