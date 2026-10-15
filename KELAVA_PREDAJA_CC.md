# KELAVA — PREDAJA ZA CC (2026-10-15)
Ivan je predao posao Claude Codeu (CC). Ovo je sve što CC treba; kontinuitet je u repou i lancu, ne u sjećanju sesije.

## Gdje je što
- **Repo:** https://github.com/nolimitvladislavci/legacy-erp · **grana `claude/loving-babbage-gzx2xt`** · PR #1 (draft). Kod je u `otpad_katalog/`. (Repo je privremeno JAVAN — vratiti na Private: Settings → Danger Zone.)
- **Čitaj prvo:** `FENIX_SOBA.md` (što je rađeno + dnevnik pogrešaka), `KELAVA_VERIFIKACIJA.md` (sha256 i testovi), `KELAVA_BRIEF_ZA_FABLE.md` (odluke), `KELAVA_NEPROVJERENO.md` (neprovjereni brojevi), `otpad_katalog/deploy/README.md` (uvođenje).
- **Napomena:** `CLAUDE.md` u korijenu repoa opisuje drugi projekt (fina-connect); za Kelavu vrijedi ovaj dokument i USTAV v3 iz korisničkih postavki.

## Stanje na EU (provjereno 15.10.2026)
- Ekran `https://genesis.limit-connect.com/otpad/` (Basic prijava, korisnik `kelava`, lozinka u `/root/otpad_pristup.txt`), servis `otpad-ekran` 127.0.0.1:8130, kod `/var/www/otpad`, venv `/opt/otpad/venv`, tajne `/etc/otpad/ekran.env` (0600), slike `/var/lib/otpad/slike`.
- Baza `otpad_kelava`: `vozilo_tip` 4642, `dio` 296 (295 vrsta + 1 „srodne varijante NEPROVJERENO"), `dio_broj` 8, `otpad_dio` 0.
- Uvođenje: `deploy_eu.sh` GOTOVO 20261015T022023Z; rollback `bash /root/otpad_rollback_20261015T022023Z.sh`. Klon repoa: `/var/www/genesis/paketi/sandbox/kelava`.
- Lanac: atomi c13826–c13834 (naknadni INTENT/RAČUN za zakrpe arhive od 13.10. + uvođenje nginx i baze).
- Dvije izmjene postojećih datoteka (obje s `.bak`): `api/arhiva_core.py` (md5 `886084c5…`), `services/arhiva_core/strazar_ophodnja.py` (md5 `4705be01…`).
- Zadnji commit na grani: vidi `git log` (≥ `1ebd4efb`).

## Što je otvoreno (redom važnosti)
1. **GenesisLogin kao identitet uz Basic prijavu** — kod je u `otpad_katalog/wip_prijava/prijava_v2.patch` (`git apply` radi na vrh grane; 6 datoteka; NETESTIRANO). Pazi: `Authorization` zaglavlje koristi i nginx Basic pa Bearer treba ići u drugo zaglavlje (npr. `X-Genesis-Token`) ili prvo maknuti Basic. Popis dopuštenih `weise3_id` nitko nije dao; bez njega samo bilježi „tko".
2. **Slike u poslovnu arhivu** (`app_id=kelava-dijelovi`, bez AI obrade): treba tenant „Kelava" + servisna sesija (token; ključeve ne diraj bez Ivana). Mjerenje: `otpad_katalog/arhiva_spoj/README.md`.
3. **Katalog zamjenjivosti brojeva** — nema provjerenog izvora (TecDoc/ETKA licenca ili vlastita evidencija). Neprovjereni brojevi su odvojeni u zaseban `dio` i NIKAD ne idu pod isti dio kao provjereni.
4. **Harness iza nginxa na EU** (`deploy/test_iza_nginxa.py`, treba Playwright) i **test na pravom mobitelu**.
5. Q4D „živo srce" i Code 128 sloj; čitač knjižice vozila (plaćeni AI, limit troška = 0 dok nije upisan).

## Pravila (iz USTAVA v3, skraćeno)
- Produkcija = A4: `DA <radnja> <meta>` od Ivana; nikad ne potpisuj kanon lanca, ne diraj privatne ključeve, trošak 0 dok limit nije u lancu.
- `.bak` prije izmjene postojeće datoteke; INTENT/RAČUN atomi za svaku izmjenu (`protokol/intent.py` / `chain_upisi.sh`).
- Gotovo = triplet (naredba, exit, izlaz). Neprovjereno se piše kao NEPROVJERENO.
- Frontend: gumb disabled dok traje zahtjev, greške na ekranu, potvrda uspjeha.

## Testovi (TESTIRANO jednom, ne DOKAZANO)
Iz `otpad_katalog/`: `test_vin.py` 40, `prodaja/test_prodaja.py` 28, `prodaja/test_tamno.py` 48, `ekran/test_arhiva_spoj.py` 37, `ekran/test_tamno_ekran.py` 70, `ekran/test_preglednik_tamno.py` 148, `ekran/test_offline.py` 15. Treba PostgreSQL 16, Chromium (Playwright), `psycopg`.

## MAX/exec na EU (do 31.12.2026 23:59 UTC)
`exec_command` je ograničen: nginx -t/reload, systemctl status, py_compile, diff/sha256sum/md5sum, git čitanje, `chain_upisi.sh`, git clone/pip/venv/`deploy_eu.sh` samo pod `/var/www/genesis/paketi/sandbox/`. `write_file` ne radi mape. Opoziv: `rm /var/lib/genesis/mcp_exec_dozvola.json`.
