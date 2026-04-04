# GEMINI_TASK: SYNESIS+ ASIMILACIJA — Strateška analiza
# Datum: 04.04.2026. | Izvršava: Gemini (autonomno)
# Koordinator: Sonnet | Odobrio: Ivan Brtan

---

## KONTEKST

LIMIT Connect je uvezao 92.3% Synesis podataka za klijente Konjik d.o.o.:
  - 33.299 partnera (direktno u partners_partner)
  - 15.327 faktura (invoicing_invoice)
  - 10.732 journal entries (konto_journalentry)
  - Metoda: mdb-export (mdbtools) + bulk_import Python skripte
  - SynesisConfig model: 9 firmi u bazi (meta prazna — uvoz bio direktan)

Ivan i Gemini predlažu: "Synesis+" modul — asimilacija Synesisa u LIMIT Connect.

---

## ZADATAK — 4 OUTPUTA

### OUTPUT 1: Pravna analiza (do 200 reci)

Odgovori na:

a) Naziv "Synesis+" — trademark rizik?
   - Je li "Synesis" registrirani trademark u HR/EU?
   - Može li se koristiti "Synesis+" u marketingu, dokumentaciji, UI?
   - Alternativni nazivi bez pravnog rizika: "LIMIT Import", "Smart Migration", itd.

b) MDB čitanje tuđeg softvera — legalno?
   - Korisnik posjeduje vlastite MDB podatke. GDPR Art. 20 (pravo na prenosivost).
   - Je li reverse engineering MDB formata (zaobilaženje DLL) zakonski problem?
   - Jesu li mdbtools open-source alati legalni za komercijalnu upotrebu?

c) Retroaktivna fiskalizacija — što smijemo, što ne?
   - Uvezene fakture iz Synesis-a NEMAJU FINA digitalni potpis.
   - Mogu li se prikazivati u LIMIT Connectu kao "arhivske" bez ponovne fiskalizacije?
   - Što ZOR i Pravilnik o fiskalizaciji kaže o uvezenim podacima?

d) Revizijska staza — zahtjevi porezne uprave
   - Trebaju li uvezeni podaci biti označeni kao "uvezeno iz Synesis-a [datum]"?
   - Audit log zahtjevi pri migraciji podataka?

### OUTPUT 2: Tehnička arhitektura Synesis+ (do 150 reci)

Opiši optimalnu arhitekturu za:

a) One-time migration wizard (5 minuta za klijenta)
   - Upload MDB fajla → automatski import → verifikacija → go live
   - Što koraci moraju biti, koji redoslijed

b) Live bidirectionalni sync (stretch goal)
   - Klijent radi u Synesis-u, LIMIT Connect dobiva kopije
   - Tehnički izvedivo s mdbtools + Celery + cron?
   - Koji podaci se sinkroniziraju (partneri, artikli, ulazne fakture?)
   - Koji se NE sinkroniziraju (fiskalizirani računi — nema retroaktivno)

c) SynesisExportQueue model — čemu služi?
   - Postoji u bazi, ali prazan. Je li ovo za reverse sync (LIMIT → Synesis)?
   - Preporuka: koristiti ili abandonati?

### OUTPUT 3: Competitive positioning (do 100 reci)

Synesis je #2 ERP u HR za male firme (procijenjeno 15-20% tržišta).
Libusoft Cicom je #1 (komunale, gradovi).

- Koliko firmi koristi Synesis u HR? (procjena)
- Koji je migratorni argument? ("Vaši podaci su vaši")
- Kako se pozicionirati: "Nasljednik Synesis-a" vs "Uvoz iz Synesis-a" vs "Synesis killer"?
- Koji je rizik od reakcije Synesis d.o.o.?

### OUTPUT 4: Preporuka — da ili ne?

Konačna preporuka u 5 točaka:
  1. Da li implementirati Synesis+ modul? (DA/NE + obrazloženje)
  2. Naziv koji preporučuješ (bez pravnog rizika)
  3. Prioritet u odnosu na Sprint (P0/P1/P2)
  4. Ključni disclaimer koji mora biti u UI-u
  5. Rok za implementaciju ako odluka bude DA

---

## GEMINI — PRAVILA IZVRŠAVANJA

- Koristi web search za trademark provjeru (HR ZIT, EUIPO TMview)
- Koristi web search za mdbtools licencu (GPL — provjeri komercijalni uvjet)
- ZOR reference: NN 78/2015, NN 115/2016 — Zakon o računovodstvu
- Fiskalizacija reference: NN 133/2012, NN 115/2016
- Output spremi u: /var/www/fina-connect/GEMINI_SYNESIS_PLUS_ANALIZA.md
- Format: markdown, čitljivo, s konkretnim preporukama
- NE piši generičko — piši specifično za LIMIT Connect kontekst

---
STATUS: PENDING — Gemini još nije pokrenuo
