#!/usr/bin/env python3
"""Testovi ekrana (poslužitelj + baza). Traži POKRENUT server i test bazu.

    OTPAD_URL=http://127.0.0.1:8765 OTPAD_DSN="host=... dbname=otpad_katalog_test user=otpad_app password=..." \
    python3 test_ekran.py

Ne pokretati prema produkcijskoj bazi: testovi upisuju podatke (s jedinstvenim brojevima TESTRUN...).
"""
import json
import os
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid

import psycopg

URL = os.environ.get("OTPAD_URL", "http://127.0.0.1:8765")
DSN = os.environ["OTPAD_DSN"]
RUN = uuid.uuid4().hex[:8].upper()


def zahtjev(metoda, put, tijelo=None, zaglavlja=None):
    z = {} if zaglavlja is None else dict(zaglavlja)
    data = None
    if tijelo is not None:
        data = json.dumps(tijelo).encode()
        z.setdefault("Content-Type", "application/json")
        z.setdefault("X-Requested-With", "otpad")
    r = urllib.request.Request(URL + put, data=data, method=metoda, headers=z)
    try:
        with urllib.request.urlopen(r, timeout=15) as o:
            return o.status, json.loads(o.read() or b"{}"), dict(o.headers)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw), dict(e.headers)
        except ValueError:
            return e.code, {"raw": raw.decode(errors="replace")}, dict(e.headers)


def q(sql, *args):
    with psycopg.connect(DSN) as c, c.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else None


def tip_id(model, generacija):
    return q("SELECT id FROM vozilo_tip WHERE marka='Ford' AND model=%s AND generacija=%s", model, generacija)[0][0]


class Statika(unittest.TestCase):
    def test_stranica_i_zaglavlja(self):
        with urllib.request.urlopen(URL + "/") as o:
            h = {k.lower(): v for k, v in o.headers.items()}
            html = o.read().decode()
        self.assertEqual(o.status, 200)
        self.assertIn("default-src 'self'", h["content-security-policy"])
        self.assertEqual(h["x-content-type-options"], "nosniff")
        self.assertIn('lang="hr"', html)

    def test_nepoznata_adresa_je_404_s_porukom(self):
        s, d, _ = zahtjev("GET", "/nema-me")
        self.assertEqual(s, 404)
        self.assertIn("greska", d)

    def test_nije_moguce_citati_proizvoljne_datoteke(self):
        s, _, _ = zahtjev("GET", "/..%2fserver.py")
        self.assertEqual(s, 404)
        s, _, _ = zahtjev("GET", "/../../etc/passwd")
        self.assertEqual(s, 404)


class Trazi(unittest.TestCase):
    def test_vozilo_i_godina(self):
        s, d, _ = zahtjev("GET", "/api/trazi?q=" + urllib.parse.quote("focus 2013"))
        self.assertEqual(s, 200)
        self.assertEqual(d["godina"], 2013)
        self.assertEqual(d["vozila"][0]["model"], "Focus")
        self.assertEqual(d["vozila"][0]["generacija"], "Mk III")

    def test_broj_u_tri_oblika(self):
        ids = set()
        for upit in ("TST 100 001 A", "tst-100-001-a", "TST100001A"):
            s, d, _ = zahtjev("GET", "/api/trazi?q=" + urllib.parse.quote(upit))
            self.assertEqual(s, 200)
            self.assertEqual(len(d["dijelovi"]), 1, upit)
            ids.add(d["dijelovi"][0]["dio_id"])
        self.assertEqual(len(ids), 1)

    def test_prekratak_i_predug_upit(self):
        s, d, _ = zahtjev("GET", "/api/trazi?q=a")
        self.assertEqual(s, 400)
        self.assertIn("2 znaka", d["greska"])
        s, d, _ = zahtjev("GET", "/api/trazi?q=" + "x" * 81)
        self.assertEqual(s, 400)

    def test_nista_nadjeno(self):
        s, d, _ = zahtjev("GET", "/api/trazi?q=NEPOSTOJI9999ZZ")
        self.assertEqual(s, 200)
        self.assertEqual((d["dijelovi"], d["vozila"]), ([], []))

    def test_sql_injection_u_upitu_je_samo_tekst(self):
        s, d, _ = zahtjev("GET", "/api/trazi?q=" + urllib.parse.quote("'; DROP TABLE dio; --"))
        self.assertEqual(s, 200)
        self.assertGreater(q("SELECT count(*) FROM dio")[0][0], 0)


