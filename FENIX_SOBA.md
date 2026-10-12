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
