#!/usr/bin/env bash
# Kelava otpad — uvođenje ekrana na EU (genesis.limit-connect.com/otpad/). Traži Ivanov:
#   DA uvedi-otpad-ekran eu-genesis
#
#   bash deploy_eu.sh --suho     # samo provjere i plan, NIŠTA ne mijenja (exit 0 = spremno)
#   bash deploy_eu.sh            # izvedi; na kraju ispiše RAČUN hasheve i rollback
#
# Što radi (sve novo osim JEDNE linije u nginx konfiguraciji):
#   baza otpad_kelava + uloge otpad_app/otpad_prodaja/otpad_ekran (bez probnih dijelova; vozila iz vozila.sql)
#   kod u /var/www/otpad, venv /opt/otpad/venv (samo psycopg), tajne u /etc/otpad/ekran.env (0600)
#   servis otpad-ekran (127.0.0.1:8130, www-data), slike u /var/lib/otpad/slike (0700)
#   nginx: snippets/otpad.conf + Basic prijava (.otpad_htpasswd), include ubačen u genesis-eu (sed, s .bak, nginx -t)
#   lanac: INTENT prije, RAČUN poslije (protokol/intent.py) + naknadni INTENT/RAČUN za dvije zakrpe od 13.10.
# Poslovna arhiva (slike) se NE uključuje: čeka Kelava tenant + servisnu sesiju (ARHIVA_* varijable, vidi arhiva_spoj/README.md).
set -euo pipefail

SUHO=0; [[ "${1:-}" == "--suho" ]] && SUHO=1
R="${OTPAD_ROOT:-}"                                   # prefiks za test (prazno = pravi sustav)
PSQL="${PSQL:-runuser -u postgres -- psql -X -q -tA -v ON_ERROR_STOP=1}"
SYSTEMCTL="${SYSTEMCTL:-systemctl}"
NGINX="${NGINX:-nginx}"
INTENT="${INTENT:-python3 /var/www/genesis/protokol/intent.py}"
SITE_LINK="${NGINX_SITE:-$R/etc/nginx/sites-enabled/genesis-eu}"
JAVNI="${JAVNI_URL:-https://genesis.limit-connect.com}"
SESIJA="${SESIJA:-session_01KME8WP5HfMkATwKt7L9dke}"
DB=otpad_kelava; PORT=8130
TS="$(date -u +%Y%m%dT%H%M%SZ)"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # otpad_katalog/
VOZILA_SHA=29fdd8973c75a40fd99e2fa1fa1d3f4102ad42a9c973cbb47598267eedc5d4f0
SIDRO='# qr_eho10_4dimenzije'                            # include ide ispred ove linije (jedinstvena u datoteci)
INC_LINIJA='    include /etc/nginx/snippets/otpad.conf;   # Kelava otpad ekran (otpad_katalog/deploy)'
ZAKRPE=("$R/var/www/genesis/api/arhiva_core.py|$R/var/www/genesis/api/arhiva_core.py.bak_20261013_062313"
        "$R/var/www/genesis/services/arhiva_core/strazar_ophodnja.py|$R/var/www/genesis/services/arhiva_core/strazar_ophodnja.py.bak_20261013_064239")

ok()  { printf '  DRŽI  %s\n' "$*"; }
pad() { printf '  PAD   %s\n' "$*" >&2; [[ -n "${RB:-}" ]] && echo "  vrati stanje: bash $RB" >&2; exit 1; }
sha() { sha256sum "$1" | cut -c1-64; }
P()   { $PSQL "$@"; }

SITE="$(readlink -f "$SITE_LINK")"                    # sed -i na simboličkoj vezi bi je pretvorio u datoteku

echo "== PROVJERE (A0) $TS"
[[ $EUID -eq 0 || -n "$R" ]] || pad "pokreni kao root"
[[ "$(sha "$SRC/deploy/vozila.sql")" == "$VOZILA_SHA" ]] && ok "vozila.sql sha256 = $VOZILA_SHA" || pad "vozila.sql nije ona testirana"
for f in schema.sql pretraga.sql uloga_app.sql vin_provjera.sql prodaja/schema_prodaja.sql prodaja/schema_tamno.sql uloga_ekran.sql ekran/server.py; do
    [[ -f "$SRC/$f" ]] || pad "nema $f"
