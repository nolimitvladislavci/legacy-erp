#!/usr/bin/env bash
# Test baze otpad_katalog na PRIVREMENOJ bazi (briše je i stvara iznova).
# Korištenje:
#   BRANDS_JS=<putanja/do/brands.js> ./test_otpad_katalog.sh
# Ako psql treba drugog korisnika: PSQL="runuser -u postgres -- psql -X -q -tA -v ON_ERROR_STOP=1"
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
PSQL="${PSQL:-psql -X -q -tA -v ON_ERROR_STOP=1}"
DB="${DB:-otpad_katalog_test}"
BRANDS_JS="${BRANDS_JS:?postavi BRANDS_JS na putanju do brands.js}"

TMPSQL="$(mktemp)"
PASS=0; FAIL=0
P()  { $PSQL -d "$DB" "$@"; }
PF() { $PSQL -d "$DB" < "$1"; }

ok() {  # ok "naziv" "očekivano" "dobiveno"
    if [ "$2" = "$3" ]; then PASS=$((PASS+1)); echo "PROŠLO  $1"
    else FAIL=$((FAIL+1)); echo "PALO    $1 | očekivano='$2' dobiveno='$3'"; fi
}
greska() {  # greska "naziv" "SQL"  -> mora završiti greškom
    if P -c "$2" >/dev/null 2>&1; then FAIL=$((FAIL+1)); echo "PALO    $1 | SQL je prošao, a trebao je pasti"
    else PASS=$((PASS+1)); echo "PROŠLO  $1"; fi
}

# --- priprema ---
$PSQL -d postgres -c "DROP DATABASE IF EXISTS $DB" >/dev/null
$PSQL -d postgres -c "CREATE DATABASE $DB ENCODING 'UTF8' TEMPLATE template0 LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8'" >/dev/null
PF "$DIR/schema.sql"  >/dev/null
PF "$DIR/pretraga.sql" >/dev/null
python3 "$DIR/uvezi_vozila.py" "$BRANDS_JS" > "$TMPSQL" 2>/dev/null
PF "$TMPSQL" >/dev/null

# očekivane brojke računamo NEZAVISNO iz izvorne datoteke
read -r OCEK_TIPOVA OCEK_MARKI OCEK_MODELA < <(python3 - "$BRANDS_JS" <<'E'
import json,sys
t=open(sys.argv[1],encoding='utf-8').read()
b=json.loads(t[t.index('['):t.rindex(']')+1])
tip={(x['brand'],m['name'],g['name'],g['yearFrom']) for x in b for m in x['models'] for g in m['generations']}
print(len(tip), len({x['brand'] for x in b}), len({(x['brand'],m['name']) for x in b for m in x['models'] if m['generations']}))
bez=[(x['brand'],m['name']) for x in b for m in x['models'] if not m['generations']]
print("NAPOMENA: modeli bez generacija (nema godišta, ne mogu se uvesti):", bez, file=sys.stderr)
E
)

# --- uvoz vozila ---
ok "vozilo_tip: broj tipova = $OCEK_TIPOVA"        "$OCEK_TIPOVA" "$(P -c 'SELECT count(*) FROM vozilo_tip')"
ok "marki = $OCEK_MARKI"                           "$OCEK_MARKI"  "$(P -c 'SELECT count(DISTINCT marka) FROM vozilo_tip')"
ok "modela (s bar jednom generacijom) = $OCEK_MODELA" "$OCEK_MODELA" "$(P -c 'SELECT count(DISTINCT (marka, model)) FROM vozilo_tip')"
PF "$TMPSQL" >/dev/null
ok "uvoz je idempotentan (drugi put isti broj)"   "$OCEK_TIPOVA" "$(P -c 'SELECT count(*) FROM vozilo_tip')"
ok "izvor 'auto-parts-db' postoji jednom"          "1" "$(P -c "SELECT count(*) FROM izvor WHERE naziv='auto-parts-db'")"

# --- pretraga vozila ---
ok "focus 2013 -> prvi red je Focus Mk III"        "Focus Mk III" "$(P -c "SELECT model || ' ' || generacija FROM trazi_vozilo('focus', 2013) LIMIT 1")"
ok "focus 2013 -> točan model Focus: točno 1 red"  "1" "$(P -c "SELECT count(*) FROM trazi_vozilo('focus', 2013) WHERE model='Focus'")"
ok "focus 2013 -> nađen i Focus kombi (srodni)"    "t" "$(P -c "SELECT count(*) > 0 FROM trazi_vozilo('focus', 2013) WHERE model='Focus kombi'")"
ok "ford fiesta 2010 -> Mk VI"                     "Mk VI"  "$(P -c "SELECT string_agg(generacija, ',') FROM trazi_vozilo('ford fiesta', 2010)")"
ok "focus 2004 -> 2 generacije Focusa (Mk I i Mk II, granična godina)" "2" "$(P -c "SELECT count(*) FROM trazi_vozilo('ford focus', 2004) WHERE model='Focus'")"
ok "ford focus 1990 -> 0"                          "0"      "$(P -c "SELECT count(*) FROM trazi_vozilo('ford focus', 1990)")"
ok "nepostojeće vozilo -> 0"                       "0"      "$(P -c "SELECT count(*) FROM trazi_vozilo('xyznemam')")"
ok "citroen (bez dijakritika) pronalazi Citroën"   "t"      "$(P -c "SELECT count(*) > 0 FROM trazi_vozilo('citroen')")"
ok "skoda octavia pronalazi vozilo"                "t"      "$(P -c "SELECT count(*) > 0 FROM trazi_vozilo('skoda octavia')")"
ok "velika/mala slova svejedno"                    "$(P -c "SELECT count(*) FROM trazi_vozilo('opel')")" "$(P -c "SELECT count(*) FROM trazi_vozilo('OPEL')")"

