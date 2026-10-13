# Brief za Fablea — Kelava (auto otpad, Tenja)

Napisala sesija Claude Code `session_01P5KN18DaRqxRrryzpCv9CK`, grana `claude/loving-babbage-gzx2xt`, PR https://github.com/nolimitvladislavci/legacy-erp/pull/1 (draft). Stanje na 2026-10-12.

## Cilj (Ivanovim riječima, sažeto)
Interni sustav za auto otpad (100+ vozila) i webshop. **Bez papira**: bez printanja i ljepljenja naljepnica, osim ako netko to želi (opcija). Sve je u sustavu. Dio bez bar/QR koda prepoznaje se **po slici**, koja ide u bazu (NE u Krunicu). Dio izlazi "na svjetlo dana" (webshop, račun, lanac) **tek kad ga se stavi u prodaju**. Predradnje: slikanje → pranje → testiranje → pakiranje. Treba smisliti i **kako dio naći na stalaži**. Živi Q4D kod prati tijek (prodano, isporučeno, plaćeno, povrat) i ostaje u srcu; oko njega su Code 128 (stari hardver) i plaćanje (GiroCode/HUB3). Ništa se ne izbacuje. Radnica nema pojma o autima, treba softversku pomoć.

## Što je GOTOVO (triplet = test_prodaja.py 28/28, test_otpad_katalog.sh, ekran 20+116)
- `otpad_katalog/`: baza kataloških brojeva (norm_broj, dio_broj, vozilo_tip, otpad_vozilo, otpad_dio), pretraga `trazi_broj` / `trazi_vozilo`, 4642 tipa vozila iz `lifeofcapo/car-api` (MIT; **bez kataloških brojeva**), ekran za radnicu (traži + unos skinutog dijela). Brojevi dijelova u seedu su izmišljeni (TST).
- `otpad_katalog/prodaja/`: tok `NA_ZALIHI → PRODAN → ISPORUCEN → POVRAT_ZATRAZEN → NA_ZALIHI | SKART`; jamstvo (fizička osoba ≥ 12 mj., pravna osoba može i 0); odustanak 14 dana samo za prodaju na daljinu; lanac događaja `dio_dogadjaj` (samo dopis, hash); izlazni red `izlaz_flota` (RACUN, STORNO, DOKARH). Modul **ne piše u flotu**. Ime kupca ne ulazi ni u događaje ni u izlaz.
- Kod plaćanja: `qr4d_klijent.py` poziva postojeći servis flote `POST /api/v1/qr4d/uplatnica` (EU :8120). HUB3 PDF417 (HR IBAN) i EPC GiroCode. Nezavisno dekodirano: HRVHUB30, EUR, iznos, IBAN.

## Što NIJE gotovo i čeka tvoj plan (WIP, ne više od 3)
1. **Cijeli bezpapirni tok**: prepoznavanje dijela po slici, slikovna baza (privatna, ne Krunica), predradnje, lokacija na stalaži, trenutak "izlaska na svjetlo". Nije osmišljeno ni napisano.
2. **Živo Q4D srce u Kelavi.** `qr4d` ruta za živi kod traži GenesisLogin Bearer token; privatne ključeve ne diramo. Treba ili ruta tipa `…/qr4d/dio` (ključ ostaje na serveru), ili token testne sesije. Faza PLAĆENO još ne postoji u mom lancu. Kod Code 128: u Ivanovoj slici je 26 znamenki (`03407429544699306998215032`), a **što kodira i koja skripta slaže kompozit, nije nađeno**.
3. Restart `genesis` na EU (Ivan je dao DA, nije izveden) i uzrok `dokarh-vlasnik` petlje.

## Postojeći moduli flote koje treba POZVATI, ne pisati ponovo (Ustav §8)
`services/media_proc.py` (WebP, cilj 70 % ili 75 %: odluka otvorena), `services/ocr.py` (Tesseract hrv+eng, točnost na naljepnicama dijelova **nemjerena**), `services/dokarh_kamera_engine.py` (`ingest_foto`), ARHIVA 2030 (`services/arhiva.py`, `arhiva_core/*`; `ulaz.py` i `obrada.py` nisu pročitani), `eho_v2/q4d.py` + `qr_eho10_4dimenzije.py` (srce, prstenovi, faze izdan / fiskaliziran / storniran), `qr4d` servis, Django apps `inventory`, `invoicing`, `fiskalizacija`. **Modul za ponude nije nađen** (u `/var/www/viskovic-ponude` su samo dvije statične HTML stranice).

## Činjenice koje mijenjaju odluke
- **Jamstvo:** za potrošača rabljena roba ne ispod 1 godine ugovorno, zakonski 2; "prodano kakvo jest" za potrošača ne postoji; za pravnu osobu može i bez garancije. Potvrđeno samo preko Your Europe; tekst hrvatskog ZZP-a nije nađen. Provjeriti s knjigovođom.
- **Knjižica vozila (Ivanova odluka 13.10.):** čitaju se i spremaju SAMO podaci o vozilu (VIN, marka, model, godište, kW, ccm, gorivo, boja, oznaka motora). Ime vlasnika se ne sprema nigdje, a prijašnji vlasnik nije bitan (nema nasljeđivanja). Slika knjižice: samo u bazi (nikad u Krunici), a ako je ime vlasnika na slici, slika se ne čuva (odluka Fablea/Ivana). Zato nema posebnog privatnog spremnika za osobne podatke: jednostavan popis dopuštenih polja (whitelist), sve ostalo se odbacuje.
- **Nesklad u Ivanovu primjeru koda:** GiroCode kaže 2.700,00 EUR / "Rechnung 106", a HUB3 80.402,62 EUR / "Racun 100…". U Kelavi svi slojevi moraju nositi isti događaj i iznos (test).
- Q4D oko srca (meta-okvir, sidra, pravi mobitel) **nije dokazan** (H16); srce kao običan QR jest.
- Na EU `https://genesis.limit-connect.com/q/test` vraća 500; `pos/q4d_racun.py` koju spominje test_q4d_fenix.py nije na NEW.
- Podaci o brojevima dijelova (ATRIS/Autodata) su u Nufringenu; Ivan tamo za ~3 tjedna. Do tada je izvor brojeva ono što radnica upiše + brojevi na skinutim dijelovima.

## Što tražiti od izvršitelja (Claude Code)
Svaki korak mora imati naredbu, exit kod, hash/izlaz. Izmjena postojećih datoteka uz `.bak.<UTC>`; produkcija samo uz Ivanov `DA <radnja> <meta>`.