class Zastita(unittest.TestCase):
    def test_post_bez_zaglavlja_403(self):
        r = urllib.request.Request(URL + "/api/otpad-dijelovi", data=b"{}", method="POST",
                                   headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(r)
        self.assertEqual(e.exception.code, 403)

    def test_post_s_tudjim_originom_403(self):
        s, d, _ = zahtjev("POST", "/api/otpad-dijelovi", {}, {"Origin": "http://zlocinac.example"})
        self.assertEqual(s, 403)

    def test_post_krivi_content_type_415(self):
        s, d, _ = zahtjev("POST", "/api/otpad-dijelovi", {}, {"Content-Type": "text/plain"})
        self.assertEqual(s, 415)

    def test_uloga_aplikacije_nema_pravo_brisati_ni_mijenjati_strukturu(self):
        for sql in ("DELETE FROM dio", "DROP TABLE dio", "UPDATE vozilo_tip SET marka='X'",
                    "INSERT INTO vozilo_tip (marka,model,generacija,godina_od) VALUES ('a','b','c',2000)"):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege, msg=sql):
                q(sql)


class UnosAuta(unittest.TestCase):
    def test_ispravan_auto_i_zastite(self):
        tip = tip_id("Focus", "Mk III")
        vin = ("WF0" + RUN + "00000000000000")[:17]   # RUN je hex (bez I, O, Q)
        s, d, _ = zahtjev("POST", "/api/otpad-vozila", {"vozilo_tip_id": tip, "vin": vin.lower(), "km": "187.000"})
        self.assertEqual(s, 201, d)
        self.assertEqual(q("SELECT vin, km FROM otpad_vozilo WHERE id=%s", d["id"]), [(vin, 187000)])
        # isti VIN ponovo
        s, d, _ = zahtjev("POST", "/api/otpad-vozila", {"vozilo_tip_id": tip, "vin": vin})
        self.assertEqual(s, 409)
        self.assertIn("VIN", d["greska"])

    def test_neispravni_podaci(self):
        tip = tip_id("Focus", "Mk III")
        for tijelo, dio_poruke in [
            ({"vozilo_tip_id": None}, "Odaberi vrstu auta"),
            ({"vozilo_tip_id": 99999999}, "ne postoji"),
            ({"vozilo_tip_id": tip, "vin": "KRATAK"}, "17 znakova"),
            ({"vozilo_tip_id": tip, "vin": "WF0IOQ00000000001"}, "17 znakova"),
            ({"vozilo_tip_id": tip, "km": "abc"}, "Kilometri"),
            ({"vozilo_tip_id": tip, "km": "-5"}, "Kilometri"),
        ]:
            s, d, _ = zahtjev("POST", "/api/otpad-vozila", tijelo)
            self.assertEqual(s, 400, tijelo)
            self.assertIn(dio_poruke, d["greska"], tijelo)


