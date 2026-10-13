#!/usr/bin/env python3
"""Test HTTP sloja za tamni dio (pretinci, rođenje, slike, predradnje, prodaja, pronalaženje) + regresija starog ekrana.

Sam stvara PRIVREMENU bazu otpad_ekran_test, pokreće server na portu 8791 (i drugi bez spremnika slika na 8792) i briše sve.
Kriteriji (upisani prije pokretanja), svaki red je zaseban slučaj:
  E1 stranica nosi nove kartice, tamno.js se poslužuje · E2 pretinci: stvaranje, ponavljanje bez duplikata, neispravan unos
  E3 popis i sadržaj pretinca (nepostojeći 404) · E4 CSRF/Origin odbijeni · E5 rođenje: poznat, nepoznat, bez auta, duplikat
  E6 slika: JPEG prolazi, ponovljena 409, ne-slika 415, krivi tip 400, prevelika 413, dohvat bajt-identičan, bez spremnika 503
  E7 predradnje traže dokaz (slika, dimenzije) · E8 pretinac: neispravan 400, nepostojeći 409, spremanje, premještaj
  E9 vrata: nepotpun 409 s popisom razloga, potpun prolazi, drugi put 409 · E10 izlazni atomi i javne slike
  E11 pronalaženje po pretincu, oznaki, broju, ništa · E12 popis u radu · E13 uloga ne smije DELETE · E14 stari unos radi
  R1 postojeći test_ekran.py (20) nad istim poslužiteljem
Pokretanje:  BRANDS_JS=<put/do/brands.js> python3 -I test_tamno_ekran.py   (traži runuser -u postgres, zxing nije potreban)
"""
from __future__ import annotations

import io
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

AQ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(AQ, "prodaja"))
import psycopg  # noqa: E402

import test_prodaja as H  # noqa: E402

DB = "otpad_ekran_test"
LOZ = secrets.token_hex(8)
PORT, PORT2 = 8791, 8792
URL, URL2 = f"http://127.0.0.1:{PORT}", f"http://127.0.0.1:{PORT2}"
DSN = f"host=127.0.0.1 dbname={DB} user=otpad_ekran password={LOZ}"
ok = H.ok


def zahtjev(metoda, put, tijelo=None, zaglavlja=None, osnova=URL, sirovo=None):
    z = dict(zaglavlja or {})
    data = None
    if sirovo is not None:
        data = sirovo
        z.setdefault("X-Requested-With", "otpad")
    elif tijelo is not None:
        data = json.dumps(tijelo).encode()
        z.setdefault("Content-Type", "application/json")
        z.setdefault("X-Requested-With", "otpad")
    r = urllib.request.Request(osnova + put, data=data, method=metoda, headers=z)
    try:
        with urllib.request.urlopen(r, timeout=30) as o:
            raw = o.read()
            tip = o.headers.get("Content-Type", "")
            return o.status, (json.loads(raw or b"{}") if "json" in tip else raw), dict(o.headers)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw), dict(e.headers)
        except ValueError:
            return e.code, {"raw": raw.decode(errors="replace")}, dict(e.headers)


def jpeg(boja: int) -> bytes:
    from PIL import Image
    im = Image.new("RGB", (240, 180), (boja % 256, (boja * 7) % 256, (boja * 13) % 256))
    for i in range(0, 240, 6):
        im.putpixel((i, (i * boja) % 180), (255, 255, 255))
    b = io.BytesIO(); im.save(b, "JPEG", quality=85)
    return b.getvalue()


def q(sql, *a):
    with psycopg.connect(DSN) as c, c.cursor() as cur:
        cur.execute(sql, a or None)
        return cur.fetchall() if cur.description else None


