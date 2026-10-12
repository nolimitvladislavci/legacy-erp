# otpad_katalog — interna baza kataloških brojeva za auto otpad

PostgreSQL, bez slika. Ovo je **probna verzija**: vozila su uvezena, brojevi dijelova su
**izmišljeni (prefiks TST)** dok ne stignu pravi podaci (vlastiti dijelovi + ATRIS/Autodata).

## Što radi
- `trazi_broj('1K0 615 301 AA')` — broj u bilo kojem obliku (razmaci, crtice, mala slova) →
  naziv dijela, na koja vozila stane, koliko ih imamo na zalihi.
- `trazi_vozilo('focus', 2013)` — vozilo + godina → tipovi vozila; točan model ide prvi.
  Bez dijakritika ("citroen" nalazi "Citroën").

## Datoteke
| Datoteka | Što |
|---|---|
| `schema.sql` | tablice: izvor, vozilo_tip, dio, dio_broj, dio_vozilo, otpad_vozilo, otpad_dio |
| `pretraga.sql` | funkcije `trazi_broj`, `trazi_vozilo` |
| `uvezi_vozila.py` | pretvara `brands.js` iz paketa `auto-parts-db` u SQL (čita kao tekst, ništa ne izvršava) |
| `seed_probni.sql` | 20 IZMIŠLJENIH dijelova + 1 probni auto, samo za test |
| `test_otpad_katalog.sh` | 40 provjera na privremenoj bazi |

## Pokretanje testa
```
BRANDS_JS=<putanja/do/auto-parts-db/dist/esm/data/brands.js> ./test_otpad_katalog.sh
# ako treba drugi korisnik:  PSQL="runuser -u postgres -- psql -X -q -tA -v ON_ERROR_STOP=1"
```
Test briše i iznova stvara bazu `otpad_katalog_test`. **Ne pokretati prema produkcijskoj bazi.**

## Izvori i ograničenja
- Vozila: paket `auto-parts-db` 3.0.0 (MIT) — 142 marke, 2377 modela s generacijama,
  4642 tipa vozila. Dva modela (Dacia Nova, Supernova) nemaju godišta pa nisu uvezeni.
  Porijeklo izvornih podataka o generacijama nije provjereno; za internu upotrebu.
- Paket sadrži i popis "dijelova", ali **bez kataloških brojeva** (ruski nazivi) — nije uvezen.
- Brojevi dijelova: **još nema pravih**. Dolaze iz (1) brojeva na vašim skinutim dijelovima,
  (2) ATRIS/Autodata kopije u skladu s licencom.
- Nema korisničkog sučelja; sljedeći korak je jednostavan ekran (jedno polje) u Djangu.