done; ok "izvorne datoteke na mjestu"
[[ -f "$SITE" ]] || pad "nema nginx site $SITE"
[[ "$(grep -cF "$SIDRO" "$SITE")" == 1 ]] && ok "sidro za include jedinstveno u $SITE" || pad "sidro '$SIDRO' nije točno jednom"
grep -qF 'snippets/otpad.conf' "$SITE" && pad "include već postoji (već uvedeno?)"
$NGINX -t >/dev/null 2>&1 && ok "nginx -t prije izmjene" || pad "nginx -t pada već PRIJE izmjene — ne diram"
if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]$PORT\$"; then pad "port $PORT zauzet"; fi; ok "port $PORT slobodan"
[[ -z "$(P -d postgres -c "SELECT 1 FROM pg_database WHERE datname='$DB'")" ]] && ok "baza $DB ne postoji" || pad "baza $DB već postoji"
[[ -z "$(P -d postgres -c "SELECT string_agg(rolname,',') FROM pg_roles WHERE rolname IN ('otpad_app','otpad_prodaja','otpad_ekran')")" ]] \
    && ok "uloge otpad_* ne postoje" || pad "uloge otpad_* već postoje"
for z in "${ZAKRPE[@]}"; do f="${z%%|*}"; b="${z##*|}"; [[ -f "$f" && -f "$b" ]] || pad "nema $f ili $b"; done; ok "obje zakrpe i njihovi .bak postoje"
[[ -e "$R/etc/systemd/system/otpad-ekran.service" ]] && pad "otpad-ekran.service već postoji"
command -v openssl >/dev/null || pad "nema openssl"
python3 -c 'import venv' 2>/dev/null || pad "nema python3 venv"

H_SITE_PRIJE="$(sha "$SITE")"
otisak() { { echo "site $(sha "$SITE")"; ls -1 "$R/etc/systemd/system" | sort; P -d postgres -c "SELECT datname FROM pg_database ORDER BY 1";
             P -d postgres -c "SELECT rolname FROM pg_roles ORDER BY 1"; ls -1 "$R/etc/nginx/snippets" | sort; } ; }
OTISAK_PRIJE="$(otisak)"

if [[ $SUHO == 1 ]]; then
    echo "== SUHO: sve provjere prošle. Izmijenila bi se samo $SITE (1 linija, sha256 $H_SITE_PRIJE); ostalo je novo."
    exit 0
fi

echo "== 0. NAKNADNI INTENT/RAČUN za zakrpe od 13.10. (izvedene bez atoma, FENIX_SOBA.md)"
for z in "${ZAKRPE[@]}"; do f="${z%%|*}"; b="${z##*|}"; p="${f#$R}"
    i="$($INTENT najavi "$p" "$(sha "$b")" "$SESIJA" "NAKNADNO: zakrpa kelava-dijelovi izvedena 13.10. bez atoma (Ivanov DA)")" || true
    r="$($INTENT racun "$p" "$(sha "$b")" "$(sha "$f")" "$SESIJA" "$i")" || true
    echo "  $p  $(sha "$b") -> $(sha "$f")  INTENT=$i RAČUN=$r"
done

