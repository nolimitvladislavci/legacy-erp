#!/usr/bin/env python3
"""Test modula prodaje na PRIVREMENOJ bazi otpad_prodaja_test (briše je i stvara iznova).

Kriteriji (upisani prije prvog pokretanja):
  S1 shema se može primijeniti dvaput · S2 prodaja: status, 2 izlazna retka, kupac NIGDJE u događajima/izlazu
  S3 jamstvo < 12 mj. za fizičku osobu odbijeno · S4 dvostruka prodaja odbijena · S5 lanac DRZI nakon cijelog toka
  S6 UPDATE/DELETE događaja odbijen · S7 krivotvoreni događaj → PAD · S8 prazan lanac → NEPOZNATO
  P1 odustanak (daljinska, 14 dana) → povrat na zalihu + STORNO · P2 odustanak bez daljinske prodaje odbijen
  P3 istekao rok odustanka odbijen · P4 reklamacija u jamstvu → škart · P5 reklamacija nakon jamstva odbijena
  A1 pad usred prodaje ne ostavlja ništa (atomarnost) · U1 uloga otpad_prodaja ne smije brisati ni mijenjati cijenu
  Q1 qr4d bez konfiguracije → NEPOZNATO, prodaja valjana · Q2 qr4d uživo: HUB3 PNG, X-Provjera DRZI (n = 10)
Pokretanje:  runuser/sudo koji smije `runuser -u postgres`;  python3 -I test_prodaja.py
"""
from __future__ import annotations

import os
import secrets
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psycopg  # noqa: E402

import prodaja as P  # noqa: E402
import qr4d_klijent  # noqa: E402

AQ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = "otpad_prodaja_test"
LOZ = secrets.token_hex(8)
TEST_IBAN = "HR6123400091110000007"          # ispravan po mod 97, IZMIŠLJEN, služi samo za crtanje koda
PASS = FAIL = 0


def ok(naziv: str, uvjet: bool, detalj: str = "") -> None:
    global PASS, FAIL
    if uvjet:
        PASS += 1
        print(f"PROŠLO  {naziv}")
    else:
        FAIL += 1
        print(f"PALO    {naziv} | {detalj}")


def psql(baza: str, sql: str | None = None, datoteka: str | None = None) -> None:
    cmd = ["runuser", "-u", "postgres", "--", "psql", "-X", "-q", "-tA", "-v", "ON_ERROR_STOP=1", "-d", baza]
    cmd += ["-f", datoteka] if datoteka else ["-c", sql]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"psql pao ({baza}): {r.stderr.strip()[:300]}")


def pripremi() -> None:
    if not DB.endswith("_test"):
        raise SystemExit("odbijeno: baza nije testna")
    psql("postgres", f"DROP DATABASE IF EXISTS {DB}")
    psql("postgres", f"CREATE DATABASE {DB}")
    for f in ("schema.sql", "pretraga.sql", "prodaja/schema_prodaja.sql"):
        psql(DB, datoteka=os.path.join(AQ, f))
    psql(DB, datoteka=os.path.join(AQ, "prodaja/schema_prodaja.sql"))                           # S1: drugi put
    psql(DB, f"ALTER ROLE otpad_prodaja PASSWORD '{LOZ}'")
    psql(DB, "GRANT CONNECT ON DATABASE %s TO otpad_prodaja" % DB)


def veza(korisnik: str = "postgres", lozinka: str | None = None) -> psycopg.Connection:
    if korisnik == "postgres":                        # vlasnik tablica: preko unix-socketa kao OS korisnik postgres nije moguće → TCP uloga
        raise RuntimeError("koristi veza_vlasnik()")
    return psycopg.connect(f"host=127.0.0.1 dbname={DB} user={korisnik} password={lozinka}", autocommit=True)


def veza_vlasnik() -> psycopg.Connection:
    return psycopg.connect(f"host=127.0.0.1 dbname={DB} user=prodaja_vlasnik password={LOZ}", autocommit=True)