def pokreni(port, slike):
    env = {**os.environ, "OTPAD_DSN": DSN, "OTPAD_PORT": str(port)}
    env.pop("OTPAD_SLIKE", None)
    if slike:
        env["OTPAD_SLIKE"] = slike
    p = subprocess.Popen([sys.executable, "-I", os.path.join(AQ, "ekran", "server.py")], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/favicon.ico", timeout=1)
            return p
        except Exception:                                                        # noqa: BLE001
            time.sleep(0.2)
    raise SystemExit("server se nije pokrenuo")


def postavi_bazu(brands: str) -> None:
    """Privremena baza sa svim shemama, ulogom otpad_ekran, vozilima i jednim otpad_vozilom."""
    H.psql("postgres", f"DROP DATABASE IF EXISTS {DB}"); H.psql("postgres", f"CREATE DATABASE {DB}")
    for f in ("schema.sql", "pretraga.sql", "uloga_app.sql", "prodaja/schema_prodaja.sql", "prodaja/schema_tamno.sql", "uloga_ekran.sql"):
        H.psql(DB, datoteka=os.path.join(AQ, f))
    if brands and os.path.exists(brands):
        sql = subprocess.run([sys.executable, "-I", os.path.join(AQ, "uvezi_vozila.py"), brands], capture_output=True, text=True).stdout
        tmp = tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False); tmp.write(sql); tmp.close(); os.chmod(tmp.name, 0o644)
        H.psql(DB, datoteka=tmp.name); os.unlink(tmp.name)
        H.psql(DB, datoteka=os.path.join(AQ, "seed_probni.sql"))
    else:
        H.psql(DB, "INSERT INTO vozilo_tip (marka, model, generacija, godina_od) VALUES ('Ford','Focus','II',2004)")
    H.psql(DB, f"ALTER ROLE otpad_ekran PASSWORD '{LOZ}'")
    H.psql(DB, "INSERT INTO otpad_vozilo (vin, vozilo_tip_id, km) SELECT 'WVWZZZ1JZ3W386752', id, 150000 FROM vozilo_tip LIMIT 1")