echo "== 1. INTENT za uvođenje"
I_SITE="$($INTENT najavi "${SITE#$R}" "$H_SITE_PRIJE" "$SESIJA" "include /etc/nginx/snippets/otpad.conf (Kelava ekran /otpad/)")" || I_SITE=NEPOZNATO
I_DB="$($INTENT najavi "postgres:$DB" "-" "$SESIJA" "nova baza $DB + uloge otpad_* + servis otpad-ekran")" || I_DB=NEPOZNATO
echo "  INTENT site=$I_SITE baza=$I_DB"

RB="$R/root/otpad_rollback_$TS.sh"; mkdir -p "$(dirname "$RB")"
cat > "$RB" <<EOF
#!/usr/bin/env bash
# Rollback uvođenja Kelava ekrana ($TS). Prije brisanja baze radi dump.
set -u
cp -p "$SITE.bak.$TS" "$SITE" && $NGINX -t && $SYSTEMCTL reload nginx
$SYSTEMCTL disable --now otpad-ekran 2>/dev/null; rm -f "$R/etc/systemd/system/otpad-ekran.service"; $SYSTEMCTL daemon-reload
rm -f "$R/etc/nginx/snippets/otpad.conf" "$R/etc/nginx/.otpad_htpasswd"
runuser -u postgres -- pg_dump $DB > "$R/root/otpad_kelava_dump_\$(date -u +%Y%m%dT%H%M%SZ).sql" 2>/dev/null
$PSQL -d postgres -c "DROP DATABASE IF EXISTS $DB"
$PSQL -d postgres -c "DROP ROLE IF EXISTS otpad_ekran" -c "DROP ROLE IF EXISTS otpad_prodaja" -c "DROP ROLE IF EXISTS otpad_app"
rm -rf "$R/var/www/otpad" "$R/opt/otpad" "$R/etc/otpad"   # /var/lib/otpad/slike se NE briše (ručno, ako treba)
echo "rollback gotov; sha256 site: \$(sha256sum "$SITE" | cut -c1-64) (očekivano $H_SITE_PRIJE)"
EOF
chmod 0700 "$RB"; echo "  rollback: bash $RB"
trap 'echo "  PAD usred izvođenja — vrati stanje: bash $RB" >&2' ERR

echo "== 2. Baza $DB"
P -d postgres -c "CREATE DATABASE $DB ENCODING 'UTF8' TEMPLATE template0 LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8'"
P -d "$DB" -c "REVOKE ALL ON DATABASE $DB FROM PUBLIC"
for f in schema.sql pretraga.sql uloga_app.sql vin_provjera.sql prodaja/schema_prodaja.sql prodaja/schema_tamno.sql uloga_ekran.sql; do
    P -d "$DB" < "$SRC/$f"
done
P -d "$DB" < "$SRC/deploy/vozila.sql"
LOZ="$(openssl rand -hex 24)"
P -d "$DB" -c "ALTER ROLE otpad_ekran PASSWORD '$LOZ'" -c "GRANT CONNECT ON DATABASE $DB TO otpad_ekran"
N_VOZ="$(P -d "$DB" -c 'SELECT count(*) FROM vozilo_tip')"; N_DIO="$(P -d "$DB" -c 'SELECT count(*) FROM dio')"
[[ "$N_VOZ" == 4642 ]] && ok "vozilo_tip = 4642" || pad "vozilo_tip = $N_VOZ (očekivano 4642)"
[[ "$N_DIO" == 0 ]] && ok "dio = 0 (nema izmišljenih brojeva)" || pad "dio = $N_DIO"

echo "== 3. Kod, venv, tajne"
install -d -m 0755 "$R/var/www/otpad"
cp -a "$SRC/." "$R/var/www/otpad/"; rm -rf "$R/var/www/otpad/deploy"
chown -R root:root "$R/var/www/otpad"; chmod -R a+rX,go-w "$R/var/www/otpad"
python3 -m venv "$R/opt/otpad/venv"
"$R/opt/otpad/venv/bin/pip" install -q "psycopg[binary]==3.3.6"
install -d -m 0700 -o www-data -g www-data "$R/var/lib/otpad" "$R/var/lib/otpad/slike"
install -d -m 0700 "$R/etc/otpad"
umask 077
cat > "$R/etc/otpad/ekran.env" <<EOF
OTPAD_DSN="host=127.0.0.1 dbname=$DB user=otpad_ekran password=$LOZ"
OTPAD_PORT=$PORT
OTPAD_SLIKE=/var/lib/otpad/slike
QR4D_URL=http://127.0.0.1:8120
EOF
umask 022; chmod 0600 "$R/etc/otpad/ekran.env"; unset LOZ
ok "ekran.env 0600, lozinka nije ispisana"

echo "== 4. Servis otpad-ekran"
install -m 0644 "$SRC/deploy/otpad-ekran.service" "$R/etc/systemd/system/otpad-ekran.service"
$SYSTEMCTL daemon-reload; $SYSTEMCTL enable --now otpad-ekran
for _ in $(seq 1 30); do curl -fsS -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null && break; sleep 1; done
K="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/")"; [[ "$K" == 200 ]] && ok "lokalno / → 200" || pad "lokalno / → $K"
K="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/pretinci")"; [[ "$K" == 200 ]] && ok "lokalno /api/pretinci → 200 (baza spojena)" || pad "/api/pretinci → $K"

