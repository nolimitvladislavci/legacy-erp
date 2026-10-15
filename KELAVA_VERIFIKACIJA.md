# KELAVA / otpad-katalog — VERIFIKACIJA RADA

Sastavila: sesija `session_01P5KN18DaRqxRrryzpCv9CK` (Claude Code, web), 2026-10-14 06:49 UTC.
Svrha: da netko drugi (druga sesija, Ivan, Fable) može PROVJERITI što je napravljeno, bez da vjeruje mom izvještaju.

## 0. Gdje je rad (i zašto ga EU sesija nije našla)
- **GitHub repo `nolimitvladislavci/legacy-erp`, grana `claude/loving-babbage-gzx2xt`, PR #1 (draft)** — https://github.com/nolimitvladislavci/legacy-erp/pull/1
- To NIJE repo `/var/www/genesis` na EU (tamo postoji samo `master`), pa `git log --all` na EU ne vidi moje commite. Paket zvan „otpad-ekran" i brojka „411/411" **nisu moji**; moji nazivi su `otpad_katalog/` i brojke u odjeljku 3.
- Provjerena osnova (čisti radni direktorij): commit **83eb9e3afd021242af7478650f5ceb3ff2d94f21** (`83eb9e3a`).
- Moj kod NIJE na EU. Na EU su samo dvije izmjene iz odjeljka 4.
- **Paket za uvođenje ekrana na EU POSTOJI, ali ga je napisala DRUGA sesija** (`session_01KME8WP5HfMkATwKt7L9dke`, Claude Fable 5.1): commit **`71a756b1`** na istoj grani (mapa `otpad_katalog/deploy/`: `deploy_eu.sh`, `nginx_otpad.conf`, `otpad-ekran.service`, `vozila.sql`, `test_iza_nginxa.py`, `README.md`; uz izmjene relativnih putanja u `ekran/static/`). To je vjerojatno ono što je Ivanov `DA uvedi-otpad-ekran eu-genesis` ciljao. EU sesija ga nije našla jer je **samo na GitHubu**, ne na EU; README u toj mapi kaže da se uvodi s `git clone -b claude/loving-babbage-gzx2xt https://github.com/nolimitvladislavci/legacy-erp` na EU (traži pristup repou). **Njegove tvrdnje (411/411, 19 × DRŽI, harness 25/25 i 33/33, rollback) NISAM provjerio**; provjerio sam samo da moji testovi prolaze i uz njegove izmjene statičkih datoteka (odjeljak 3b). Prije uvođenja pročitati `deploy/README.md` i pokrenuti `deploy_eu.sh --suho`.

## 1. Kako dobiti kod
```
git clone https://github.com/nolimitvladislavci/legacy-erp.git && cd legacy-erp
git fetch origin claude/loving-babbage-gzx2xt
git checkout claude/loving-babbage-gzx2xt            # ova datoteka je u njemu
# provjera: svaka datoteka kakva je bila na commitu 83eb9e3a mora imati hash iz odjeljka 6
sed -n '/^## 6/,$p' KELAVA_VERIFIKACIJA.md | grep -E '^[0-9a-f]{64}  ' | while read h f; do
  [ "$(git show 83eb9e3afd021242af7478650f5ceb3ff2d94f21:"$f" | sha256sum | cut -d' ' -f1)" = "$h" ] && echo "OK  $f" || echo "PAD $f"; done
```
Repo je privatan: treba Ivanov pristup. Očekivano: 45 redaka, svi `OK`.

