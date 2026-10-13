#!/usr/bin/env python3
"""Ekran za radnicu: traženje dijela/auta i unos skinutog dijela.

Samo standardna biblioteka + psycopg 3. Sve SQL naredbe su parametrizirane.
Pokretanje (test):
    OTPAD_DSN="host=127.0.0.1 dbname=otpad_katalog_test user=otpad_app password=..." \
    OTPAD_PORT=8765 python3 server.py

VAŽNO: nema prijave. Sluša samo na 127.0.0.1. Prije bilo kakve prave upotrebe
treba dodati prijavu (Django login ili reverse proxy s autentikacijom).
"""
import json
import mimetypes
import os
import re
import sys
import traceback
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parent))      # i uz `python3 -I`, bez ovisnosti o radnom direktoriju
import spremnik as spremnik_modul
import tamno_api as TA
from greske import Greska

DSN = os.environ.get("OTPAD_DSN", "")
PORT = int(os.environ.get("OTPAD_PORT", "8765"))
STATIC = Path(__file__).resolve().parent / "static"
STATICKE_DATOTEKE = {"index.html", "app.css", "app.js", "tamno.js", "favicon.svg"}

GODINA_RE = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
STANJA = ("A", "B", "C", "D")

PORUKA_SERVER = ("Dogodila se greška na poslužitelju. Podaci nisu spremljeni. "
                 "Pokušaj ponovo; ako se ponavlja, javi Ivanu.")


def veza():
    return psycopg.connect(DSN, row_factory=dict_row, connect_timeout=5)


def veza_t():
    """Obična (tuple) konekcija za prodaja/tamno.py. `with` = commit na kraju, rollback na grešku."""
    return psycopg.connect(DSN, connect_timeout=5)


try:
    SPREMNIK = spremnik_modul.iz_okoline()
except ValueError as _e:                       # pogrešna postavka arhive: ne startati (inače bi svaka slika koštala AI obradu)
    print("POSTAVKA ARHIVE: " + str(_e), file=sys.stderr)
    sys.exit(2)


# ----------------------------------------------------------------- pretraga

def trazi(cur, q: str) -> dict:
    q = (q or "").strip()
    if len(q) < 2:
        raise Greska(400, "Upiši barem 2 znaka.")
    if len(q) > 80:
        raise Greska(400, "Upit je predug (najviše 80 znakova).")

    # 1) dijelovi po broju (razmaci i crtice nisu važni)
    cur.execute("SELECT * FROM trazi_broj(%s)", (q,))
    redovi = cur.fetchall()
    dijelovi: dict[int, dict] = {}
    for r in redovi:
        d = dijelovi.setdefault(r["dio_id"], {
            "dio_id": r["dio_id"], "naziv": r["naziv_hr"], "brojevi": [],
            "vozila": [], "na_zalihi": int(r["na_zalihi"]), "zaliha": [],
        })
        if r["broj"] not in [b["broj"] for b in d["brojevi"]]:
            d["brojevi"].append({"broj": r["broj"], "vrsta": r["vrsta"], "proizvodjac": r["proizvodjac"]})
        if r["marka"]:
            v = {"marka": r["marka"], "model": r["model"], "generacija": r["generacija"],
                 "od": r["godina_od"], "do": r["godina_do"]}
            if v not in d["vozila"]:
                d["vozila"].append(v)
    if dijelovi:
        cur.execute(
            "SELECT o.dio_id, o.polica, o.stanje, o.cijena, o.broj_na_dijelu "
            "FROM otpad_dio o WHERE o.dio_id = ANY(%s) AND o.status = 'NA_ZALIHI' "
            "ORDER BY o.id", (list(dijelovi),))
        for z in cur.fetchall():
            dijelovi[z["dio_id"]]["zaliha"].append({
                "polica": z["polica"], "stanje": z["stanje"],
                "cijena": str(z["cijena"]) if z["cijena"] is not None else None,
                "broj_na_dijelu": z["broj_na_dijelu"]})

    # 2) vozila: izdvoji godinu ako je upisana, ostatak su riječi
    m = GODINA_RE.search(q)
    godina = int(m.group(1)) if m else None
    riječi = GODINA_RE.sub(" ", q).strip()
    vozila = []
    if riječi:
        cur.execute("SELECT * FROM trazi_vozilo(%s, %s) LIMIT 41", (riječi, godina))
        vozila = [{"id": r["id"], "marka": r["marka"], "model": r["model"],
                   "generacija": r["generacija"], "od": r["godina_od"], "do": r["godina_do"]}
                  for r in cur.fetchall()]
    return {"upit": q, "godina": godina,
            "dijelovi": list(dijelovi.values()),
            "vozila": vozila[:40], "vozila_ima_jos": len(vozila) > 40}


