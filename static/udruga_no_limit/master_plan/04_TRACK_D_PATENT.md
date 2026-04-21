# TRAK D — PATENT + PRAVNO

**Vlasnik**: Sadržajni AI agent (Opus preferiran za pravni tekst)
**File područje**: `static/udruga_no_limit/patent/`, `static/udruga_no_limit/genesis/`, `static/udruga_no_limit/opp/`
**NE diraj**: kod (Django apps), QA Lab

---

## CILJ

Pretvoriti tehnologiju u **pravnu imovinu** + **trajne licence** + **obrambene strategije**.

---

## SPRINT 1 — Genesis #1: Forensic DNA (T1, ovaj tjedan)

### Akcija D1.1 — Genesis Document #1

**Tema**: Metoda detekcije neovlaštenih izmjena u poslovnoj bazi semantičko-numeričkom konzistencijom.

**Konkretno**: kad netko ispod žita mijenja `total = 1000` u `total = 10000`, ali `description` ostaje "Sitni alat" → semantički embedding ne odgovara numeričkom iznosu → audit alert.

**Mehanizam**:
1. Svaki Invoice/transakcija ima L3 embedding generiran iz `description`
2. Cron noću usporedi `embedding(description)` s `expected_embedding(amount, customer, items)`
3. Ako kosinusna sličnost < 0.85 → red flag u audit logu
4. Predsjednik dobiva email upozorenje

**Output**: `NOLIMIT-GENESIS-0002.pdf` (model po uzoru na #0)
**SHA-256 pečat + ChainBlock POE Block #1**

### Akcija D1.2 — Patent Specification: Forensic DNA

Drugi patent u ChainBlock familiji. Naslov:

> **„Računarski implementirana metoda detekcije neovlaštenih izmjena u poslovnoj bazi podataka kombinacijom semantičkog vektora opisa i izvedenih numeričkih obilježja"**

Output: `patent/PATENT-Forensic-DNA-01_Tehnicki_opis.pdf` + Claims + Sažetak

---

## SPRINT 2 — OPP v1.2 + Sponsor Agreement (T3–T4)

### Akcija D2.1 — OPP v1.2 (Poison Pill ugrađen)

Nadogradnja v1.1 s novim čl. 28 — **Trajna obveza OPP-a u slučaju akvizicije** (100 godina).

Format: PDF, javno na `https://no-limit.world/static/udruga_no_limit/opp/NOLIMIT-OPP-v1.2.pdf`

### Akcija D2.2 — Sponsor Agreement template

Predložak ugovora između Konjik d.o.o. i Founding Sponsor-a u sektoru:
- Sektor (Banking, Justice, Media, Education...)
- Ekskluziva 5 godina
- 60 % komercijalnih prihoda
- „Recovered" status nakon 2× break-even
- Ugrađena Poison Pill klauzula (čl. 12)

Output: `patent/SPONSOR-AGREEMENT-template-v1.docx + .pdf`

---

## SPRINT 3 — DZIV prijava (T5–T8)

### Akcija D3.1 — Pronaći hrvatskog patent zastupnika

Lista kandidata (predložiti Ivanu):
- **Plavšić & Krneta**, Zagreb — patenti + IT
- **Korper Čović**, Zagreb — IT specijalisti
- **Vukmir & Associates**, Zagreb — IP
- **HAOPI** registar: https://haopi.hr/registar-zastupnika

### Akcija D3.2 — Predaja paketa odvjetniku

6 PDF-ova već pripremljeno:
- `PATENT-01_Tehnicki_opis.pdf`
- `PATENT-02_Nacrt_claims.pdf`
- `PATENT-03_Sazetak.pdf`
- `PATENT-04_Formalni_obrazac.pdf`
- `PATENT-05_Sheme.pdf`
- `PATENT-06_Upute_odvjetniku.pdf`

Odvjetnik treba: prior art search (2 h) + claim rebalancing (2 h) + DZIV obrazac + uplata 250 EUR + predaja.

### Akcija D3.3 — Forensic DNA isto u DZIV

Drugi paket, isti workflow.

---

## SPRINT 4 — Trust Anchor pravna podloga (T6–T8)

### Akcija D4.1 — Memorandum s Hrvatskim Crvenim križem

Za Program DOM (humanitarno stambeno zbrinjavanje). Predložak:
- Suradnja u procjeni potreba
- Crveni Križ ovjerava korisnike
- NO LIMIT financira materijal
- Volonteri dijele rad

### Akcija D4.2 — Pismo namjere s Pravnim fakultetom

Trust Anchor #1 — akademska podloga. Predložak za fakultet:
- Pristup mreži NO LIMIT
- Studenti pravo dobivaju stažiranja
- Akademski članovi konzultiraju OPP licencni model

### Akcija D4.3 — Pismo HOK-u

Hrvatska obrtnička komora — dio ZOS zaklade (Strategic Move #3).

---

## SPRINT 5 — Pravilnik o prijateljstvu (T2–T3)

Nov pravni dokument koji uvodi „Prijatelje Udruge" (1-click join).

### Akcija D5.1 — Tekst Pravilnika

Sukladno čl. 11 Statuta — Skupština ratificira na prvoj redovnoj sjednici. U međuvremenu, Predsjednik pokreće pilot odlukom.

Sadržaj (skraćeno):
- Tko može biti Prijatelj
- Pravo pristupa alatima (eValidator, Honor Roll)
- Bez prava glasa u Skupštini
- 1-click join, 1-click leave
- Doprinos je dobrovoljan (0 € OK)

Output: `static/udruga_no_limit/PRAVILNIK-PRIJATELJSTVO-v1.pdf`

---

## SPRINT 6 — Marija Brtan dopuna (kad podaci stignu)

### Akcija D6.1 — Dopuniti Popis osnivača
- `NOLIMIT_Popis_osnivaca.pdf` regenerirati s Marijinim OIB-om
- Dopuniti Zapisnik
- Dopuniti Odluku o osnivanju
- Sve ponovno SHA-256 pečatiti i POE log

---

## SLJEDEĆA AKCIJA

→ **D1.1 + D1.2**: Genesis Document #1 (Forensic DNA) — najvažnije, nova patent klasa.

## ZADNJA IZMJENA

| Datum | Tko | Što | Sljedeći korak |
|---|---|---|---|
| 21.04.2026. | Opus design | Plan napisan + savjetnikova ideja Forensic DNA prepoznata kao novi patent | Pokreni D1.1 |

## DEPENDENCIES

- **Čeka**: ništa za Sprint 1 (Genesis #1)
- **Blokira**: Trak F (Pilot) — pilot s bilježnikom traži Trust Anchor pismo