def main() -> int:
    brands = os.environ.get("BRANDS_JS", "")
    try:
        postavi_bazu(brands)
    except Exception as e:                                                       # noqa: BLE001
        print(f"PRIPREMA PALA: {e}"); return 2
    slike_dir = tempfile.mkdtemp(prefix="otpad_slike_")
    os.chmod(slike_dir, 0o700)
    s1, s2 = pokreni(PORT, slike_dir), pokreni(PORT2, None)
    try:
        auto = q("SELECT id FROM otpad_vozilo ORDER BY id LIMIT 1")[0][0]

        # E1
        st, html, h = zahtjev("GET", "/")
        ok("E1 stranica ima kartice Novi dio, U radu, Stalaža", all(x.encode() in html for x in ("Novi dio", "U radu", "Stalaža")))
        ok("E1 tamno.js se poslužuje", zahtjev("GET", "/tamno.js")[0] == 200)
        ok("E1 CSP dopušta slike iz istog izvora i blob:", "img-src 'self' blob:" in h["Content-Security-Policy"])

        # E2, E3
        st, r, _ = zahtjev("POST", "/api/pretinci", {"regal": 3, "polica": 2, "pretinaca": 8})
        ok("E2 stvaranje 8 pretinaca", st == 201 and r["nova"] == 8, str(r))
        st, r, _ = zahtjev("POST", "/api/pretinci", {"regal": 3, "polica": 2, "pretinaca": 8})
        ok("E2 ponavljanje ne duplicira", st == 201 and r["nova"] == 0 and r["vec_postojala"] == 8, str(r))
        zahtjev("POST", "/api/pretinci", {"regal": 1, "polica": 1, "pretinaca": 2})
        ok("E2 neispravan regal 0 → 400", zahtjev("POST", "/api/pretinci", {"regal": 0, "polica": 1, "pretinaca": 2})[0] == 400)
        ok("E2 polica 'x' → 400", zahtjev("POST", "/api/pretinci", {"regal": 1, "polica": "x", "pretinaca": 2})[0] == 400)
        st, r, _ = zahtjev("GET", "/api/pretinci")
        ok("E3 popis sadrži 10 pretinaca", st == 200 and len(r["pretinci"]) == 10 and r["pretinci"][0]["adresa"] == "R01-P1-01", str(r)[:120])
        ok("E3 sadržaj pretinca (prazan)", zahtjev("GET", "/api/pretinac/R03-P2-04")[1]["dijelovi"] == [])
        ok("E3 nepostojeći pretinac → 404", zahtjev("GET", "/api/pretinac/R99-P9-99")[0] == 404)

        # E4
        r = urllib.request.Request(URL + "/api/pretinci", data=b'{"regal":5,"polica":1,"pretinaca":1}', method="POST", headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(r); kod = 200
        except urllib.error.HTTPError as e:
            kod = e.code
        ok("E4 POST bez X-Requested-With → 403", kod == 403)
        ok("E4 tuđi Origin → 403", zahtjev("POST", "/api/pretinci", {"regal": 5, "polica": 1, "pretinaca": 1}, {"Origin": "http://zlo.example"})[0] == 403)
        ok("E4 tuđi pokušaj nije ništa stvorio", q("SELECT count(*) FROM pretinac WHERE adresa LIKE 'R05%'")[0][0] == 0)

        # E5
        st, r1, _ = zahtjev("POST", "/api/dio/rodi", {"otpad_vozilo_id": auto, "broj_na_dijelu": "0 124 525 040", "naziv": "Alternator"})
        ok("E5 rođenje poznatog dijela", st == 201 and len(r1["token"]) == 16 and r1["id"] > 0, str(r1))
        st, r2, _ = zahtjev("POST", "/api/dio/rodi", {"otpad_vozilo_id": auto})
        ok("E5 nepoznat dio (bez broja i naziva) se ipak rađa", st == 201, str(r2))
        ok("E5 bez auta → 400", zahtjev("POST", "/api/dio/rodi", {"naziv": "x"})[0] == 400)
        st, r, _ = zahtjev("POST", "/api/dio/rodi", {"otpad_vozilo_id": auto, "broj_na_dijelu": "0124525040", "naziv": "Alternator"})
        ok("E5 isti broj za isti auto → 409 duplikat", st == 409 and r.get("duplikat") is True, str(r))
        st, r3, _ = zahtjev("POST", "/api/dio/rodi", {"otpad_vozilo_id": auto, "broj_na_dijelu": "0124525040", "naziv": "Alternator", "dopusti_duplikat": True})
        ok("E5 uz potvrdu duplikat prolazi", st == 201, str(r3))
        d = r1["id"]

        # E6
        j = [jpeg(k) for k in range(1, 8)]
        for k in range(3):
            st, r, _ = zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "DIO", "Content-Type": "image/jpeg"}, sirovo=j[k])
            ok(f"E6 JPEG {k + 1}/3 prolazi", st == 201 and r["slika"] > 0, str(r))
        st, r, _ = zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "DIO", "Content-Type": "image/jpeg"}, sirovo=j[0])
        ok("E6 ista slika dvaput → 409", st == 409, f"{st} {r}")
        ok("E6 ne-slika → 415", zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "DIO"}, sirovo=b"ovo nije slika")[0] == 415)
        ok("E6 krivi tip slike → 400", zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "SELFIE"}, sirovo=j[3])[0] == 400)
        import http.client
        hc = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
        hc.putrequest("POST", f"/api/dio/{d}/slika"); hc.putheader("X-Requested-With", "otpad"); hc.putheader("X-Vrsta", "DIO")
        hc.putheader("Content-Type", "image/jpeg"); hc.putheader("Content-Length", str(15 * 1024 * 1024 + 1)); hc.endheaders()
        kod413 = hc.getresponse().status; hc.close()
        ok("E6 prevelika (Content-Length > 15 MB) → 413 bez čitanja tijela", kod413 == 413, str(kod413))
        sid = q("SELECT id FROM dio_slika WHERE otpad_dio_id=%s AND vrsta='DIO' ORDER BY id LIMIT 1", d)[0][0]
        st, b, h = zahtjev("GET", f"/api/slika/{sid}")
        ok("E6 dohvat slike je bajt-identičan i privatan", st == 200 and b == j[0] and "no-store" in h.get("Cache-Control", ""))
        ok("E6 slika bez spremnika na poslužitelju → 503", zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "DIO"}, sirovo=j[4], osnova=URL2)[0] == 503)
        ok("E6 slika nije u bazi kao blob (samo veza i otisak)", q("SELECT count(*) FROM dio_slika WHERE ref NOT LIKE 'lokalno:%'")[0][0] == 0)
        ok("E6 nepostojeći dio → 409/404, ne 500", zahtjev("POST", "/api/dio/99999/slika", zaglavlja={"X-Vrsta": "DIO"}, sirovo=j[5])[0] in (404, 409))

        # E7, E8
        ok("E7 OPRAN bez slike poslije pranja → 409", zahtjev("POST", f"/api/dio/{d}/predradnja", {"vrsta": "OPRAN"})[0] == 409)
        zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "POSLIJE_PRANJA"}, sirovo=j[5])
        ok("E7 OPRAN sa slikom prolazi", zahtjev("POST", f"/api/dio/{d}/predradnja", {"vrsta": "OPRAN"})[0] == 201)
        ok("E7 test sa stanjem 'valjda' → 409", zahtjev("POST", f"/api/dio/{d}/predradnja", {"vrsta": "TESTIRAN", "stanje": "VALJDA"})[0] == 409)
        ok("E7 test DRZI prolazi", zahtjev("POST", f"/api/dio/{d}/predradnja", {"vrsta": "TESTIRAN", "stanje": "DRZI", "napomena": "kratki test"})[0] == 201)
        ok("E7 pakiranje s krivim dimenzijama → 400", zahtjev("POST", f"/api/dio/{d}/predradnja", {"vrsta": "PAKIRAN", "dimenzije_cm": "velika kutija", "tezina_g": 100})[0] == 400)
        ok("E7 pakiranje bez slike paketa → 409", zahtjev("POST", f"/api/dio/{d}/predradnja", {"vrsta": "PAKIRAN", "dimenzije_cm": "30x20x15", "tezina_g": 3200})[0] == 409)
        zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "PAKET"}, sirovo=j[6])
        ok("E7 pakiranje s dokazom prolazi", zahtjev("POST", f"/api/dio/{d}/predradnja", {"vrsta": "PAKIRAN", "dimenzije_cm": "30x20x15", "tezina_g": 3200})[0] == 201)
        ok("E7 nepoznata predradnja → 400", zahtjev("POST", f"/api/dio/{d}/predradnja", {"vrsta": "POLIRAN"})[0] == 400)
        ok("E8 neispravna adresa pretinca → 400", zahtjev("POST", f"/api/dio/{d}/spremi", {"adresa": "polica 3"})[0] == 400)
        ok("E8 nepostojeći pretinac → 409", zahtjev("POST", f"/api/dio/{d}/spremi", {"adresa": "R09-P9-09"})[0] == 409)
        ok("E8 prodaja prije pretinca odbijena (razlog: lokacija)", "lokacija nije poznata" in " ".join(zahtjev("POST", f"/api/dio/{d}/prodaja", {"cijena": "45", "razred_jamstva": "POTROSAC_12M", "javne_slike": [sid]})[1].get("razlozi", [])))
        st, r, _ = zahtjev("POST", f"/api/dio/{d}/spremi", {"adresa": "R03-P2-04"})
        ok("E8 spremanje u pretinac → NA_STALAZI", st == 201 and r["status"] == "NA_STALAZI", str(r))
        ok("E8 premještaj", zahtjev("POST", f"/api/dio/{d}/spremi", {"adresa": "R01-P1-02"})[0] == 201 and zahtjev("GET", f"/api/dio/{d}")[1]["pretinac"] == "R01-P1-02")

        # E9, E10
        st, k, _ = zahtjev("GET", f"/api/dio/{d}")
        ok("E9 kartica nosi checklistu", k["checklist"]["opran"] and k["checklist"]["pakiran"] and k["checklist"]["test"] == "DRZI" and k["checklist"]["slika_dio"] == 3, str(k["checklist"]))
        n2 = r2["id"]
        st, r, _ = zahtjev("POST", f"/api/dio/{n2}/prodaja", {"cijena": "10", "razred_jamstva": "POTROSAC_12M", "javne_slike": []})
        ok("E9 nepotpun dio: 409 s popisom razloga (≥ 4)", st == 409 and len(r.get("razlozi", [])) >= 4, str(r))
        ok("E9 cijena 'abc' → 400", zahtjev("POST", f"/api/dio/{d}/prodaja", {"cijena": "abc", "razred_jamstva": "POTROSAC_12M", "javne_slike": [sid]})[0] == 400)
        ok("E9 nema atoma prije vrata", q("SELECT count(*) FROM izlaz_flota")[0][0] == 0)
        dio_slike = [x[0] for x in q("SELECT id FROM dio_slika WHERE otpad_dio_id=%s AND vrsta='DIO' ORDER BY id", d)]
        st, r, _ = zahtjev("POST", f"/api/dio/{d}/prodaja", {"cijena": "45,50", "razred_jamstva": "POTROSAC_12M", "javne_slike": dio_slike[:2]})
        ok("E9 potpun dio prolazi vrata", st == 201 and r["token"] == k["token"], str(r))
        ok("E9 drugi put → 409", zahtjev("POST", f"/api/dio/{d}/prodaja", {"cijena": "45", "razred_jamstva": "POTROSAC_12M", "javne_slike": dio_slike[:1]})[0] == 409)
        ok("E10 status NA_ZALIHI, cijena 45,50, jamstvo 12", q("SELECT status, cijena, jamstvo_mjeseci FROM otpad_dio WHERE id=%s", d) == [("NA_ZALIHI", 45.50, 12)] or str(q("SELECT status, cijena, jamstvo_mjeseci FROM otpad_dio WHERE id=%s", d)) .startswith("[('NA_ZALIHI', Decimal('45.50'), 12)"))
        ok("E10 točno jedan LANAC_SVJETLO i jedan OGLAS", q("SELECT count(*) FROM izlaz_flota WHERE cilj='LANAC_SVJETLO'")[0][0] == 1 and q("SELECT count(*) FROM izlaz_flota WHERE cilj='OGLAS'")[0][0] == 1)
        ok("E10 oglas nosi samo 2 odabrane slike", q("SELECT jsonb_array_length(podaci->'slike') FROM izlaz_flota WHERE cilj='OGLAS'")[0][0] == 2)
        ok("E10 atom svjetla nema sadržaj dnevnika ni slika", q("SELECT count(*) FROM izlaz_flota WHERE cilj='LANAC_SVJETLO' AND podaci ? 'merkle_koren' AND NOT podaci ? 'slike'")[0][0] == 1)

        # E11, E12
        st, r, _ = zahtjev("GET", "/api/nadji?q=r01-p1-02")
        ok("E11 nađi po adresi pretinca (mala slova)", st == 200 and r["vrsta"] == "pretinac" and [x["id"] for x in r["dijelovi"]] == [d], str(r)[:150])
        st, r, _ = zahtjev("GET", f"/api/nadji?q={r1['token']}")
        ok("E11 nađi po oznaki dijela", r["vrsta"] == "dio" and r["dio"]["id"] == d)
        st, r, _ = zahtjev("GET", "/api/nadji?q=0124525040")
        ok("E11 nađi po broju na dijelu", r["vrsta"] == "dijelovi" and any(x["id"] == d for x in r["dijelovi"]))
        ok("E11 ništa → vrsta nista", zahtjev("GET", "/api/nadji?q=ZZZZZZZZ")[1]["vrsta"] == "nista")
        ok("E11 prekratko → 400", zahtjev("GET", "/api/nadji?q=a")[0] == 400)
        st, r, _ = zahtjev("GET", "/api/tamni")
        ids = [x["id"] for x in r["dijelovi"]]
        ok("E12 popis u radu: nepoznat dio i duplikat su tu, prodani nije", n2 in ids and d not in ids, str(ids))

        # E13, E14
        with psycopg.connect(DSN, autocommit=True) as c:
            try:
                c.execute("DELETE FROM otpad_dio WHERE id=%s", (n2,)); obrisano = True
            except psycopg.Error:
                obrisano = False
            try:
                c.execute("UPDATE otpad_dio SET broj_na_dijelu='x' WHERE id=%s", (n2,)); mijenja = True
            except psycopg.Error:
                mijenja = False
        ok("E13 uloga ekrana ne smije DELETE", not obrisano)
        ok("E13 uloga ekrana ne smije mijenjati broj na dijelu", not mijenja)
        st, r, _ = zahtjev("POST", "/api/otpad-dijelovi", {"otpad_vozilo_id": auto, "naziv": "Far lijevi", "stanje": "B", "polica": "A-01", "cijena": "30"})
        ok("E14 stari brzi unos radi i nakon refaktora", st == 201 and r["naziv"] == "Far lijevi", str(r))
        ok("E14 stari unos bez naziva i dalje → 400", zahtjev("POST", "/api/otpad-dijelovi", {"otpad_vozilo_id": auto, "stanje": "B"})[0] == 400)
        ok("E14 pretraga radi", zahtjev("GET", "/api/trazi?q=ford")[0] == 200)

        # R1: stari testovi
        if brands and os.path.exists(brands):
            r = subprocess.run([sys.executable, "-I", os.path.join(AQ, "ekran", "test_ekran.py")], capture_output=True, text=True,
                               env={**os.environ, "OTPAD_URL": URL, "OTPAD_DSN": DSN})
            kraj = (r.stderr.strip().splitlines() or ["?"])[-1]
            ok("R1 postojeći test_ekran.py prolazi", r.returncode == 0, kraj + " | " + "\n".join(r.stderr.splitlines()[-12:]))
        else:
            print("NEPOZNATO R1 BRANDS_JS nije zadan: regresija starog ekrana preskočena")
    finally:
        for p in (s1, s2):
            p.send_signal(signal.SIGTERM)
        shutil.rmtree(slike_dir, ignore_errors=True)
        try:
            H.psql("postgres", f"DROP DATABASE IF EXISTS {DB}")
        except Exception as e:                                                   # noqa: BLE001
            print(f"upozorenje: čišćenje baze: {e}")
    print(f"\nUKUPNO {H.PASS + H.FAIL} · PROŠLO {H.PASS} · PALO {H.FAIL}")
    return 1 if H.FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
