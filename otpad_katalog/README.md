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

## Ekran: tamni dio (kartice Novi dio · U radu · Stalaža)

Tok bez papira, jedna radnica s mobitelom: **Novi dio** (auto + broj/naziv; nepoznat dio se svejedno unosi) → **U radu**
(3+ slike, pranje sa slikom, test DRŽI/PAD/NE ZNAM, pakiranje sa slikom i dimenzijama, pretinac, pa „Stavi u prodaju" uz
cijenu i razred jamstva) → **Stalaža** (nađi po adresi pretinca, oznaci dijela ili broju; dodavanje pretinaca polica po polica).
Vrata „Stavi u prodaju" provjerava stroj i izlistava sve razloge ako dio još ne smije van. Stara kartica „Brzi unos (staro)"
zaobilazi vrata (dio odmah ide na zalihu) i treba se ukinuti čim novi tok proradi.

Pokretanje na TEST bazi (uz korake iz prethodnog odjeljka, plus):
```
psql -d <test_baza> -f prodaja/schema_prodaja.sql -f prodaja/schema_tamno.sql -f uloga_ekran.sql
psql -d postgres -c "ALTER ROLE otpad_ekran PASSWORD '<lozinka>'"                     # NE u repo
OTPAD_DSN="host=127.0.0.1 dbname=<test_baza> user=otpad_ekran password=<lozinka>" \
OTPAD_SLIKE=/putanja/izvan/repoa/slike OTPAD_PORT=8765 python3 ekran/server.py
```
Bez `OTPAD_SLIKE` učitavanje slika vraća 503 (nema slučajnog spremanja). Uloga `otpad_ekran` nema DELETE i ne smije mijenjati
token, donora ni broj na dijelu.

**Slike:** `ekran/spremnik.py` je PRIJELAZNI lokalni direktorij (sadržaj izvan baze, u bazi samo sha256 i veza). Prava pohrana je
poslovna arhiva (ARHIVA 2030, `arhiva_core/ulaz.py: primi_dokument`) iz koje se gradi webshop; spajanje čeka mjerenje što
`resolver.put` radi dalje s dokumentom i kako se u arhivi razlikuju privatne slike od javnih. Preglednik prije slanja smanji sliku
na 2000 px i ponovno je kodira, čime se izbacuje EXIF (npr. GPS). Krunica nikad ne nosi sadržaj slike.

**Testovi (sve na privremenim bazama):**
```
BRANDS_JS=<brands.js> python3 -I ekran/test_tamno_ekran.py          # 64 provjere + stari test_ekran.py (20)
BRANDS_JS=<brands.js> python3 -I ekran/test_preglednik_tamno.py [mapa_snimki]   # Chromium, 2 teme x 2 širine, cijeli tok, 132 provjere
```

**Nije gotovo:** prepoznavanje po slici (H1), skeniranje kamerom (sada tipkovnica/skener kao tipkovnica), obilazak pretinaca (inventura),
offline rad u dvorištu bez signala, zamagljivanje javnih slika (lica, pločice), prijava i HTTPS (ekran sluša samo 127.0.0.1),
nativni odabir datoteka je na jeziku preglednika. Samo Chromium je testiran.
