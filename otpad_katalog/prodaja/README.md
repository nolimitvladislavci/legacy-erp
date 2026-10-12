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