## 2. Commiti ove sesije (od `16c7d00f`)
```
83eb9e3a 2026-10-13 feat(otpad_katalog): rad bez signala — red slika na uređaju (IndexedDB) i servisni worker
b58a8473 2026-10-13 docs(soba): zakrpa stražara primijenjena na EU (strazar_ophodnja.py), odstupanja i rollback
57b7e4ce 2026-10-13 fix(otpad_katalog): test_arhiva_spoj — nedostajući uvoz timezone (pokvareno čišćenjem, uhvaćeno regresijom)
377ae034 2026-10-13 feat(otpad_katalog): inventura pretinaca, zakrpa za ophodnju stražara (pripremljena), zajednička logika zakrpa
69723796 2026-10-13 docs(soba): zakrpa bez AI primijenjena na EU (api/arhiva_core.py), odstupanja i rollback
258dbccb 2026-10-13 feat(otpad_katalog): adapter za poslovnu arhivu (slike dijelova), zaštita od AI troška, zakrpa kao skripta, testovi
b02ee0b5 2026-10-13 feat(otpad_katalog): ekran za pretince i unos dijelova (Novi dio, U radu, Stalaža) + vrata prema svjetlu
4cfb2051 2026-10-13 feat(otpad_katalog): tamni dio, predradnje, stalaža, vrata STAVI_U_PRODAJU s Merkle korijenom; N1/N2 zatvoreni
4aeb4cef 2026-10-13 feat(otpad_katalog): validator VIN-a (oblik, kontrolna znamenka, dva čitanja, potvrda 6 znakova) + DB provjera
323b4edd 2026-10-13 docs(kelava): slika knjižice se ne sprema; VIN mora biti potpun i potvrđen
d1480125 2026-10-13 docs(kelava): knjižica vozila — samo podaci o vozilu, bez imena vlasnika
359b0176 2026-10-12 docs(kelava): brief za Fablea — stanje, otvoreno, činjenice
66c36217 2026-10-12 feat(otpad_katalog): prodaja, isporuka, povrat i jamstvo dijela; kod plaćanja preko qr4d servisa flote
```

## 3. Testovi — svježe pokrenuti na `83eb9e3a` (2026-10-14 06:49 UTC), svi na PRIVREMENIM bazama
Okolina: Python 3.13, PostgreSQL 16, Chromium (Playwright), `psycopg 3`, `zxing-cpp`, `sqlalchemy` (samo za test zakrpe).
Brands podaci: `auto-parts-db` 3.0.0 (`dist/esm/data/brands.js`, MIT) — `BRANDS_JS=<put>`.
```
test_vin | exit=0 | UKUPNO 40 · PROŠLO 40 · PALO 0
test_prodaja | exit=0 | UKUPNO 28 · PROŠLO 28 · PALO 0
test_tamno | exit=0 | UKUPNO 48 · PROŠLO 48 · PALO 0
test_arhiva_spoj | exit=0 | UKUPNO 37 · PROŠLO 37 · PALO 0
test_tamno_ekran | exit=0 | UKUPNO 70 · PROŠLO 70 · PALO 0
test_preglednik_tamno | exit=0 | UKUPNO 148 · PROŠLO 148 · PALO 0
test_offline | exit=0 | UKUPNO 15 · PROŠLO 15 · PALO 0
test_preglednik_staro | exit=0 | prošlo: 117 | exit: 0 
```
### 3b. Isti testovi na vrhu grane `b918cf11` (uključuje tuđi commit `71a756b1`), čisti checkout (git worktree), 2026-10-14
`test_vin` 40/40 · `test_prodaja` 28/28 · `test_tamno` 48/48 · `test_arhiva_spoj` 37/37 · `test_tamno_ekran` 70/70 · `test_preglednik_tamno` 148/148 · `test_offline` 15/15 · stari `test_preglednik` 117 prošlo; nijedan `PALO`, svi exit 0.
Nisam pokretao `deploy/test_iza_nginxa.py` ni `deploy_eu.sh` (traže nginx/EU-sličnu okolinu).

Naredbe (iz `otpad_katalog/`): `python3 -I test_vin.py` · `cd prodaja && python3 -I test_prodaja.py` · `cd prodaja && python3 -I test_tamno.py` ·
`BRANDS_JS=<brands.js> python3 -I ekran/test_arhiva_spoj.py` · `… ekran/test_tamno_ekran.py` · `… ekran/test_preglednik_tamno.py` · `… ekran/test_offline.py`.
Razina: **TESTIRANO** (jedno pokretanje po paketu), ne DOKAZANO (nema n ≥ 30 ponavljanja). Testirano samo u Chromiumu, nikad na pravom mobitelu.
Dva testa gađaju stvarni servis flote `qr4d` (POST /api/v1/qr4d/uplatnica, bez pohrane): ako je nedostupan, ispisuju NEPOZNATO.
`test_arhiva_spoj.py` koristi LAŽNU arhivu napisanu prema pročitanom ugovoru, ne stvarnu arhivu.

