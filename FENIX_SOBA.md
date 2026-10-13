# FENIX SOBA — soba za sastanke sesija (Staza A)

Zajednička datoteka na grani `claude/loving-babbage-gzx2xt`. Svaka sesija ovdje javi tko je i na čemu radi, kako se ne bismo razbacali.
**Ovo je JEDINA Fenix soba** (odluka Ivana: bez druge, odvojene Kanal sobe na New serveru).

## Pravila upisa
1. Dopisuj na kraj tablice **PRISUTNI**, ne mijenjaj tuđe retke.
2. Jedan redak po sesiji: ID sesije, naslov, što radiš, što je otvoreno, što trebaš od drugih.
3. Ažuriraj svoj redak kad se stanje promijeni (novi redak ispod, stari ostaje kao povijest).
4. Nikad ne upisuj ključeve, tokene ni lozinke.
5. Tvrdnje o stanju sustava nose triplet (naredba, exit kod, hash ili izlaz); bez njega su NAPISANO.
6. Commit poruka: `docs(soba): <sesija> <kratko>`. Prije pusha `git pull --rebase origin claude/loving-babbage-gzx2xt`.

## PRISUTNI

| UTC | ID sesije | Naslov | Radim na | Otvoreno / trebam |
|---|---|---|---|---|
| 2026-10-11 | session_01P5KN18DaRqxRrryzpCv9CK | Fenix sobu za sastanke | otvaranje sobe, pozivnice | DA za Stazu B; uzrok alarma na New i EU |

## DNEVNIK ODLUKA

### PREDAJA — session_01P5KN18DaRqxRrryzpCv9CK (stanje 2026-10-12)
- **Soba:** jedina soba je ovaj file (Ivan: bez Kanal sobe). Upisa drugih sesija još nema; nova laptop sesija u WSL-u tek treba nastati (sesija 016cP4… je `computer_unreachable`). Nalog za nju: kopija ovog filea u ~/Downloads, dvosmjerna sinkronizacija, sha256 obje kopije isti, upis retka u PRISUTNI.
- **MAR čišćenje na EU:** `borg/peers.json` (atomi c12781/c12782) i `BORG_PEERS` u `.env` (c12790/c12791) gotovo. **Restart `genesis` nije izveden** (Ivan je dao DA; čeka `exec_command` na EU). Provjera nakon restarta: `_peer_nedostupan.json` bez 212.227.181.201 u 2 ciklusa. Izuzeće u `ocekivano_odsutni.json` ostaje do toga.
- **dokarh-vlasnik petlja:** osumnjičen `memio-u-dokarh.service` (timer 00:45 i 12:45 UTC); 1 uhvaćeno + 1 neizravno od ≥3 potrebna. Uski tracer na EU: `/root/dokarh_pisac2_20261011T123524Z/pisac.log` (istekao ~00:35 UTC 12.10., prije termina 00:45).
- **Auto otpad / baza kataloških brojeva:** ATRIS Stahlgruber (+ Autodata 2003) je u Nufringenu, Ivan tamo za ~3 tjedna. Do tada: SQL shema (vozilo_tip, dio, dio_broj + normalizirani broj, dio_vozilo, otpad_vozilo, otpad_dio, izvor), probni uvoz Ford podataka iz NHTSA vPIC (polja Make_ID, Make_Name, Model_ID, Model_Name potvrđena), ekran s jednim poljem za radnicu. Čeka Ivanov "kreni". Postojeći moduli: `webshop`, `inventory`, `marketplace`.
- **Nalog CC-u (soba):** gotovo kad `git log -- FENIX_SOBA.md` ima ≥ 3 commita različitih sesija i sha256 kopije u Downloads = repo.

### DNEVNIK POGREŠAKA AI-a
- **2026-10-12, session_01P5KN18… — gradnja prije provjere (dupliciranje).**
  *Što:* počeo sam pisati vlastito spremanje slika dijelova i vlastiti AI čitač slika, a flota već ima
  `services/media_proc.py` (kompresija u WebP), `services/ocr.py` (lokalni Tesseract) i
  `services/dokarh_kamera_engine.py` (uvoz fotografije, WeisE3, Bršljan/Krunica).
  *Gdje:* `otpad_katalog/ekran/` (nedovršeno, parkirano u `git stash`, nije u grani).
  *Kako otkriveno:* Ivan je upozorio usred rada ("zašto ne provjeriš prvo").
  *Pravilo od sada (Korak Nula prije svakog novog modula):* pregledati `services/` na EU (ime + zaglavlje datoteke) i
  u PREDAJI upisati koji su postojeći moduli pregledani, PRIJE prve linije novog koda (Ustav §8, §2).

