# Uvođenje Kelava ekrana na EU — `genesis.limit-connect.com/otpad/`

**Traži:** `DA uvedi-otpad-ekran eu-genesis` (A4) i izvršitelja s `exec` na EU (MAX nema `exec`).

## Naredbe (na EU, kao root, iz ove grane)
```
git clone --depth 1 -b claude/loving-babbage-gzx2xt https://github.com/nolimitvladislavci/legacy-erp /root/legacy-erp-otpad
cd /root/legacy-erp-otpad/otpad_katalog
sha256sum deploy/deploy_eu.sh        # mora biti isti kao u tablici dolje
bash deploy/deploy_eu.sh --suho      # exit 0 = sve provjere DRŽE, ništa nije promijenjeno
bash deploy/deploy_eu.sh             # izvedba; na kraju ispiše RAČUN hasheve i rollback naredbu
L=$(sed -n 's/^lozinka: //p' /root/otpad_pristup.txt)
OTPAD_JAVNI=https://genesis.limit-connect.com OTPAD_KORISNIK=kelava OTPAD_LOZINKA="$L" OTPAD_BEZ_UPISA=1 \
  python3 -I deploy/test_iza_nginxa.py   # treba playwright; ako ga EU nema, pokreće se izvana (bilo gdje)
```
Rollback: `bash /root/otpad_rollback_<TS>.sh` (skripta ga ispiše; radi `pg_dump` prije brisanja baze).

## Što mijenja
| Što | Gdje | Novo / izmjena |
|---|---|---|
| baza `otpad_kelava`, uloge `otpad_app`, `otpad_prodaja`, `otpad_ekran` | PostgreSQL EU | novo (bez izmišljenih dijelova; 4642 tipa vozila) |
| kod | `/var/www/otpad` | novo |
| venv (samo `psycopg[binary]==3.3.6`) | `/opt/otpad/venv` | novo |
| tajne (DSN lozinka) | `/etc/otpad/ekran.env` 0600 | novo, lozinka se nigdje ne ispisuje |
| slike (prijelazno, dok arhiva ne dobije servisnu sesiju) | `/var/lib/otpad/slike` 0700 www-data | novo |
| servis `otpad-ekran` | 127.0.0.1:8130, www-data, ProtectSystem=strict | novo |
| Basic prijava | `/etc/nginx/.otpad_htpasswd`, pristup u `/root/otpad_pristup.txt` 0600 | novo |
| nginx | `snippets/otpad.conf` novo; **1 linija** `include` u `genesis-eu` ispred `# qr_eho10_4dimenzije` | jedina izmjena postojeće datoteke (`.bak.<TS>`, `nginx -t`, automatski povrat ako padne) |
| lanac | INTENT/RAČUN za nginx i bazu + **naknadni** INTENT/RAČUN za obje zakrpe od 13.10. | `protokol/intent.py` |

Skripta odbija rad ako: baza ili uloge već postoje, port 8130 je zauzet, `nginx -t` pada već prije izmjene, sidro nije
jedinstveno, `vozila.sql` nije ona testirana, nedostaje `.bak` neke od zakrpa.

## Dokaz (lokalni kontejner koji oponaša EU: Postgres 16, nginx 1.24, lažni systemctl/intent.py)
| Naredba | Exit | Izlaz |
|---|---|---|
| `deploy_eu.sh --suho` (uloge već postoje) | 1 | `PAD uloge otpad_* već postoje` (čuvar radi) |
| `deploy_eu.sh --suho` | 0 | sve provjere DRŽE |
| `deploy_eu.sh` | 0 | 19 × DRŽI; otisak: samo site hash + 6 novih stavki |
| `test_iza_nginxa.py` | 0 | 33/33 (Chromium, uklj. servisni worker pod /otpad/ × 2 teme × 2 širine; Firefox/WebKit NEPOZNATO, nisu instalirani) |
| `otpad_rollback_<TS>.sh` | 0 | site sha256 vraćen na `89c4f680…` (identično prije) |

Nađeno testom: kroz proxy je ekran odbijao svaki POST („nepoznato podrijetlo") jer je `Host $host` gubio port.
Popravljeno u `nginx_otpad.conf` (`$http_host`); na EU (443, bez porta) bi radilo i prije, ali sada vrijedi svugdje.

| Datoteka | sha256 |
|---|---|
| `deploy_eu.sh` | `dccca09c546ba5967adf86b47d0940530f20970c4cbc3bab0a7575caa804f655` |
| `nginx_otpad.conf` | `88f066f35d68da9bb94e43128f6b02571719d6bd2811f6c0e91fc6648b009f08` |
| `otpad-ekran.service` | `cf5cf4319a0a1e54aed1f80beb6f24e5dd50ad7984b0ef8a831232470bb4fea6` |
| `vozila.sql` (iz `auto-parts-db@3.0.0` `brands.js` sha256 `7d33cd1b…ce19d`, `uvezi_vozila.py`) | `29fdd8973c75a40fd99e2fa1fa1d3f4102ad42a9c973cbb47598267eedc5d4f0` |

## Nije u ovom koraku
- Slike u poslovnu arhivu: čeka Kelava tenant + servisnu sesiju (Ivan), pa mjerenje iz `arhiva_spoj/README.md` korak 3.
- GenesisLogin umjesto Basic prijave; offline rad; prepoznavanje po slici (H1); Firefox/WebKit harness.