## 4. Što je promijenjeno na PRODUKCIJI (EU) — jedino
Obje izmjene su napravljene alatom `write_file` (cijela datoteka, uz automatski backup) jer MAX nema `exec`. Ivanov DA za svaku zasebno.
| Datoteka (EU) | Backup | Prije | Poslije | md5 poslije |
|---|---|---|---|---|
| `/var/www/genesis/api/arhiva_core.py` | `api/arhiva_core.py.bak_20261013_062313` | 806 redaka, 35598 znakova | 811 redaka, 36022 znaka | `886084c5c9a3bc3e3feaf1ce96c210c8` |
| `/var/www/genesis/services/arhiva_core/strazar_ophodnja.py` | `services/arhiva_core/strazar_ophodnja.py.bak_20261013_064239` | 162 retka, 6351 znak | 165 redaka, 6693 znaka | `4705be0140ac48b3604718de1e6dd25b` |
Restart: `genesis` (oba puta „active"). Očekivane razlike (provjeri na EU):
```
diff /var/www/genesis/api/arhiva_core.py.bak_20261013_062313 /var/www/genesis/api/arhiva_core.py
  + 3 retka iza `router = APIRouter(...)` (komentar x2 + `_APP_ID_BEZ_AI = frozenset(... ARHIVA_BEZ_AI_APP_ID ... "kelava-dijelovi" ...)`) i prazan redak
  + `    if app_id not in _APP_ID_BEZ_AI:` ispred `background_tasks.add_task(_obradi_u_pozadini, dokument.weise3_id)` (taj redak uvučen)
diff /var/www/genesis/services/arhiva_core/strazar_ophodnja.py.bak_20261013_064239 /var/www/genesis/services/arhiva_core/strazar_ophodnja.py
  ~ `from sqlalchemy import select` -> `from sqlalchemy import func, select`
  + komentar + `_APP_ID_BEZ_STRAZARA = tuple(... STRAZAR_BEZ_APP_ID ... "kelava-dijelovi" ...)` iza `PO_KRUGU`
  + `.where(func.coalesce(ArhivaCoreDokumentORM.app_id, "").notin_(_APP_ID_BEZ_STRAZARA))` u `_kandidati`
```
Druga sesija je na EU vidjela commit `aa19b304` („upload za kelava-dijelovi bez AI obrade"): to je vjerojatno automatski commit prve izmjene; potvrdi s `git -C /var/www/genesis show aa19b304 --stat`.
Poslije svake izmjene: `/health` 200, `/api/v1/arhiva-core/strazar/zdravlje` 200 (zadnji prolaz nakon restarta), `/api/v1/arhiva-core/status/red` 401 (traži prijavu).

## 5. Što NIJE učinjeno / odstupanja (iskreno)
- **INTENT i RAČUN atomi za obje izmjene NISU upisani** (nema `exec`, atome piše samo `protokol/intent.py`). Nema otiska produkcije prije/poslije.
- **Zakrpa nije dokazana na stvarnim podacima:** treba servisna sesija (token) s aktivnim tenantom; do tada `ARHIVA_BEZ_AI_POTVRDENO=1` se ne uključuje.
- Čitač knjižice vozila nije građen (dva neovisna čitanja VIN-a traže plaćeni AI; limit troška = 0). Validator VIN-a (`vin.py`) postoji i testiran je.
- Nema prijave/HTTPS za ekran u ovom commitu (u tijeku, nije u grani). Ekran sluša samo 127.0.0.1.
- Prepoznavanje po slici (H1), Q4D srce i Code 128 sloj, stvarni mobitel: nisu učinjeni.
- Usputni nalaz (nisam dirao): `log` nije definiran u `api/arhiva_core.py` (NameError u dvije grane).

## 6. SHA-256 datoteka na `83eb9e3a` (`sha256sum -c`)
febd430b1964854440075ebd6925b842148a5e5915e33427139874dc3ba56480  FENIX_SOBA.md
e4eb0584cd04613a5e469e822e5bbde0160df5660962c6397b81e8bc21ffa0b9  KELAVA_BRIEF_ZA_FABLE.md
862263fa1f46c20f0d1e4dac5ffcc75abd55c08211b2c3864c5f8764b9d87793  otpad_katalog/.gitignore
32ef7ae7dca58ffa1edd9e6379dd8603ce430c5301809bfc1bcc480267e7b3e0  otpad_katalog/README.md
d08bd3f5d8bfab957955cc0f715313eff05a8cbc28c226e3c0fb21f8184836f8  otpad_katalog/arhiva_spoj/README.md
d4ffad0d2240edccc001a1f4780c465fb046f96ddb9e602e4d4cfd4ae668e96c  otpad_katalog/arhiva_spoj/primijeni_zakrpu.py
63033ce1961daae4a62d4d0c82987d4bb5bc83d494cff56c422a7189ee0343da  otpad_katalog/arhiva_spoj/primijeni_zakrpu_strazar.py
95c2c8b560926a724f2b6abb3f607e8b40ac962833141c9e7da8c7e318d74a17  otpad_katalog/arhiva_spoj/zakrpa_lib.py
a36347d47da9289f27623b8be5348abc339f401f7b2c01b4f6919a9cf1c72ea6  otpad_katalog/ekran/arhiva_spremnik.py
76901902de4129947525ce670b2cd7511fd10d2105d95c5eb274ce51b5d21717  otpad_katalog/ekran/greske.py
839e3160a3b3ccda8b762e13fd52e97dc8be4c268736cd97716dbc432c99df9c  otpad_katalog/ekran/lazna_arhiva.py
af113d7d3e61b2e012ea379cf75ea7690cea7a8714c3cbde29cf96a35f0ea74d  otpad_katalog/ekran/server.py
d5f1f7f67aa2e6c5b277b2437fd9f3a7e41c9e09c349487e27c8b872e91635e9  otpad_katalog/ekran/spremnik.py
f901f7bd5488e3c52640edea6f0980a0c86f76713be0967e1c322af033ae0d13  otpad_katalog/ekran/static/app.css
a0ca1fb756d12934ed1090926d9c3b2a437eb970222469e5ef1ee5dbb399854d  otpad_katalog/ekran/static/app.js
fc508af0f9e1e6a464b20e027c7d4cb2d4098876ce8ba035ef9e6f4f021ef197  otpad_katalog/ekran/static/favicon.svg
aabe59c8aff3af501760f53ea3d847d4efc7c6bb44fcedbbc9735ab3bcff9ae8  otpad_katalog/ekran/static/index.html
733dedbb5674cfa7eac7631f6bbe62597a79e7c1deafcb0cc840cbaf4e6c9001  otpad_katalog/ekran/static/sw.js
c6d32c7ee2e9b91f4e75d3d9eda5fb1442386501a59653d881c8b0d8dc32e2f9  otpad_katalog/ekran/static/tamno.js
719aa1ff04733146c8a8efe4977e2d8d2af0adcf2deb0c5db7acdbe572439a71  otpad_katalog/ekran/tamno_api.py
502dd4d3c3fb0dd1d5b8169acc32466d7d04ffa4093868363725f9bd10f545cc  otpad_katalog/ekran/test_arhiva_spoj.py
4831b4cc8aaf87c11ca78094ae8f796a96e959a009bef80758f4ef772f517012  otpad_katalog/ekran/test_ekran.py
e99ae88ff6e767ce9da7edc233981680c29e81824cbb7f6bab6af1b30df04b15  otpad_katalog/ekran/test_offline.py
759b54bb3a7426c0eec01b8e4ae017892c59152aa217c8c2123b1b17eb188ed9  otpad_katalog/ekran/test_preglednik.py
510027fb5e7983872bec49f822b3efca34d1c08f16feb94d6a56f172fa93a149  otpad_katalog/ekran/test_preglednik_tamno.py
c8147bd1f244a5def6e5564ed2ed3bb703bd22807ba42d00254d7d1a75552684  otpad_katalog/ekran/test_tamno_ekran.py
a571cc9c7b673078ff4240fed27c90e0439afb712991558b5e92866ac8419697  otpad_katalog/pretraga.sql
c0ef142d5dd5aa199966f1d21357d3034134b8b0d8df2fea92c58eb6277bf4ae  otpad_katalog/prodaja/README.md
a84d295f4834daff4f7c9ed02cec3d9092a9fb63b5bbefeb86761e33894771b5  otpad_katalog/prodaja/prodaja.py
23aa969db81e6a87e4ebbe8d354fa8f9f3033410c9c4be701eeb6b649e3fac59  otpad_katalog/prodaja/qr4d_klijent.py
f0bcbab063923656aed5e03edcf02067a768bcee5d635cb3aad9afa8066c93b6  otpad_katalog/prodaja/schema_prodaja.sql
6ff07e0503a3b3b25d6b4fdd6f361b30712bc2a55d04523b8f28c1ca510d2d12  otpad_katalog/prodaja/schema_tamno.sql
f53596a4e18fbf2b85954b463558fa5eadf9adcee38483c2a88328aa90b1cde5  otpad_katalog/prodaja/tamno.py
480146d820546bb87f2175385fd5f9c8b048f22c779e37ca48cef6f192fa5e29  otpad_katalog/prodaja/test_prodaja.py
d6127c93f7c61e78408762b721275d5026d116fdacd752dd5685d48b402addfc  otpad_katalog/prodaja/test_tamno.py
03099cd5a6485b1764a46695ec18c29ed7013d6645477692f5bfc5ad5f87ce3b  otpad_katalog/schema.sql
9b10b8c651d9d88bcb341e73a04d639166ab35f4bb978c3ec8a2523f578e54b8  otpad_katalog/seed_probni.sql
3f74e62779049c4b2bddf568aefe568506d1d5eac511be7e94181d63e5d781e6  otpad_katalog/test_otpad_katalog.sh
2b7594b27a098fc97d12076be53721cf7fba127a042a68c2c347d1256df086eb  otpad_katalog/test_vin.py
c96731821d50b4144efeea212c7264923d968e0f4c5d9bb1b0f041ddf3b031c0  otpad_katalog/uloga_app.sql
a738cc17437b8fd59b6b302702c53095b2ca5ab3a4110c5e17e8b1a6b862105e  otpad_katalog/uloga_ekran.sql
a8d946d803b6986a1dbdd5d9e775b5b711b09498df6b9415e24374d0ec0c244a  otpad_katalog/uvezi_vozila.py
e47fbceb6ca7de7f31539266b74139b84e9200e5c8d7cd2158b48ebc7e3ece9e  otpad_katalog/vin.py
3db04d0b9564b1f198f9e6c4e88b50af42368b2c3f6bac58fe395f949535d056  otpad_katalog/vin_provjera.sql
da1fbc7ec9476278f3d6fb53e5ee3c6a3908a6f784a8585a40cc7b69bda9357e  otpad_katalog/wmi.csv

## 7. SHA-256 datoteka paketa za uvođenje (tuđi commit `71a756b1`) i izmijenjenih statičkih datoteka, na vrhu grane `b918cf11`
Provjera: `sed -n '/^## 7/,$p' KELAVA_VERIFIKACIJA.md | grep -E '^[0-9a-f]{64}  ' | while read h f; do [ "$(git show b918cf11d10bd20fa638fb2ac5ddf69032e5d269:"$f" | sha256sum | cut -d' ' -f1)" = "$h" ] && echo "OK  $f" || echo "PAD $f"; done`
dbbc14efd166bbb91d8681fb31bd5eb2cdab531c64eb5102753f10b46d7f56ad  otpad_katalog/deploy/README.md
dccca09c546ba5967adf86b47d0940530f20970c4cbc3bab0a7575caa804f655  otpad_katalog/deploy/deploy_eu.sh
88f066f35d68da9bb94e43128f6b02571719d6bd2811f6c0e91fc6648b009f08  otpad_katalog/deploy/nginx_otpad.conf
cf5cf4319a0a1e54aed1f80beb6f24e5dd50ad7984b0ef8a831232470bb4fea6  otpad_katalog/deploy/otpad-ekran.service
d6185284a10668151063431a94d5c116332cee5b29b00a6a14e627d12608ff2b  otpad_katalog/deploy/test_iza_nginxa.py
29fdd8973c75a40fd99e2fa1fa1d3f4102ad42a9c973cbb47598267eedc5d4f0  otpad_katalog/deploy/vozila.sql
7bcb411f0164cfe4d7c4d9bd5441b81f33b19910d9ae328ee3684cd68d956883  otpad_katalog/ekran/static/app.js
a84a0f4a5516ccba2763a60c44aaab534c7c0793173a4a264f34fae59ad5b23b  otpad_katalog/ekran/static/index.html
541ba23bc9726dcea8963be52ce94f7f25b05b30311e1752e35e746edea1deab  otpad_katalog/ekran/static/sw.js
8befe809a8bbdd79a94eb19478f5b9b4b174e50cd3ad8691dd52101127ec7ac8  otpad_katalog/ekran/static/tamno.js