def lista_otpad_vozila(cur) -> list:
    cur.execute(
        "SELECT ov.id, ov.vin, ov.km, ov.datum_dolaska, v.marka, v.model, v.generacija, "
        "       v.godina_od, v.godina_do "
        "FROM otpad_vozilo ov LEFT JOIN vozilo_tip v ON v.id = ov.vozilo_tip_id "
        "ORDER BY ov.id DESC LIMIT 200")
    return [{"id": r["id"], "vin": r["vin"], "km": r["km"],
             "datum": r["datum_dolaska"].isoformat() if r["datum_dolaska"] else None,
             "marka": r["marka"], "model": r["model"], "generacija": r["generacija"],
             "od": r["godina_od"], "do": r["godina_do"]} for r in cur.fetchall()]


def nazivi_dijelova(cur) -> list:
    cur.execute("SELECT DISTINCT naziv_hr FROM dio ORDER BY naziv_hr LIMIT 300")
    return [r["naziv_hr"] for r in cur.fetchall()]


def zadnji_uneseni(cur) -> list:
    cur.execute(
        "SELECT o.id, d.naziv_hr, o.broj_na_dijelu, o.polica, o.stanje, o.cijena, o.status, "
        "       v.marka, v.model, v.generacija "
        "FROM otpad_dio o JOIN dio d ON d.id = o.dio_id "
        "LEFT JOIN otpad_vozilo ov ON ov.id = o.otpad_vozilo_id "
        "LEFT JOIN vozilo_tip v ON v.id = ov.vozilo_tip_id "
        "ORDER BY o.id DESC LIMIT 10")
    return [{"id": r["id"], "naziv": r["naziv_hr"], "broj": r["broj_na_dijelu"],
             "polica": r["polica"], "stanje": r["stanje"],
             "cijena": str(r["cijena"]) if r["cijena"] is not None else None,
             "status": r["status"],
             "auto": " ".join(x for x in (r["marka"], r["model"], r["generacija"]) if x)}
            for r in cur.fetchall()]


# --------------------------------------------------------------------- unos

def _cijena(v):
    if v is None or str(v).strip() == "":
        return None
    try:
        c = Decimal(str(v).strip().replace(",", ".").replace("€", "").strip())
    except InvalidOperation:
        raise Greska(400, "Cijena nije ispravan broj. Upiši npr. 45 ili 45,50.")
    if c < 0 or c > 1_000_000:
        raise Greska(400, "Cijena mora biti između 0 i 1.000.000.")
    return c.quantize(Decimal("0.01"))


def novo_otpad_vozilo(cur, p: dict) -> dict:
    try:
        tip_id = int(p.get("vozilo_tip_id"))
    except (TypeError, ValueError):
        raise Greska(400, "Odaberi vrstu auta s popisa (upiši npr. Focus 2013 i klikni na točan red).")
    cur.execute("SELECT 1 FROM vozilo_tip WHERE id = %s", (tip_id,))
    if not cur.fetchone():
        raise Greska(400, "Odabrana vrsta auta ne postoji. Pretraži ponovo.")
    vin = (p.get("vin") or "").strip().upper() or None
    if vin and not VIN_RE.match(vin):
        raise Greska(400, "VIN mora imati točno 17 znakova (slova i brojke, bez I, O i Q). "
                          "Ostavi prazno ako ga nemaš.")
    km = p.get("km")
    if km in (None, ""):
        km = None
    else:
        try:
            km = int(str(km).replace(".", "").replace(" ", ""))
        except ValueError:
            raise Greska(400, "Kilometri moraju biti broj.")
        if km < 0 or km > 5_000_000:
            raise Greska(400, "Kilometri nisu vjerojatni. Provjeri upis.")
    if vin:
        cur.execute("SELECT id FROM otpad_vozilo WHERE vin = %s", (vin,))
        if cur.fetchone():
            raise Greska(409, "Auto s tim VIN-om već je na popisu. Odaberi ga s popisa.")
    cur.execute("INSERT INTO otpad_vozilo (vin, vozilo_tip_id, km, datum_dolaska) "
                "VALUES (%s, %s, %s, CURRENT_DATE) RETURNING id", (vin, tip_id, km))
    return {"id": cur.fetchone()["id"], "poruka": "Auto je dodan na popis."}


