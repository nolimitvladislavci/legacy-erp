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
- Sirovi izvor: `src/data/brands.ts` iz `lifeofcapo/car-api` (commit `0a7092f`, 11.8.2026., MIT).
  Provjereno: identičan je `car-brands.json` iz istog repoa i paketu `auto-parts-db` 3.0.0.
  `uvezi_vozila.py` čita `.ts`, `.js` ili `.json` kao tekst.
- Ekran za radnicu postoji (vidi dolje); još nije spojen na Django projekt ni na prijavu.

## Ekran za radnicu (`ekran/`)
Dvije kartice: **Traži** (jedno polje: broj dijela ili "Focus 2013") i **Unesi skinuti dio**
(auto → broj na dijelu → stanje A–D, polica, cijena). Poznati broj sam upiše naziv dijela;
dio se automatski povezuje s vrstom auta s kojeg je skinut. Duplikat traži potvrdu.

Samo standardna Python biblioteka + `psycopg` 3. Pokretanje na TEST bazi:
```
psql -d <test_baza> -f schema.sql -f pretraga.sql -f uloga_app.sql      # + uvoz vozila i seed_probni.sql
psql -d postgres -c "ALTER ROLE otpad_app PASSWORD '<lozinka>'"          # lozinka NE ide u repo
OTPAD_DSN="host=127.0.0.1 dbname=<test_baza> user=otpad_app password=<lozinka>" OTPAD_PORT=8765 python3 ekran/server.py
```
Testovi (traže pokrenut server i test bazu):
```
OTPAD_URL=http://127.0.0.1:8765 OTPAD_DSN=... python3 ekran/test_ekran.py          # poslužitelj, 20 testova
OTPAD_URL=http://127.0.0.1:8765 python3 ekran/test_preglednik.py [mapa_snimki]     # Chromium, 2 teme x 2 širine
```
**Prije prave upotrebe obavezno:** prijava (sada je ekran otvoren svakome tko dođe na port;
sluša samo `127.0.0.1`), HTTPS, produkcijska baza i lozinka uloge `otpad_app`.
Uloga `otpad_app` smije samo čitati i dodavati (bez brisanja i izmjene strukture).
Preglednik: testirano samo u Chromiumu; Firefox i WebKit nisu provjereni.
