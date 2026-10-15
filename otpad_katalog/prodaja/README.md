# prodaja — dio od police do prodaje i povrata

Tok: `NA_ZALIHI → PRODAN → ISPORUCEN → POVRAT_ZATRAZEN → NA_ZALIHI | SKART`.
Dio ulazi u račun/fiskalizaciju/DokArh **tek kad je prodan**; do tada je samo interni zapis.
Modul **ne piše u flotu**: sve ide u red `izlaz_flota` (RACUN, STORNO, DOKARH); postojeći moduli flote ga čitaju.

| Datoteka | Što |
|---|---|
| `schema_prodaja.sql` | statusi, jamstvo (zadano 12 mj.), povrat, lanac događaja `dio_dogadjaj` (samo dopis, hash lanac), `izlaz_flota`, uloga `otpad_prodaja` |
| `prodaja.py` | `prodaj`, `isporuci`, `zatrazi_povrat`, `zaprimi_povrat`, `provjeri_lanac` |
| `qr4d_klijent.py` | poziva postojeći servis flote `qr4d` (`POST /api/v1/qr4d/uplatnica`): HUB3 PDF417 za HR IBAN, GiroCode za ostale. Ne crta ništa sam |
| `test_prodaja.py` | 28 provjera na privremenoj bazi + 10 poziva prema `qr4d` uživo |

Postavke (okolina, ne repo): `KELAVA_PRIMATELJ` (≤ 25 znakova), `KELAVA_IBAN`, opcionalno `QR4D_URL`.
Bez njih prodaja radi, a kod plaćanja je `NEPOZNATO`.

**Nije dokazano / nije gotovo:** Q4D prsteni po fazama dijela (čeka H16), povezivanje izlaznog reda s `invoicing`/fiskalizacijom/DokArh-om,
zakonski rokovi su NAPISANI (ne pravni savjet). Testne vrijednosti IBAN-a su izmišljene.

## Tamni dio (`schema_tamno.sql`, `tamno.py`, `test_tamno.py`): KELAVA_PLAN_K2 §1

`RODEN → PREDRADNJE → NA_STALAZI → [STAVI_U_PRODAJU] → NA_ZALIHI → PRODAN → …`
Dio se rađa uvijek (i kad tip nije prepoznat), s nasumičnim tokenom. Predradnje (OPRAN, TESTIRAN, PAKIRAN) traže dokaz (slika,
dimenzije, težina); test PAD vodi u SKART. Pretinac je adresa `R03-P2-04`. Na vratima stroj provjerava ≥ 3 slike dijela,
zadnji test DRZI, pakiranje, lokaciju, cijenu, razred jamstva i javne slike; tek tada nastaju atomi `LANAC_SVJETLO`
(Merkle korijen privatnog dnevnika, bez sadržaja) i `OGLAS` u `izlaz_flota`. Tjedni korijen svih tamnih dnevnika: `tjedni_korijen`.
Stari Code 128 broj mapira se na token (`kod_alias`). H3: HUB3 i GiroCode se izvode iz iznosa događaja PRODAJA.
Test: `python3 -I test_tamno.py` (40 provjera + 10 poziva prema `qr4d` uživo).

**Nije gotovo:** prepoznavanje po slici (H1), `Q4D` srce i Code 128 sloj (čeka uzorke), obilazak pretinaca (inventura),
offline sinkronizacija, zamagljivanje javnih slika, stvarno spremanje slika u ARHIVA 2030 (ovdje samo otisak i veza).