def _katalog_dio(cur, p: dict, auto: dict, broj: str, *, nepoznat_ok: bool = False):
    """Zajednički dio unosa dijela: provjera duplikata, dio (poznat/novi), dio_broj, dio_vozilo.
    -> (dio_id | None, broj_norm | None). dio_id je None samo kad je nepoznat_ok i naziv nije upisan."""
    auto_id = auto["id"]
    cur.execute("SELECT norm_broj(%s) AS n", (broj,))
    broj_norm = cur.fetchone()["n"]
    if broj and not broj_norm:
        raise Greska(400, "Broj dijela mora sadržavati slova ili brojke.")

    if broj_norm and not p.get("dopusti_duplikat"):
        cur.execute("SELECT id FROM otpad_dio WHERE otpad_vozilo_id = %s AND broj_norm = %s "
                    "AND status <> 'PRODAN'", (auto_id, broj_norm))
        if cur.fetchone():
            raise Greska(409, "Dio s tim brojem već je unesen za ovaj auto. "
                              "Ako je to drugi isti dio (npr. dva amortizera), potvrdi unos.",
                         duplikat=True)

    # koji je to dio: poznat po broju, odabran, ili novi
    dio_id = None
    if p.get("dio_id") not in (None, ""):
        try:
            dio_id = int(p["dio_id"])
        except (TypeError, ValueError):
            raise Greska(400, "Neispravan dio. Osvježi stranicu.")
        cur.execute("SELECT 1 FROM dio WHERE id = %s", (dio_id,))
        if not cur.fetchone():
            raise Greska(400, "Taj dio ne postoji u bazi. Osvježi stranicu.")
    else:
        naziv = (p.get("naziv") or "").strip()
        if not naziv and nepoznat_ok:
            return None, (broj_norm or None)
        if len(naziv) < 2:
            raise Greska(400, "Upiši naziv dijela (npr. Alternator, Far lijevi).")
        if len(naziv) > 120:
            raise Greska(400, "Naziv dijela je predug (najviše 120 znakova).")
        cur.execute("INSERT INTO dio (naziv_hr) VALUES (%s) RETURNING id", (naziv,))
        dio_id = cur.fetchone()["id"]

    cur.execute("SELECT id FROM izvor WHERE naziv = 'Unos radnice'")
    izvor = cur.fetchone()
    izvor_id = izvor["id"] if izvor else None

    if broj_norm:
        cur.execute("INSERT INTO dio_broj (dio_id, broj, broj_norm, vrsta, izvor_id) "
                    "VALUES (%s, %s, %s, 'KATALOSKI', %s) ON CONFLICT DO NOTHING",
                    (dio_id, broj, broj_norm, izvor_id))
    if auto["vozilo_tip_id"]:
        cur.execute("INSERT INTO dio_vozilo (dio_id, vozilo_tip_id, izvor_id) VALUES (%s, %s, %s) "
                    "ON CONFLICT DO NOTHING", (dio_id, auto["vozilo_tip_id"], izvor_id))
    return dio_id, (broj_norm or None)


