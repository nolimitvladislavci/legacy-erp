#!/usr/bin/env python3
"""Test spajanja slika s poslovnom arhivom: adapter, zaštita od troška, ekran + LAŽNA arhiva (ugovor pročitan iz koda, ne stvarna arhiva).

Kriteriji (upisani prije pokretanja):
  A1 tvornica odbija arhivu bez ARHIVA_BEZ_AI_POTVRDENO=1, server se ne pokreće · A2 upload: ref arhiva:<64 hex>, sha256 sadržaja,
  app_id kelava-dijelovi, Bearer, ime dio-<sha>.jpg · A3 isti sadržaj = isti ref (idempotentno) · A4 readback ne štima → greška, ništa u bazi
  A5 401, 500 i nedostupna arhiva → čitljiva poruka, ništa u bazi · A6 dohvat bajt-identičan, nevaljan ref → None
  E1 ekran: slika ide u arhivu (dio_slika.ref arhiva:…, nijedna lokalna), dohvat preko ekrana je bajt-identičan
  E2 arhiva pala → 502 s porukom, dio_slika bez novog retka · E3 stare lokalne slike ostaju čitljive uz arhivu
  E4 AI obrada nije pokrenuta (ai_pokrenuto = 0) za app_id kelava-dijelovi · E5 bez zaštite (kontrola): tuđi app_id pokreće AI (dokazuje da brojač radi)
  Z1 zakrpa: suho ne piše, primjena mijenja točno dva mjesta, py_compile prolazi, druga primjena je bezopasna, krivo sidro → STOP bez izmjene
Pokretanje:  BRANDS_JS=<brands.js> python3 -I test_arhiva_spoj.py
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psycopg  # noqa: E402

import test_tamno_ekran as TE  # noqa: E402
from arhiva_spremnik import ArhivaSpremnik, SpremnikGreska  # noqa: E402
from lazna_arhiva import LaznaArhiva  # noqa: E402

H = TE.H
ok = H.ok
AQ = TE.AQ
TOKEN = "TESTSESIJA-" + hashlib.sha256(b"otpad").hexdigest()[:8]


def main() -> int:
    # ---------- adapter bez servera i baze ----------
    arh = LaznaArhiva(TOKEN).start()
    try:
        sp = ArhivaSpremnik(arh.url, TOKEN, bez_ai_potvrdeno=True)
        j = TE.jpeg(11)
        sha, ref = sp.spremi(j)
        ok("A2 upload: sha256 sadržaja i ref arhiva:<64 hex>", sha == hashlib.sha256(j).hexdigest() and len(ref) == 7 + 64 and ref.startswith("arhiva:"), ref)
        z = arh.zahtjevi[-1]
        ok("A2 app_id kelava-dijelovi, ime dio-<sha>.jpg", z["app_id"] == "kelava-dijelovi" and z["ime"] == f"dio-{sha[:12]}.jpg", str(z))
        ok("A3 isti sadržaj daje isti ref", sp.spremi(j)[1] == ref and len(arh.dokumenti) == 1)
        ok("A6 dohvat je bajt-identičan", sp.dohvati(ref) == j)
        ok("A6 nevaljan ref → None, nepoznat → None", sp.dohvati("lokalno:" + "0" * 64) is None and sp.dohvati("arhiva:" + "0" * 64) is None)
        ok("A1 bez potvrde bez AI-a konstruktor baca", _baca(lambda: ArhivaSpremnik(arh.url, TOKEN, bez_ai_potvrdeno=False)))
        ok("A1 prazan token baca", _baca(lambda: ArhivaSpremnik(arh.url, "", bez_ai_potvrdeno=True)))
        arh.kvar = "krivi_original"
        g = _poruka(lambda: sp.spremi(TE.jpeg(12)))
        ok("A4 readback ne štima → greška 'Provjera nakon spremanja'", g is not None and "Provjera nakon spremanja" in g, str(g))
        arh.kvar = "401"
        g = _poruka(lambda: sp.spremi(TE.jpeg(13)))
        ok("A5 401 → čitljiva poruka o prijavi", g is not None and "Prijava u arhivu" in g, str(g))
        arh.kvar = "500"
        g = _poruka(lambda: sp.spremi(TE.jpeg(14)))
        ok("A5 500 → čitljiva poruka, slika nije spremljena", g is not None and "nije spremljena" in g, str(g))
        arh.kvar = None
        mrtva = ArhivaSpremnik("http://127.0.0.1:1", TOKEN, bez_ai_potvrdeno=True, rok=2)
        g = _poruka(lambda: mrtva.spremi(TE.jpeg(15)))
        ok("A5 nedostupna arhiva → 'nije dostupna'", g is not None and "nije dostupna" in g, str(g))
        ok("E5 kontrola: tuđi app_id bi pokrenuo AI (brojač radi)", _kontrola_ai(arh))
    finally:
        arh.stop()

    # ---------- ekran ----------
    brands = os.environ.get("BRANDS_JS", "")
    try:
        TE.postavi_bazu(brands)
    except Exception as e:                                                       # noqa: BLE001
        print(f"PRIPREMA PALA: {e}"); return 2
    arh = LaznaArhiva(TOKEN).start()
    lokalno = tempfile.mkdtemp(prefix="otpad_slike_"); os.chmod(lokalno, 0o700)
    # A1: server se ne smije pokrenuti bez potvrde
    env = {**os.environ, "OTPAD_DSN": TE.DSN, "OTPAD_PORT": "8795", "ARHIVA_URL": arh.url, "ARHIVA_TOKEN": TOKEN}
    env.pop("ARHIVA_BEZ_AI_POTVRDENO", None)
    r = subprocess.run([sys.executable, "-I", os.path.join(AQ, "ekran", "server.py")], env=env, capture_output=True, text=True, timeout=20)
    ok("A1 server bez ARHIVA_BEZ_AI_POTVRDENO ne starta (exit 2, jasna poruka)", r.returncode == 2 and "POSTAVKA ARHIVE" in r.stderr, f"{r.returncode} {r.stderr[:200]}")

    # prije arhive: jedna lokalna slika (prijelazno razdoblje)
    srv0 = TE.pokreni(TE.PORT, lokalno)
    try:
        auto = TE.q("SELECT id FROM otpad_vozilo ORDER BY id LIMIT 1")[0][0]
        d = TE.zahtjev("POST", "/api/dio/rodi", {"otpad_vozilo_id": auto, "naziv": "Alternator"})[1]["id"]
        lok = TE.jpeg(21)
        st, r, _ = TE.zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "DIO", "Content-Type": "image/jpeg"}, sirovo=lok)
        lok_id = r["slika"]
    finally:
        srv0.terminate()

    srv = TE.pokreni(TE.PORT, lokalno, {"ARHIVA_URL": arh.url, "ARHIVA_TOKEN": TOKEN, "ARHIVA_BEZ_AI_POTVRDENO": "1"})
    try:
        slike = [TE.jpeg(k) for k in (31, 32, 33)]
        for k, b in enumerate(slike):
            st, r, _ = TE.zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "DIO", "Content-Type": "image/jpeg"}, sirovo=b)
            ok(f"E1 slika {k + 1}/3 ide u arhivu (201)", st == 201, f"{st} {r}")
        refovi = [x[0] for x in TE.q("SELECT ref FROM dio_slika WHERE otpad_dio_id=%s ORDER BY id", d)]
        ok("E1 nove slike imaju ref arhiva:…, stara ostaje lokalno:…", refovi[0].startswith("lokalno:") and all(x.startswith("arhiva:") for x in refovi[1:]), str(refovi))
        sid = TE.q("SELECT id FROM dio_slika WHERE otpad_dio_id=%s AND ref LIKE 'arhiva:%%' ORDER BY id LIMIT 1", d)[0][0]
        st, b, h = TE.zahtjev("GET", f"/api/slika/{sid}")
        ok("E1 dohvat preko ekrana je bajt-identičan (iz arhive)", st == 200 and b == slike[0] and "no-store" in h.get("Cache-Control", ""))
        st, b, _ = TE.zahtjev("GET", f"/api/slika/{lok_id}")
        ok("E3 stara lokalna slika ostaje čitljiva uz arhivu", st == 200 and b == lok)
        ok("E1 ista slika dvaput → 409 (ne duplicira)", TE.zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "DIO"}, sirovo=slike[0])[0] == 409)
        ok("E4 AI obrada NIJE pokrenuta ni za jednu sliku", arh.ai_pokrenuto == 0, str(arh.ai_pokrenuto))
        ok("E1 u arhivi je 3 različita dokumenta s app_id kelava-dijelovi", len(arh.dokumenti) == 3 and all(z["app_id"] == "kelava-dijelovi" for z in arh.zahtjevi))
        # E2: arhiva pada usred rada
        prije = TE.q("SELECT count(*) FROM dio_slika WHERE otpad_dio_id=%s", d)[0][0]
        arh.kvar = "500"
        st, r, _ = TE.zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "DIO"}, sirovo=TE.jpeg(41))
        ok("E2 arhiva pala → 502 s čitljivom porukom", st == 502 and "nije spremljena" in r.get("greska", ""), f"{st} {r}")
        ok("E2 u bazi nije nastao redak za neuspjelu sliku", TE.q("SELECT count(*) FROM dio_slika WHERE otpad_dio_id=%s", d)[0][0] == prije)
        arh.kvar = "krivi_original"
        st, r, _ = TE.zahtjev("POST", f"/api/dio/{d}/slika", zaglavlja={"X-Vrsta": "DIO"}, sirovo=TE.jpeg(42))
        ok("A4 readback ne štima → 502 i ništa u bazi", st == 502 and TE.q("SELECT count(*) FROM dio_slika WHERE otpad_dio_id=%s", d)[0][0] == prije, f"{st} {r}")
        arh.kvar = "401"
        st, r, _ = TE.zahtjev("GET", f"/api/slika/{sid}")
        ok("E2 čitanje kad arhiva odbije prijavu → 502 s porukom", st == 502 and "Prijava u arhivu" in r.get("greska", ""), f"{st} {r}")
        arh.kvar = None
        ok("E2 nakon oporavka arhive sve opet radi", TE.zahtjev("GET", f"/api/slika/{sid}")[0] == 200)
    finally:
        srv.terminate()
        arh.stop()
        shutil.rmtree(lokalno, ignore_errors=True)
        try:
            H.psql("postgres", f"DROP DATABASE IF EXISTS {TE.DB}")
        except Exception as e:                                                   # noqa: BLE001
            print(f"upozorenje: čišćenje baze: {e}")

    zakrpa()
    print(f"\nUKUPNO {H.PASS + H.FAIL} · PROŠLO {H.PASS} · PALO {H.FAIL}")
    return 1 if H.FAIL else 0


def _baca(f) -> bool:
    try:
        f()
    except ValueError:
        return True
    return False


def _poruka(f):
    try:
        f()
    except SpremnikGreska as e:
        return str(e)
    return None


def _kontrola_ai(arh: LaznaArhiva) -> bool:
    """Kontrola mjerila: upload s drugim app_id (računi) MORA povećati brojač, inače E4 ne bi ništa dokazivao."""
    sp = ArhivaSpremnik(arh.url, TOKEN, bez_ai_potvrdeno=True, app_id="poslovna-arhiva-dashboard")
    prije = arh.ai_pokrenuto
    sp.spremi(TE.jpeg(99))
    return arh.ai_pokrenuto == prije + 1


def zakrpa() -> None:
    d = tempfile.mkdtemp(prefix="zakrpa_")
    skripta = os.path.join(AQ, "arhiva_spoj", "primijeni_zakrpu.py")
    put = os.path.join(d, "arhiva_core.py")
    fixtura = '''from fastapi import APIRouter
router = APIRouter(prefix="/api/v1/arhiva-core", tags=["arhiva_core"])


async def upload_datoteka(background_tasks, datoteka, app_id="x"):
    dokument, novi = await primi_dokument()
    if not novi:
        return _serialize(dokument)  # idempotentno
    background_tasks.add_task(_obradi_u_pozadini, dokument.weise3_id)
    return _serialize(dokument)


async def obradi_dokument_ep(weise3_id, background_tasks):
    background_tasks.add_task(_obradi_u_pozadini, weise3_id)
'''
    open(put, "w").write(fixtura)
    izv = lambda *a: subprocess.run([sys.executable, "-I", skripta, put, *a], capture_output=True, text=True)
    r = izv("--suho")
    ok("Z1 suho: ne piše ništa", r.returncode == 0 and open(put).read() == fixtura and "SUHO" in r.stdout, r.stdout + r.stderr)
    r = izv()
    novo = open(put).read()
    ok("Z1 primjena: mijenja točno dva mjesta, .bak postoji", r.returncode == 0 and "_APP_ID_BEZ_AI" in novo and novo.count("if app_id not in _APP_ID_BEZ_AI:") == 1
       and any(f.startswith("arhiva_core.py.bak.") for f in os.listdir(d)), r.stdout + r.stderr)
    ok("Z1 /obradi (ručno pokretanje) ostaje netaknut", "background_tasks.add_task(_obradi_u_pozadini, weise3_id)" in novo)
    compile(novo, "arhiva_core.py", "exec")
    ok("Z1 rezultat je valjan Python", True)
    r = izv()
    ok("Z1 druga primjena je bezopasna ('VEĆ PRIMIJENJENO')", r.returncode == 0 and "VEĆ PRIMIJENJENO" in r.stdout and open(put).read() == novo)
    krivi = os.path.join(d, "druga.py"); open(krivi, "w").write(fixtura.replace("return _serialize(dokument)\n\n\nasync def obradi", "return 1\n\n\nasync def obradi"))
    sadrzaj_prije = open(krivi).read()
    r = subprocess.run([sys.executable, "-I", skripta, krivi], capture_output=True, text=True)
    ok("Z1 krivo sidro → STOP bez izmjene", r.returncode == 1 and "STOP" in r.stdout and open(krivi).read() == sadrzaj_prije, r.stdout)
    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
