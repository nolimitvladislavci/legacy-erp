---
name: POS Redesign — 3 klika do prvog bona
description: Kompletna reorganizacija POS aktivacije i artikl unosa. Globalne porezne kategorije, blagajnik s OIB-om, tri koraka.
type: project
---

## POS REDESIGN: "3 klika do prvog bona"

### KONTEKST (21.03.2026 — feedback iz testiranja):
- POS aktivacija je prekomplicirana
- Porezne grupe nisu vidljive nigdje
- Unos artikla → Spremi → 404
- Blagajnik nema OIB (zakonski obavezan podatak)
- Unos gotovine pri otvaranju smjene je opcionalan ali koristan
- Korisnik ne razumije redoslijed koraka

### NOVI FLOW — 3 koraka:

**KORAK 1: Porezne kategorije (globalno, jednom)**
- Pregled/uređivanje PDV stopa za firmu
- Default: 25% (standard), 13% (hrana/piće), 5% (kruh/mlijeko), 0% (oslobođeno)
- DE: 19% + 7% + 0%
- Svaka kategorija: naziv, stopa %, opis, zemlja
- Ovo se postavlja JEDNOM i koristi u cijelom sustavu (POS, fakture, inventar)
- Ako ne postoji → auto-seed po zemlji firme (HR/DE/AT/SI)
- UI: jednostavna lista s inline editom, gumb "Dodaj novu stopu"

**KORAK 2: Blagajnik (ime, prezime, OIB)**
- Puno ime blagajnika
- OIB blagajnika — ZAKONSKI OBAVEZNO za fiskalizaciju
  (Zakon o fiskalizaciji čl. 9 — OIB operatera na svakom računu)
- PIN za brzo prebacivanje (4 znamenke)
- Opcionalno: unos početne gotovine u blagajni
  - Ako unese: pamti se kao opening_cash na sesiji
  - Ako ne unese: 0 EUR, može se promijeniti naknadno
- UI: jednostavan form, 4 polja

**KORAK 3: Odabir vrste blagajne**
- Radio lista (kao sad, native HTML — radi na svakom uređaju)
- 6 tipova: Brza, Maloprodaja, Restoran, Terenska, Usluge, Recepcija
- Klik na tip → ODMAH OTVARA BLAGAJNU
- Auto-kreira terminal + sesiju + redirecta na POS sučelje
- Nema "Dalje", nema "Kreiraj" — odabir = pokretanje

### GLOBALNE PROMJENE:

**Porezne kategorije:**
- TaxRate model VEĆ POSTOJI (companies.TaxRate)
- Treba: stranica za upravljanje (/companies/tax-rates/)
- Treba: auto-seed pri registraciji (po country)
- Treba: vidljivo u POS artiklima, fakturama, inventaru

**Artikl unos u POS-u:**
- Spremi → 404 bug treba fiksati
- Zelena poruka "Artikl spremljen" nakon uspješnog unosa
- Porezna kategorija obavezna pri unosu artikla (dropdown iz TaxRate)

**Blagajnik OIB:**
- POSCashier model: dodati oib polje (CharField max 11)
- Migracija
- Fiskalizacija: koristiti cashier.oib kao OibOper (trenutno koristi company OIB)

### REDOSLIJED IMPLEMENTACIJE:
1. Auto-seed TaxRate pri registraciji
2. TaxRate management stranica
3. POSCashier.oib migracija
4. Novi 3-step POS activation wizard
5. Fix artikl unos 404
6. Integracija OIB operatera u fiskalizaciju

### PRONAĐENI BUGOVI (za fiksati):
- Artikl spremi → 404 (URL routing problem)
- AI cockpit ne reagira (treba dijagnozu)
- QR scan s mobitela ne dolazi (scan endpoints nedostaju u URL-ovima)