class UnosDijela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tip = tip_id("Focus", "Mk III")
        s, d, _ = zahtjev("POST", "/api/otpad-vozila", {"vozilo_tip_id": cls.tip})
        assert s == 201, d
        cls.auto = d["id"]

    def dio(self, **kw):
        t = {"otpad_vozilo_id": self.auto, "naziv": "Probni dio", "stanje": "b", "broj_na_dijelu": ""}
        t.update(kw)
        return zahtjev("POST", "/api/otpad-dijelovi", t)

    def test_novi_dio_postaje_pretraziv_i_povezan_s_autom(self):
        broj = f"TESTRUN {RUN} 77 A"
        s, d, _ = self.dio(naziv="Alternator probni", broj_na_dijelu=broj.lower(), polica="Z-9-9", cijena="45,5", stanje="B")
        self.assertEqual(s, 201, d)
        self.assertEqual(d["broj_norm"], f"TESTRUN{RUN}77A")
        s, r, _ = zahtjev("GET", "/api/trazi?q=" + urllib.parse.quote(broj))
        self.assertEqual(len(r["dijelovi"]), 1)
        dio = r["dijelovi"][0]
        self.assertEqual(dio["naziv"], "Alternator probni")
        self.assertEqual(dio["na_zalihi"], 1)
        self.assertEqual(dio["zaliha"][0]["polica"], "Z-9-9")
        self.assertEqual(dio["zaliha"][0]["cijena"], "45.50")
        self.assertEqual((dio["vozila"][0]["model"], dio["vozila"][0]["generacija"]), ("Focus", "Mk III"))

    def test_poznati_broj_koristi_postojeci_dio(self):
        prije = q("SELECT count(*) FROM dio")[0][0]
        s, r, _ = zahtjev("GET", "/api/trazi?q=TST100002A")
        dio_id = r["dijelovi"][0]["dio_id"]
        s, d, _ = self.dio(dio_id=dio_id, broj_na_dijelu="TST-100-002-A", stanje="A")
        self.assertEqual(s, 201, d)
        self.assertEqual(d["dio_id"], dio_id)
        self.assertEqual(q("SELECT count(*) FROM dio")[0][0], prije)

    def test_duplikat_traži_potvrdu_i_ne_stvara_dio(self):
        broj = f"TESTRUN{RUN}DUP"
        self.assertEqual(self.dio(naziv="Duplikat test", broj_na_dijelu=broj)[0], 201)
        prije = q("SELECT count(*) FROM dio")[0][0]
        s, d, _ = self.dio(naziv="Duplikat test", broj_na_dijelu=broj.lower())
        self.assertEqual(s, 409)
        self.assertTrue(d["duplikat"])
        self.assertEqual(q("SELECT count(*) FROM dio")[0][0], prije)  # ništa nije upisano
        s, d, _ = self.dio(naziv="Duplikat test", broj_na_dijelu=broj, dopusti_duplikat=True)
        self.assertEqual(s, 201, d)
        self.assertEqual(q("SELECT count(*) FROM otpad_dio WHERE broj_norm=%s", broj)[0][0], 2)

    def test_greske_su_citljive_i_nista_se_ne_upisuje(self):
        prije = q("SELECT (SELECT count(*) FROM dio), (SELECT count(*) FROM otpad_dio)")[0]
        slucajevi = [
            (dict(otpad_vozilo_id=None), "odaberi auto"),
            (dict(otpad_vozilo_id=99999999), "ne postoji"),
            (dict(stanje=""), "stanje"),
            (dict(stanje="X"), "stanje"),
            (dict(naziv=""), "naziv"),
            (dict(naziv="x" * 121), "predug"),
            (dict(cijena="abc"), "Cijena"),
            (dict(cijena="-3"), "Cijena"),
            (dict(broj_na_dijelu="---"), "slova ili brojke"),
            (dict(dio_id=99999999), "ne postoji"),
        ]
        for kw, dio_poruke in slucajevi:
            s, d, _ = self.dio(**kw)
            self.assertEqual(s, 400, kw)
            self.assertIn(dio_poruke.lower(), d["greska"].lower(), kw)
        self.assertEqual(q("SELECT (SELECT count(*) FROM dio), (SELECT count(*) FROM otpad_dio)")[0], prije)

    def test_posebni_znakovi_se_spremaju_kao_tekst(self):
        zlo = "<img src=x onerror=alert(1)>'; DROP TABLE dio;--"
        s, d, _ = self.dio(naziv=zlo[:120], polica="<b>x</b>")
        self.assertEqual(s, 201, d)
        self.assertEqual(q("SELECT naziv_hr FROM dio WHERE id=%s", d["dio_id"])[0][0], zlo[:120])
        self.assertGreater(q("SELECT count(*) FROM dio")[0][0], 0)

    def test_zadnji_uneseni_i_nazivi(self):
        s, d, _ = zahtjev("GET", "/api/zadnji")
        self.assertEqual(s, 200)
        self.assertLessEqual(len(d["dijelovi"]), 10)
        s, d, _ = zahtjev("GET", "/api/nazivi")
        self.assertIn("Alternator", d["nazivi"])
        s, d, _ = zahtjev("GET", "/api/otpad-vozila")
        self.assertEqual(s, 200)
        self.assertTrue(any(v["id"] == self.auto for v in d["vozila"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