def novi_otpad_dio(cur, p: dict) -> dict:
    try:
        auto_id = int(p.get("otpad_vozilo_id"))
    except (TypeError, ValueError):
        raise Greska(400, "Prvo odaberi auto s kojeg je dio skinut.")
    cur.execute("SELECT id, vozilo_tip_id FROM otpad_vozilo WHERE id = %s", (auto_id,))
    auto = cur.fetchone()
    if not auto:
        raise Greska(400, "Taj auto ne postoji na popisu. Osvježi stranicu.")

    broj = (p.get("broj_na_dijelu") or "").strip()[:80]
    stanje = (p.get("stanje") or "").strip().upper()
    if stanje not in STANJA:
        raise Greska(400, "Odaberi stanje dijela: A, B, C ili D.")
    cijena = _cijena(p.get("cijena"))
    polica = (p.get("polica") or "").strip()[:40] or None

    dio_id, broj_norm = _katalog_dio(cur, p, auto, broj)
    cur.execute("INSERT INTO otpad_dio (dio_id, otpad_vozilo_id, broj_na_dijelu, polica, stanje, cijena) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (dio_id, auto_id, broj or None, polica, stanje, cijena))
    novi = cur.fetchone()["id"]
    cur.execute("SELECT naziv_hr FROM dio WHERE id = %s", (dio_id,))
    return {"id": novi, "dio_id": dio_id, "naziv": cur.fetchone()["naziv_hr"],
            "broj_norm": broj_norm or None,
            "poruka": "Dio je spremljen."}


def rodi_katalog(cur, p: dict) -> dict:
    """Korak 1 rođenja dijela (dict kursor): auto + katalog. Korak 2 je tamno.rodi (tuple konekcija).
    Nepoznat dio je dopušten: dio se svejedno rađa, tip se može dopuniti kasnije."""
    try:
        auto_id = int(p.get("otpad_vozilo_id"))
    except (TypeError, ValueError):
        raise Greska(400, "Prvo odaberi auto s kojeg je dio skinut.")
    cur.execute("SELECT id, vozilo_tip_id FROM otpad_vozilo WHERE id = %s", (auto_id,))
    auto = cur.fetchone()
    if not auto:
        raise Greska(400, "Taj auto ne postoji na popisu. Osvježi stranicu.")
    broj = (p.get("broj_na_dijelu") or "").strip()[:80]
    dio_id, _ = _katalog_dio(cur, p, auto, broj, nepoznat_ok=True)
    return {"auto": auto_id, "broj": broj or None, "dio_id": dio_id,
            "prepoznavanje": "NEPOZNATO" if dio_id is None else "RUCNO"}


# ----------------------------------------------------------------- poslužitelj

class Handler(BaseHTTPRequestHandler):
    server_version = "OtpadEkran/0.1"

    def log_message(self, fmt, *args):  # tiši zapisnik, bez upita (mogu sadržavati brojeve)
        sys.stderr.write("%s %s\n" % (self.command, urlparse(self.path).path))

    # -- pomoćne
    def _json(self, status: int, obj: dict):
        tijelo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(tijelo)))
        self.send_header("Cache-Control", "no-store")
        self._sigurnosna_zaglavlja()
        self.end_headers()
        self.wfile.write(tijelo)

    def _bajtovi(self, tijelo: bytes, tip: str):
        self.send_response(200)
        self.send_header("Content-Type", tip)
        self.send_header("Content-Length", str(len(tijelo)))
        self.send_header("Cache-Control", "private, no-store")
        self._sigurnosna_zaglavlja()
        self.end_headers()
        self.wfile.write(tijelo)

    def _sigurnosna_zaglavlja(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")

    def _statika(self, ime: str):
        if ime not in STATICKE_DATOTEKE:
            return self._json(404, {"greska": "Stranica ne postoji."})
        put = STATIC / ime
        tijelo = put.read_bytes()
        tip = mimetypes.guess_type(ime)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{tip}; charset=utf-8")
        self.send_header("Content-Length", str(len(tijelo)))
        self.send_header("Cache-Control", "no-cache")
        self._sigurnosna_zaglavlja()
        self.end_headers()
        self.wfile.write(tijelo)

    def _provjeri_post(self, sirovo: bool = False):
        if self.headers.get("X-Requested-With") != "otpad":
            raise Greska(403, "Zahtjev odbijen. Osvježi stranicu pa pokušaj ponovo.")
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            raise Greska(403, "Zahtjev odbijen (nepoznato podrijetlo).")
        if not sirovo and "application/json" not in (self.headers.get("Content-Type") or ""):
            raise Greska(415, "Neispravan zahtjev.")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > (TA.MAX_SLIKA if sirovo else 20_000):
            raise Greska(400 if n <= 0 else 413, "Neispravan zahtjev." if n <= 0 else "Datoteka je prevelika (najviše 15 MB).")
        if sirovo:
            return self.rfile.read(n)
        try:
            p = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise Greska(400, "Neispravan zahtjev.")
        if not isinstance(p, dict):
            raise Greska(400, "Neispravan zahtjev.")
        return p

    # -- usmjeravanje
    def do_GET(self):
        try:
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                return self._statika("index.html")
            if u.path in ("/app.css", "/app.js", "/tamno.js", "/favicon.svg"):
                return self._statika(u.path[1:])
            if u.path == "/favicon.ico":          # preglednik ga uvijek traži; bez 404 u konzoli
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self._sigurnosna_zaglavlja()
                self.end_headers()
                return
            if not u.path.startswith("/api/"):
                return self._json(404, {"greska": "Stranica ne postoji."})
            qs = parse_qs(u.query)
            with veza() as con, con.cursor() as cur:
                if u.path == "/api/trazi":
                    return self._json(200, trazi(cur, (qs.get("q") or [""])[0]))
                if u.path == "/api/otpad-vozila":
                    return self._json(200, {"vozila": lista_otpad_vozila(cur)})
                if u.path == "/api/nazivi":
                    return self._json(200, {"nazivi": nazivi_dijelova(cur)})
                if u.path == "/api/zadnji":
                    return self._json(200, {"dijelovi": zadnji_uneseni(cur)})
            with veza_t() as ct:
                if u.path == "/api/pretinci":
                    return self._json(200, TA.pretinci_popis(ct))
                if u.path == "/api/tamni":
                    return self._json(200, TA.tamni_popis(ct))
                if u.path == "/api/nadji":
                    return self._json(200, TA.nadji(ct, (qs.get("q") or [""])[0]))
                m = re.fullmatch(r"/api/pretinac/([A-Za-z0-9-]{1,12})", u.path)
                if m:
                    return self._json(200, TA.pretinac_sadrzaj(ct, m[1].upper()))
                m = re.fullmatch(r"/api/dio/(\d{1,9})", u.path)
                if m:
                    return self._json(200, TA.dio_kartica(ct, int(m[1])))
                m = re.fullmatch(r"/api/slika/(\d{1,9})", u.path)
                if m:
                    b, tip = TA.slika_citaj(ct, int(m[1]), SPREMNIK)
                    return self._bajtovi(b, tip)
            return self._json(404, {"greska": "Nepoznata adresa."})
        except Greska as g:
            self._json(g.status, {"greska": g.poruka, **g.extra})
        except Exception:
            traceback.print_exc()
            self._json(500, {"greska": PORUKA_SERVER})

    def do_POST(self):
        try:
            u = urlparse(self.path)
            m_slika = re.fullmatch(r"/api/dio/(\d{1,9})/slika", u.path)
            p = self._provjeri_post(sirovo=bool(m_slika))
            rezultat = None
            if m_slika:
                with veza_t() as ct:
                    rezultat = TA.slika_spremi(ct, int(m_slika[1]), self.headers.get("X-Vrsta", ""), p, SPREMNIK)
                return self._json(201, rezultat)
            m = re.fullmatch(r"/api/dio/(\d{1,9})/(predradnja|spremi|prodaja)", u.path)
            if m:
                f = {"predradnja": TA.predradnja, "spremi": TA.spremi_u_pretinac, "prodaja": TA.u_prodaju}[m[2]]
                with veza_t() as ct:
                    rezultat = f(ct, int(m[1]), p)
                return self._json(201, rezultat)
            if u.path == "/api/pretinci":
                with veza_t() as ct:
                    rezultat = TA.pretinci_stvori(ct, p)
                return self._json(201, rezultat)
            if u.path == "/api/dio/rodi":
                with veza() as con:
                    with con.transaction(), con.cursor() as cur:
                        k = rodi_katalog(cur, p)
                with veza_t() as ct:
                    r = TA._uvijek(TA.T.rodi, ct, k["auto"], broj_na_dijelu=k["broj"], dio_id_tip=k["dio_id"],
                                   prepoznavanje=k["prepoznavanje"])
                return self._json(201, {"id": r["id"], "token": r["token"], "poruka": "Dio je rođen. Sad ga slikaj."})
            with veza() as con:
                with con.transaction(), con.cursor() as cur:
                    if u.path == "/api/otpad-vozila":
                        rezultat = novo_otpad_vozilo(cur, p)
                    elif u.path == "/api/otpad-dijelovi":
                        rezultat = novi_otpad_dio(cur, p)
            # odgovor se šalje TEK nakon uspješnog commita transakcije
            if rezultat is None:
                return self._json(404, {"greska": "Nepoznata adresa."})
            return self._json(201, rezultat)
        except Greska as g:
            self._json(g.status, {"greska": g.poruka, **g.extra})
        except Exception:
            traceback.print_exc()
            self._json(500, {"greska": PORUKA_SERVER})


def main():
    if not DSN:
        print("Postavi OTPAD_DSN (npr. \"host=127.0.0.1 dbname=... user=otpad_app password=...\").")
        sys.exit(2)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Ekran radi na http://127.0.0.1:{PORT}/ (bez prijave, samo lokalno)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