# --- normalizacija broja ---
ok "norm 'TST 100 001 A'"  "TST100001A" "$(P -c "SELECT norm_broj('TST 100 001 A')")"
ok "norm 'tst-100-001-a'"  "TST100001A" "$(P -c "SELECT norm_broj('tst-100-001-a')")"
ok "norm NULL -> prazno"   ""           "$(P -c "SELECT norm_broj(NULL)")"

# --- probni dijelovi ---
PF "$DIR/seed_probni.sql" >/dev/null
ok "20 probnih dijelova"                           "20" "$(P -c "SELECT count(*) FROM dio")"
PF "$DIR/seed_probni.sql" >/dev/null
ok "probni podaci idempotentni (i dalje 20)"       "20" "$(P -c "SELECT count(*) FROM dio")"
ok "broj 'TST 100 001 A' -> Alternator"            "Alternator" "$(P -c "SELECT DISTINCT naziv_hr FROM trazi_broj('TST 100 001 A')")"
ok "isti dio za 'tst-100-001-a'"                   "1" "$(P -c "SELECT count(DISTINCT dio_id) FROM trazi_broj('tst-100-001-a')")"
ok "isti dio za 'TST100001A'"                      "1" "$(P -c "SELECT count(DISTINCT dio_id) FROM trazi_broj('TST100001A')")"
ok "alternator: 1 na zalihi"                       "1" "$(P -c "SELECT max(na_zalihi) FROM trazi_broj('TST100001A')")"
ok "alternator stane na Focus Mk III"              "Mk III" "$(P -c "SELECT generacija FROM trazi_broj('TST100001A')")"
ok "far lijevi je prodan -> 0 na zalihi"           "0" "$(P -c "SELECT max(na_zalihi) FROM trazi_broj('TST 100 003 B')")"
ok "računalo motora stane na 2 tipa vozila"        "2" "$(P -c "SELECT count(*) FROM trazi_broj('TST 100 008 D')")"
ok "nepostojeći broj -> 0 redova"                  "0" "$(P -c "SELECT count(*) FROM trazi_broj('NEPOSTOJI 123')")"
ok "prazan upit -> 0 redova"                       "0" "$(P -c "SELECT count(*) FROM trazi_broj('')")"
ok "broj proizvođača vodi na isti dio"             "Alternator" "$(P -c "SELECT DISTINCT naziv_hr FROM trazi_broj('tstx-986-000-001')")"
ok "broj_norm na otpad_dio se računa sam"          "TST100001A" "$(P -c "SELECT broj_norm FROM otpad_dio WHERE broj_na_dijelu='tst-100-001-a'")"

# --- pravila baze (moraju odbiti loše podatke) ---
greska "pogrešan broj_norm se odbija"      "INSERT INTO dio_broj (dio_id,broj,broj_norm,vrsta) SELECT id,'ABC 1','KRIVO','OEM' FROM dio LIMIT 1"
greska "dvostruki broj za isti dio"        "INSERT INTO dio_broj (dio_id,broj,broj_norm,vrsta) SELECT dio_id,'TST 100 001 A',norm_broj('TST 100 001 A'),'OEM' FROM dio_broj WHERE broj_norm='TST100001A' AND vrsta='OEM' LIMIT 1"
greska "prazan broj se odbija"             "INSERT INTO dio_broj (dio_id,broj,broj_norm,vrsta) SELECT id,'---','','OEM' FROM dio LIMIT 1"
greska "VIN krive duljine se odbija"       "INSERT INTO otpad_vozilo (vin) VALUES ('KRATAK')"
greska "godina_do < godina_od se odbija"   "INSERT INTO vozilo_tip (marka,model,generacija,godina_od,godina_do) VALUES ('X','Y','Z',2010,2000)"
greska "nepoznat status se odbija"         "INSERT INTO otpad_dio (status) VALUES ('NEPOZNATO')"
greska "nepoznata vrsta broja se odbija"   "INSERT INTO dio_broj (dio_id,broj,broj_norm,vrsta) SELECT id,'A1',norm_broj('A1'),'KRIVA' FROM dio LIMIT 1"

# --- idempotentnost shema/pretraga ---
PF "$DIR/schema.sql"   >/dev/null 2>&1; ok "schema.sql se može pokrenuti ponovo" "0" "$?"
PF "$DIR/pretraga.sql" >/dev/null 2>&1; ok "pretraga.sql se može pokrenuti ponovo" "0" "$?"

rm -f "$TMPSQL"
echo "------"
echo "PROŠLO: $PASS | PALO: $FAIL"
[ "$FAIL" -eq 0 ]