echo "== 5. nginx"
KORISNIK=kelava; LOZ_W="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)"
printf '%s:%s\n' "$KORISNIK" "$(openssl passwd -apr1 "$LOZ_W")" > "$R/etc/nginx/.otpad_htpasswd"
chown root:www-data "$R/etc/nginx/.otpad_htpasswd"; chmod 0640 "$R/etc/nginx/.otpad_htpasswd"
umask 077; printf 'Kelava ekran: %s/otpad/\nkorisnik: %s\nlozinka: %s\n' "$JAVNI" "$KORISNIK" "$LOZ_W" > "$R/root/otpad_pristup.txt"; umask 022
install -m 0644 "$SRC/deploy/nginx_otpad.conf" "$R/etc/nginx/snippets/otpad.conf"
cp -p "$SITE" "$SITE.bak.$TS"
sed -i "/^[[:space:]]*$SIDRO/i\\$INC_LINIJA" "$SITE"
[[ "$(grep -cF 'snippets/otpad.conf' "$SITE")" == 1 ]] || { cp -p "$SITE.bak.$TS" "$SITE"; pad "include nije ubačen točno jednom (vraćeno)"; }
D="$(diff "$SITE.bak.$TS" "$SITE" | grep -c '^[<>]' || true)"; [[ "$D" == 1 ]] && ok "diff site = točno 1 dodana linija" || { cp -p "$SITE.bak.$TS" "$SITE"; pad "diff site = $D linija (vraćeno)"; }
if ! $NGINX -t >/dev/null 2>&1; then cp -p "$SITE.bak.$TS" "$SITE"; $NGINX -t >/dev/null 2>&1; pad "nginx -t pao nakon izmjene — vraćeno, reload NIJE rađen"; fi
ok "nginx -t nakon izmjene"
$SYSTEMCTL reload nginx; sleep 1
K="$(curl -s -o /dev/null -w '%{http_code}' "$JAVNI/otpad/")";                      [[ "$K" == 401 ]] && ok "javno bez prijave → 401" || pad "javno bez prijave → $K"
K="$(curl -s -o /dev/null -w '%{http_code}' -u "$KORISNIK:$LOZ_W" "$JAVNI/otpad/")";  [[ "$K" == 200 ]] && ok "javno s prijavom → 200" || pad "javno s prijavom → $K"
K="$(curl -s -o /dev/null -w '%{http_code}' -u "$KORISNIK:$LOZ_W" "$JAVNI/otpad/api/pretinci")"; [[ "$K" == 200 ]] && ok "javno /otpad/api/pretinci → 200" || pad "→ $K"
K="$(curl -s -o /dev/null -w '%{http_code}' "$JAVNI/health")";                       [[ "$K" == 200 ]] && ok "genesis /health → 200 (ostatak nedirnut)" || pad "/health → $K"
unset LOZ_W

echo "== 6. RAČUN + otisak"
H_SITE_POSLIJE="$(sha "$SITE")"
R_SITE="$($INTENT racun "${SITE#$R}" "$H_SITE_PRIJE" "$H_SITE_POSLIJE" "$SESIJA" "$I_SITE")" || R_SITE=NEPOZNATO
R_DB="$($INTENT racun "postgres:$DB" "-" "$(P -d "$DB" -c "SELECT md5(string_agg(table_name,',' ORDER BY table_name)) FROM information_schema.tables WHERE table_schema='public'")" "$SESIJA" "$I_DB")" || R_DB=NEPOZNATO
OTISAK_POSLIJE="$(otisak)"
echo "  razlika otiska (očekivano: site hash, otpad-ekran.service, otpad_kelava, 3 uloge otpad_*, otpad.conf):"
diff <(echo "$OTISAK_PRIJE") <(echo "$OTISAK_POSLIJE") | grep '^[<>]' | sed 's/^/    /' || true
echo
echo "GOTOVO $TS"
echo "  site     $H_SITE_PRIJE -> $H_SITE_POSLIJE   INTENT=$I_SITE RAČUN=$R_SITE"
echo "  baza     $DB   INTENT=$I_DB RAČUN=$R_DB"
echo "  pristup  /root/otpad_pristup.txt (0600)"
echo "  rollback bash $RB"