### IZVRŠENJE KELAVA_PLAN_K2 — session_01P5KN18DaRqxRrryzpCv9CK (2026-10-13)
- **N1 (gdje žive q4d i qr4d): ZATVOREN.** Na EU: `/var/www/genesis/qr4d/app.py` (servis `qr4d`, uvicorn, 127.0.0.1:8120, venv `/opt/qr4d/venv`, log `get_logs qr4d`),
  `/var/www/genesis/paketi/eho_v2/eho_v2/{q4d.py,qr_eho10_4dimenzije.py,kod4d.py}`, atomi c12422/c12423 (HUB3 propis). Plan je u Koraku Nula grešno javio "0 pogodaka": MAX `grep` je nepouzdan, a `qr4d` nije pod `/var/www/genesis/services`.
- **N2 (`/q/test` 500): ZATVOREN.** `GET /q/test` sada 200 (5384 B), `/api/v1/qr4d/stanje` 200, `/q/skener` 200; u logu `qr4d` sve 200 od 04:33 do 05:40 UTC 13.10.
  `genesis.limit-connect.com` i `limit-connect.com` → 217.160.71.124 (nije MAR 212.227.181.201), pa hipoteza o DNS-u na MAR otpada. 500 viđen 12.10. u 22:53 UTC bio je prolazan, uzrok nepoznat (log prozor ga ne pokriva).
- **N3 (root-pisac):** nije izveden. Treba `auditctl` na produkciji (A4, traži Ivanov DA) i `exec`, kojeg MAX nema.
- **N4:** čeka 10 fotografija Code 128 naljepnica i model skenera (Ivan). Jedini uzorak: `03407429544699306998215032` (26 znamenki, n=1, bez strukture).
- **Isporučeno** (testovi, TESTIRANO): `otpad_katalog/{vin.py,vin_provjera.sql,test_vin.py}` 40/40; `prodaja/` 28/28; `prodaja/{schema_tamno.sql,tamno.py,test_tamno.py}` 40/40.
- **DNEVNIK POGREŠAKA AI-a:** (1) `provjeri_svjetlo` je davao DRZI nad dnevnikom s krivotvorenim sadržajem (gledao samo spremljene hasheve); otkriveno testom V4; sada prvo zove `provjeri_lanac`. (2) u `schema_tamno.sql` upisao sam GRANT na nepostojeći stupac; uhvaćeno čitanjem prije pokretanja. (3) tvrdio sam "/q/test vraća 500" bez provjere ponavljanjem; kasnije mjerenje daje 200.

### EKRAN ZA PRETINCE I UNOS DIJELOVA — session_01P5KN18DaRqxRrryzpCv9CK (2026-10-13)
- **Pregledani moduli prije koda:** `ekran/server.py` i `static/*` (moji, prošli tjedan), `arhiva_core/ulaz.py` (jedini ulaz u poslovnu arhivu: asinkrono, traži kreatora/tenanta, piše u DokArh resolver), `prodaja/tamno.py`, `prodaja/prodaja.py`.
- **Slike dijelova pripadaju u poslovnu arhivu** (iz nje se gradi webshop; Ivan 13.10.), a Krunica ne nosi sadržaj slike. Moja ranija formulacija "ne smiju ući" bila je pogrešna i ispravljena u `spremnik.py`. Spajanje s `primi_dokument` NIJE gotovo (traži mjerenje: što `resolver.put` radi dalje, privatno/javno u arhivi); do tada lokalni spremnik izvan repoa.
- **Isporučeno:** nove kartice Novi dio · U radu · Stalaža; rute `/api/pretinci`, `/api/dio/...`, `/api/nadji`, `/api/slika/<id>`; uloga `otpad_ekran`. Testovi: `test_tamno_ekran.py` 64/64 (uklj. stari `test_ekran.py` 20/20), `test_preglednik_tamno.py` 132/132, stari `test_preglednik.py` 117 prošlo, 0 palo; `test_tamno.py` 40/40, `test_prodaja.py` 28/28.
- **DNEVNIK POGREŠAKA AI-a:** (1) uloga `otpad_prodaja` dobila je UPDATE na `token`, `otpad_vozilo_id`, `broj_na_dijelu` bez potrebe; uhvaćeno testom E13, sužena + REVOKE. (2) Potvrda "Slike su spremljene" nestajala je jer se kartica ponovno iscrtavala (isto bi se dogodilo i s porukom o grešci); uhvaćeno preglednik-testom, dodana trajna obavijest. (3) `server.py` nije radio s `python3 -I` (uvoz iz vlastite mape); popravljeno.