def novi_dio(c: psycopg.Connection, broj: str, naziv: str = "Svjetlo stražnje lijevo") -> int:
    with c.cursor() as cur:
        cur.execute("INSERT INTO dio (naziv_hr) VALUES (%s) RETURNING id", (naziv,))
        d = cur.fetchone()[0]
        cur.execute("INSERT INTO otpad_dio (dio_id, broj_na_dijelu, polica, stanje, cijena) "
                    "VALUES (%s,%s,'A1','B',25.00) RETURNING id", (d, broj))
        return cur.fetchone()[0]


def stanje(c, dio_id: int) -> str:
    with c.cursor() as cur:
        cur.execute("SELECT status FROM otpad_dio WHERE id=%s", (dio_id,))
        return cur.fetchone()[0]


def broj(c, sql: str, *arg) -> int:
    with c.cursor() as cur:
        cur.execute(sql, arg or None)
        return cur.fetchone()[0]


def pada(f, *a, **k) -> str | None:
    try:
        f(*a, **k)
    except (P.PoslovnaGreska, psycopg.Error) as e:
        return str(e)
    return None


def main() -> int:
    pripremi_ok = False
    try:
        pripremi()
        psql(DB, "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='prodaja_vlasnik') THEN "
                 "CREATE ROLE prodaja_vlasnik LOGIN SUPERUSER; END IF; END $$")
        psql(DB, f"ALTER ROLE prodaja_vlasnik PASSWORD '{LOZ}'")
        pripremi_ok = True
    except Exception as e:                                                           # noqa: BLE001
        print(f"PRIPREMA PALA: {e}")
    if not pripremi_ok:
        return 2
    ok("S1 shema primijenjena dvaput bez greške", True)

    os.environ.pop("KELAVA_PRIMATELJ", None)
    os.environ.pop("KELAVA_IBAN", None)
    c = veza_vlasnik()

    # ── prodaja ──────────────────────────────────────────────────────────────────────────────
    d1 = novi_dio(c, "1K0 945 095 AB")
    r = P.prodaj(c, d1, 3500, "Ivo Ivić, Tenja", fizicka_osoba=True, na_daljinu=True)
    ok("S2 prodaja: status PRODAN", stanje(c, d1) == "PRODAN")
    ok("S2 prodaja: izlazni redovi RACUN + DOKARH", broj(c, "SELECT count(*) FROM izlaz_flota WHERE cilj IN ('RACUN','DOKARH')") == 2)
    tekst = broj(c, "SELECT count(*) FROM dio_dogadjaj WHERE podaci::text ILIKE '%Ivić%' OR podaci::text ILIKE '%Tenja%'") \
        + broj(c, "SELECT count(*) FROM izlaz_flota WHERE podaci::text ILIKE '%Ivić%' OR podaci::text ILIKE '%Tenja%'")
    ok("S2 ime kupca NIJE ni u događajima ni u izlaznom redu", tekst == 0, f"pronađeno {tekst}")
    ok("Q1 bez KELAVA_IBAN: kod NEPOZNATO, prodaja ipak valjana", r["kod"]["stanje"] == "NEPOZNATO" and stanje(c, d1) == "PRODAN",
       str(r["kod"]))

    d2 = novi_dio(c, "5Q0 941 005")
    g = pada(P.prodaj, c, d2, 3500, "Ana", fizicka_osoba=True, jamstvo_mjeseci=6)
    ok("S3 jamstvo 6 mj. za fizičku osobu odbijeno, status ostaje", g is not None and stanje(c, d2) == "NA_ZALIHI", str(g))
    ok("S3b isto 6 mj. za pravnu osobu dopušteno", pada(P.prodaj, c, d2, 3500, "Servis d.o.o.", fizicka_osoba=False, jamstvo_mjeseci=6) is None)
    ok("S4 dvostruka prodaja odbijena", pada(P.prodaj, c, d1, 3500, "Netko") is not None)

    # ── isporuka i odustanak (P1) ────────────────────────────────────────────────────────────
    i = P.isporuci(c, d1)
    ok("P1 isporuka daljinske prodaje daje povrat_do = danas + 14", broj(c, "SELECT (povrat_do - current_date) FROM otpad_dio WHERE id=%s", d1) == 14,
       str(i))
    ok("P1 odustanak u roku prihvaćen", pada(P.zatrazi_povrat, c, d1, "Ne treba mi", vrsta="ODUSTANAK") is None and stanje(c, d1) == "POVRAT_ZATRAZEN")
    z = P.zaprimi_povrat(c, d1, ispravan=True)
    ok("P1 ispravan povrat → NA_ZALIHI i kupac obrisan", z["ishod"] == "NA_ZALIHI" and stanje(c, d1) == "NA_ZALIHI"
       and broj(c, "SELECT count(*) FROM otpad_dio WHERE id=%s AND kupac IS NULL", d1) == 1)
    ok("P1 STORNO u izlaznom redu", broj(c, "SELECT count(*) FROM izlaz_flota WHERE cilj='STORNO'") == 1)
    ok("S5 lanac dijela DRZI nakon cijelog toka", P.provjeri_lanac(c, d1)[0] == "DRZI", str(P.provjeri_lanac(c, d1)))
    ok("S8 dio bez događaja → NEPOZNATO (nikad PAD)", P.provjeri_lanac(c, d2 + 999)[0] == "NEPOZNATO")

    # ── odustanak: odbijanja (P2, P3) ────────────────────────────────────────────────────────
    d3 = novi_dio(c, "3C0 959 855")
    P.prodaj(c, d3, 1000, "Marko", na_daljinu=False)
    P.isporuci(c, d3)
    ok("P2 odustanak bez prodaje na daljinu odbijen", pada(P.zatrazi_povrat, c, d3, "x", vrsta="ODUSTANAK") is not None)
    d4 = novi_dio(c, "6R0 807 217")
    P.prodaj(c, d4, 1000, "Mia", na_daljinu=True)
    P.isporuci(c, d4)
    with c.cursor() as cur:
        cur.execute("UPDATE otpad_dio SET povrat_do = current_date - 1 WHERE id=%s", (d4,))
    ok("P3 istekao rok od 14 dana odbijen", pada(P.zatrazi_povrat, c, d4, "x", vrsta="ODUSTANAK") is not None)

    # ── reklamacija (P4, P5) ─────────────────────────────────────────────────────────────────
    ok("P4 reklamacija u jamstvu prihvaćena", pada(P.zatrazi_povrat, c, d3, "Ne radi") is None)
    ok("P4 neispravan povrat → SKART", P.zaprimi_povrat(c, d3, ispravan=False)["ishod"] == "SKART" and stanje(c, d3) == "SKART")
    with c.cursor() as cur:
        cur.execute("UPDATE otpad_dio SET datum_prodaje = now() - interval '13 months' WHERE id=%s", (d4,))
    ok("P5 reklamacija nakon isteka jamstva (12 mj.) odbijena", pada(P.zatrazi_povrat, c, d4, "Ne radi") is not None)

    # ── nepromjenjivost i krivotvorina (S6, S7) ──────────────────────────────────────────────
    ok("S6 UPDATE događaja odbijen", pada(lambda: c.execute("UPDATE dio_dogadjaj SET vrijeme='x' WHERE id=1")) is not None)
    ok("S6 DELETE događaja odbijen", pada(lambda: c.execute("DELETE FROM dio_dogadjaj WHERE id=1")) is not None)
    c.execute("ALTER TABLE dio_dogadjaj DISABLE TRIGGER dio_dogadjaj_nepromjenjiv")
    c.execute("UPDATE dio_dogadjaj SET podaci = jsonb_set(podaci, '{iznos_centi}', '1') WHERE otpad_dio_id=%s AND vrsta='PRODAJA'", (d1,))
    c.execute("ALTER TABLE dio_dogadjaj ENABLE TRIGGER dio_dogadjaj_nepromjenjiv")
    ok("S7 krivotvoreni iznos u događaju → PAD", P.provjeri_lanac(c, d1)[0] == "PAD", str(P.provjeri_lanac(c, d1)))

    # ── atomarnost (A1) ──────────────────────────────────────────────────────────────────────
    d5 = novi_dio(c, "8E0 820 801")
    ev_prije = broj(c, "SELECT count(*) FROM dio_dogadjaj")
    original = P._izlaz
    def pokvaren(*a, **k):
        raise RuntimeError("simulirani pad usred prodaje")
    P._izlaz = pokvaren
    try:
        g = None
        try:
            P.prodaj(c, d5, 1000, "Pero")
        except RuntimeError:
            g = "pao"
    finally:
        P._izlaz = original
    ok("A1 pad usred prodaje: status i događaji kao prije", g == "pao" and stanje(c, d5) == "NA_ZALIHI"
       and broj(c, "SELECT count(*) FROM dio_dogadjaj") == ev_prije, f"{g} {stanje(c, d5)}")

    # ── najmanja prava (U1) ──────────────────────────────────────────────────────────────────
    u = veza("otpad_prodaja", LOZ)
    ok("U1 uloga otpad_prodaja ne smije DELETE otpad_dio", pada(lambda: u.execute("DELETE FROM otpad_dio WHERE id=%s", (d5,))) is not None)
    ok("U1 uloga ne smije mijenjati cijenu", pada(lambda: u.execute("UPDATE otpad_dio SET cijena=1 WHERE id=%s", (d5,))) is not None)
    ok("U1 uloga smije raditi prodaju (UPDATE statusa + INSERT događaja)", pada(P.prodaj, u, d5, 1000, "Pero") is None and stanje(c, d5) == "PRODAN")
    u.close()

    # ── qr4d uživo (Q2) ──────────────────────────────────────────────────────────────────────
    os.environ["KELAVA_PRIMATELJ"], os.environ["KELAVA_IBAN"] = "Kelava TEST", TEST_IBAN
    drzi, nepoznato, ostalo = 0, 0, []
    for k in range(10):
        dk = novi_dio(c, f"TST{k:03d}000")
        try:
            r = P.prodaj(c, dk, 1000 + k, "Qr kupac")
        except Exception as e:                                                       # noqa: BLE001
            ostalo.append(str(e)[:80])
            continue
        s = r["kod"]["stanje"]
        if s == "DRZI" and r["kod"].get("png", b"").startswith(b"\x89PNG"):
            drzi += 1
        elif s == "NEPOZNATO":
            nepoznato += 1
        else:
            ostalo.append(s)
    if nepoznato == 10:
        print(f"NEPOZNATO Q2 qr4d nedostupan 10/10 (nije prolaz ni pad)")
    else:
        ok("Q2 qr4d uživo: HUB3 PNG s X-Provjera DRZI", drzi == 10, f"DRZI {drzi}/10, NEPOZNATO {nepoznato}, ostalo {ostalo}")
        ok("Q2 PLACANJE_KOD događaj zapisan za svaku prodaju s kodom",
           broj(c, "SELECT count(*) FROM dio_dogadjaj WHERE vrsta='PLACANJE_KOD'") == drzi)

    c.close()
    try:                                                    # čišćenje: testna baza i privremena superuser uloga
        psql("postgres", f"DROP DATABASE IF EXISTS {DB}")
        psql("postgres", "DROP ROLE IF EXISTS prodaja_vlasnik")
    except Exception as e:                                  # noqa: BLE001
        print(f"upozorenje: čišćenje nije uspjelo: {e}")
    print(f"\nUKUPNO {PASS + FAIL} · PROŠLO {PASS} · PALO {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
