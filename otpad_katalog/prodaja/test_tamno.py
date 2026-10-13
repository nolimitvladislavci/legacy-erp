#!/usr/bin/env python3
"""Test tamnog dijela (tamno.py) na PRIVREMENOJ bazi otpad_tamno_test. Kriteriji upisani prije pokretanja:
  T1 rođenje (token, događaj, nepoznat donor odbijen) · T2 NEPOZNATO prepoznavanje ipak rađa dio
  T3 OPRAN traži sliku · T4 TESTIRAN: PAD → SKART, krivo stanje odbijeno · T5 PAKIRAN traži sliku + dimenzije
  T6 spremanje/premještanje (nepostojeći pretinac odbijen, zadnja lokacija = zadnji događaj) · T7 kartica · T8 put po hali
  V1 nepotpun dio ne smije van (sa svim razlozima, bez promjene) · V2 potpun prolazi: status, cijena, jamstvo, 2 izlazna atoma
  V3 oglas nosi samo javne slike · V4 Merkle korijen DRZI, krivotvoreni dnevnik PAD · V5 Merkle vektori (1, 2, 3 lista)
  V6 lanac cijelog toka DRZI · V7 PRAVNA_BEZ ne može B2C · V8 tjedni korijen · V9 alias starog koda · V10 tuđa slika odbijena
  H3 isti događaj: HUB3 i GiroCode iz iznosa događaja, dekodirani drugim čitačem, iznos jednak (n = 10, uživo qr4d)
Pokretanje:  python3 -I test_tamno.py
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psycopg  # noqa: E402

import prodaja as P  # noqa: E402
import qr4d_klijent  # noqa: E402
import tamno as T  # noqa: E402
import test_prodaja as H  # noqa: E402  (pomoćne funkcije: psql, ok, pada, broj)

H.DB = DB = "otpad_tamno_test"
LOZ = secrets.token_hex(8)
AQ = H.AQ
TEST_IBAN = "HR6123400091110000007"


def sha(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()


def veza() -> psycopg.Connection:
    return psycopg.connect(f"host=127.0.0.1 dbname={DB} user=prodaja_vlasnik password={LOZ}", autocommit=True)


def pripremi_dio(c, donor, pretinac="R01-P1-01", n_slika=3, test="DRZI", ime="Alternator") -> int:
    """Potpun dio spreman za vrata."""
    r = T.rodi(c, donor, broj_na_dijelu="0 124 525 040", prepoznavanje="OCR")
    d = r["id"]
    for k in range(n_slika):
        T.zabiljezi_sliku(c, d, "DIO", sha(f"{d}-dio-{k}"), f"arhiva://{d}/dio{k}")
    T.zabiljezi_sliku(c, d, "POSLIJE_PRANJA", sha(f"{d}-pr"), f"arhiva://{d}/pr")
    T.predradnja(c, d, "OPRAN")
    T.predradnja(c, d, "TESTIRAN", stanje=test)
    T.zabiljezi_sliku(c, d, "PAKET", sha(f"{d}-pk"), f"arhiva://{d}/pk")
    T.predradnja(c, d, "PAKIRAN", dimenzije_cm="30x20x15", tezina_g=3200)
    if test != "PAD":
        T.spremi(c, d, pretinac)
    return d


def main() -> int:
    ok, pada, broj = H.ok, H.pada, H.broj
    try:
        H.psql("postgres", f"DROP DATABASE IF EXISTS {DB}"); H.psql("postgres", f"CREATE DATABASE {DB}")
        for f in ("schema.sql", "pretraga.sql", "prodaja/schema_prodaja.sql", "prodaja/schema_tamno.sql", "prodaja/schema_tamno.sql"):
            H.psql(DB, datoteka=os.path.join(AQ, f))
        H.psql(DB, "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='prodaja_vlasnik') THEN "
                   "CREATE ROLE prodaja_vlasnik LOGIN SUPERUSER; END IF; END $$")
        H.psql(DB, f"ALTER ROLE prodaja_vlasnik PASSWORD '{LOZ}'")
    except Exception as e:                                                       # noqa: BLE001
        print(f"PRIPREMA PALA: {e}"); return 2
    ok("T0 sheme primijenjene dvaput bez greške", True)
    c = veza()
    for a in ("R01-P1-01", "R01-P1-02", "R03-P2-04", "R02-P1-10"):
        c.execute("INSERT INTO pretinac (adresa) VALUES (%s)", (a,))
    c.execute("INSERT INTO otpad_vozilo (vin) VALUES ('WVWZZZ1JZ3W386752') RETURNING id")
    donor = c.execute("SELECT id FROM otpad_vozilo LIMIT 1").fetchone()[0]
    os.environ.pop("KELAVA_IBAN", None); os.environ.pop("KELAVA_PRIMATELJ", None)

    # T1, T2
    r = T.rodi(c, donor, broj_na_dijelu="1K0 615 301 AA", prepoznavanje="OCR")
    ok("T1 rođenje: status RODEN, token od 16 znakova, događaj RODEN",
       P.__name__ and broj(c, "SELECT count(*) FROM otpad_dio WHERE id=%s AND status='RODEN' AND length(token)=16", r["id"]) == 1
       and broj(c, "SELECT count(*) FROM dio_dogadjaj WHERE otpad_dio_id=%s AND vrsta='RODEN'", r["id"]) == 1)
    ok("T1 nepostojeći donor odbijen", pada(T.rodi, c, 9999) is not None)
    ok("T1 neispravan način prepoznavanja odbijen", pada(T.rodi, c, donor, prepoznavanje="PRETPOSTAVKA") is not None)
    n = T.rodi(c, donor, prepoznavanje="NEPOZNATO")
    ok("T2 nepoznat tip: dio se ipak rađa", n["id"] > 0 and broj(c, "SELECT count(*) FROM otpad_dio WHERE id=%s AND dio_id IS NULL", n["id"]) == 1)
    ok("T1 tokeni su različiti", r["token"] != n["token"])

    # T3–T5
    d = r["id"]
    ok("T3 OPRAN bez slike poslije pranja odbijen", pada(T.predradnja, c, d, "OPRAN") is not None)
    T.zabiljezi_sliku(c, d, "POSLIJE_PRANJA", sha("pr"), "arhiva://pr")
    ok("T3 OPRAN sa slikom prolazi, status PREDRADNJE", pada(T.predradnja, c, d, "OPRAN") is None and H.broj(c, "SELECT count(*) FROM otpad_dio WHERE id=%s AND status='PREDRADNJE'", d) == 1)
    ok("T4 test sa stanjem 'možda' odbijen", pada(T.predradnja, c, d, "TESTIRAN", stanje="MOZDA") is not None)
    ok("T5 PAKIRAN bez slike paketa odbijen", pada(T.predradnja, c, d, "PAKIRAN", dimenzije_cm="1x1x1", tezina_g=10) is not None)
    T.zabiljezi_sliku(c, d, "PAKET", sha("pk"), "arhiva://pk")
    ok("T5 PAKIRAN bez dimenzija odbijen", pada(T.predradnja, c, d, "PAKIRAN", tezina_g=100) is not None)
    ok("T5 PAKIRAN s paketom, dimenzijama i težinom prolazi", pada(T.predradnja, c, d, "PAKIRAN", dimenzije_cm="30x20x15", tezina_g=3200) is None)
    dp = T.rodi(c, donor)["id"]
    T.predradnja(c, dp, "TESTIRAN", stanje="PAD")
    ok("T4 test PAD → SKART", H.broj(c, "SELECT count(*) FROM otpad_dio WHERE id=%s AND status='SKART'", dp) == 1)
    ok("T4 škart se više ne obrađuje", pada(T.predradnja, c, dp, "OPRAN") is not None)

    # T6–T8
    ok("T6 nepostojeći pretinac odbijen", pada(T.spremi, c, d, "R99-P9-99") is not None)
    s1 = T.spremi(c, d, "R03-P2-04")
    ok("T6 spremanje: NA_STALAZI + događaj SPREMLJEN", s1["status"] == "NA_STALAZI" and broj(c, "SELECT count(*) FROM dio_dogadjaj WHERE otpad_dio_id=%s AND vrsta='SPREMLJEN'", d) == 1)
    T.spremi(c, d, "R01-P1-02")
    ok("T6 premještaj: događaj PREMJESTEN, zadnja lokacija = novi pretinac",
       broj(c, "SELECT count(*) FROM dio_dogadjaj WHERE otpad_dio_id=%s AND vrsta='PREMJESTEN' AND podaci->>'od'='R03-P2-04' AND podaci->>'na'='R01-P1-02'", d) == 1
       and T.kartica(c, d)["pretinac"] == "R01-P1-02")
    T.zabiljezi_sliku(c, d, "POLICA", sha("pol"), "arhiva://pol")
    k = T.kartica(c, d)
    ok("T7 kartica: adresa, regal/polica/mjesto i slika police", (k["regal"], k["polica"], k["mjesto"]) == (1, 1, 2) and k["slika_police"] == "arhiva://pol", str(k))
    ok("T8 put po hali: regal, polica, pretinac", T.put_po_hali(["R03-P2-04", "R01-P1-02", "R02-P1-10", "R01-P1-01"]) == ["R01-P1-01", "R01-P1-02", "R02-P1-10", "R03-P2-04"])

    # V1: vrata za nepotpun dio
    nepotpun = T.rodi(c, donor)["id"]
    raz = T.provjere_vrata(c, nepotpun, None, None, [])
    g = pada(T.stavi_u_prodaju, c, nepotpun, 1000, "POTROSAC_12M", [])
    ok("V1 nepotpun dio: ≥ 6 razloga", len(raz) >= 6, str(raz))
    ok("V1 vrata odbijaju, status i izlaz ostaju netaknuti", g is not None and broj(c, "SELECT count(*) FROM otpad_dio WHERE id=%s AND status='RODEN'", nepotpun) == 1
       and broj(c, "SELECT count(*) FROM izlaz_flota WHERE cilj='LANAC_SVJETLO'") == 0, str(g))

    # V2–V4, V6: potpun dio kroz vrata
    dd = pripremi_dio(c, donor, "R01-P1-01")
    slike = [x[0] for x in c.execute("SELECT id FROM dio_slika WHERE otpad_dio_id=%s AND vrsta='DIO' ORDER BY id", (dd,)).fetchall()]
    tuda = T.zabiljezi_sliku(c, d, "DIO", sha("tuda"), "arhiva://tuda")["slika"]
    ok("V10 tuđa slika kao javna odbijena", pada(T.stavi_u_prodaju, c, dd, 3500, "POTROSAC_12M",
       [tuda]) is not None)
    ok("V1b test koji nije DRZI blokira vrata", len(T.provjere_vrata(c, d, 1000, "POTROSAC_12M", [1])) > 0)
    v = T.stavi_u_prodaju(c, dd, 3500, "POTROSAC_12M", slike[:2])
    ok("V2 status NA_ZALIHI, cijena 35.00, jamstvo 12, razred upisan",
       broj(c, "SELECT count(*) FROM otpad_dio WHERE id=%s AND status='NA_ZALIHI' AND cijena=35.00 AND jamstvo_mjeseci=12 AND razred_jamstva='POTROSAC_12M'", dd) == 1)
    ok("V2 izlazni atomi LANAC_SVJETLO i OGLAS (po jedan)", broj(c, "SELECT count(*) FROM izlaz_flota WHERE cilj='LANAC_SVJETLO'") == 1
       and broj(c, "SELECT count(*) FROM izlaz_flota WHERE cilj='OGLAS'") == 1)
    ok("V3 oglas nosi samo 2 odabrane javne slike", broj(c, "SELECT jsonb_array_length(podaci->'slike') FROM izlaz_flota WHERE cilj='OGLAS'") == 2
       and broj(c, "SELECT count(*) FROM dio_slika WHERE otpad_dio_id=%s AND javna", dd) == 2)
    ok("V2 atom svjetla nosi korijen, a ne sadržaj dnevnika",
       broj(c, "SELECT count(*) FROM izlaz_flota WHERE cilj='LANAC_SVJETLO' AND podaci ? 'merkle_koren' AND NOT podaci ? 'slike'") == 1)
    ok("V4 Merkle korijen odgovara dnevniku → DRZI", T.provjeri_svjetlo(c, dd)[0] == "DRZI", str(T.provjeri_svjetlo(c, dd)))
    ok("V6 hash-lanac cijelog toka DRZI", P.provjeri_lanac(c, dd)[0] == "DRZI", str(P.provjeri_lanac(c, dd)))
    ok("V4 dio koji nije u prodaji → NEPOZNATO", T.provjeri_svjetlo(c, d)[0] == "NEPOZNATO")
    c.execute("ALTER TABLE dio_dogadjaj DISABLE TRIGGER dio_dogadjaj_nepromjenjiv")
    c.execute("UPDATE dio_dogadjaj SET podaci = jsonb_set(podaci, '{tezina_g}', '1') WHERE otpad_dio_id=%s AND vrsta='PAKIRAN'", (dd,))
    c.execute("ALTER TABLE dio_dogadjaj ENABLE TRIGGER dio_dogadjaj_nepromjenjiv")
    ok("V4 krivotvoren zapis pakiranja → PAD", T.provjeri_svjetlo(c, dd)[0] == "PAD" and P.provjeri_lanac(c, dd)[0] == "PAD")

    # V5 Merkle vektori
    a, b, cc = (hashlib.sha256(x).hexdigest() for x in (b"a", b"b", b"c"))
    h2 = hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).digest()
    h3 = hashlib.sha256(bytes.fromhex(cc) + bytes.fromhex(cc)).digest()
    ok("V5 Merkle: jedan list = sam list; prazno = None", T.merkle_koren([a]) == a and T.merkle_koren([]) is None)
    ok("V5 Merkle: dva lista", T.merkle_koren([a, b]) == h2.hex())
    ok("V5 Merkle: tri lista (zadnji se udvostručuje)", T.merkle_koren([a, b, cc]) == hashlib.sha256(h2 + h3).hexdigest())

    # V7: B2C bez garancije nije dopušteno
    pb = pripremi_dio(c, donor, "R01-P1-02")
    sl = [x[0] for x in c.execute("SELECT id FROM dio_slika WHERE otpad_dio_id=%s AND vrsta='DIO'", (pb,)).fetchall()]
    T.stavi_u_prodaju(c, pb, 1000, "PRAVNA_BEZ", sl[:1])
    ok("V7 PAVNA_BEZ: fizičkoj osobi odbijeno", pada(P.prodaj, c, pb, 1000, "Ana", fizicka_osoba=True) is not None)
    ok("V7 PRAVNA_BEZ: pravnoj osobi dopušteno (jamstvo 0)", pada(P.prodaj, c, pb, 1000, "Servis d.o.o.", fizicka_osoba=False) is None
       and broj(c, "SELECT jamstvo_mjeseci FROM otpad_dio WHERE id=%s", pb) == 0)

    # V8 tjedni korijen; V9 alias
    tj = T.tjedni_korijen(c)
    ok("V8 tjedni korijen DRZI i zapisan u izlaz (bez sadržaja)", tj["stanje"] == "DRZI" and tj["broj_dijelova"] >= 1
       and broj(c, "SELECT count(*) FROM izlaz_flota WHERE cilj='LANAC_TJEDNI' AND dogadjaj_id IS NULL") == 1, str(tj))
    T.dodaj_alias(c, "03407429544699306998215032", r["token"])
    ok("V9 stari Code 128 broj vodi na dio preko aliasa", T.po_aliasu(c, "03407429544699306998215032") == d and T.po_aliasu(c, "x") is None)
    ok("V9 isti alias dvaput odbijen", pada(T.dodaj_alias, c, "03407429544699306998215032", n["token"]) is not None)

    # H3 uživo
    try:
        import zxingcpp
        from PIL import Image
        import io
    except ImportError:
        zxingcpp = None
    os.environ["KELAVA_PRIMATELJ"], os.environ["KELAVA_IBAN"] = "Kelava TEST", TEST_IBAN
    if zxingcpp is None:
        print("NEPOZNATO H3 zxing-cpp nije instaliran (pip install zxing-cpp pillow)")
    else:
        slaganje, nepoznato, ostalo = 0, 0, []
        for k in range(10):
            dk = pripremi_dio(c, donor, "R02-P1-10")
            sk = [x[0] for x in c.execute("SELECT id FROM dio_slika WHERE otpad_dio_id=%s AND vrsta='DIO'", (dk,)).fetchall()]
            T.stavi_u_prodaju(c, dk, 1000 + 137 * k, "POTROSAC_12M", sk[:1])
            P.prodaj(c, dk, 1000 + 137 * k, "Kupac")
            iznos, hd = T.iznos_iz_dogadjaja(c, dk)
            try:
                hub = qr4d_klijent.uplatnica("Kelava TEST", TEST_IBAN, iznos, f"Dio {dk}", oblik="hub3")
                epc = qr4d_klijent.uplatnica("Kelava TEST", TEST_IBAN, iznos, f"Dio {dk}", oblik="epc")
            except qr4d_klijent.Qr4dNedostupan as e:
                nepoznato += 1; ostalo.append(str(e)[:60]); continue
            bh = zxingcpp.read_barcodes(Image.open(io.BytesIO(hub["png"])))
            be = zxingcpp.read_barcodes(Image.open(io.BytesIO(epc["png"])))
            if not bh or not be:
                ostalo.append("nečitljivo"); continue
            iznos_hub = int(bh[0].bytes.split(b"\n")[2])
            iznos_epc = round(float(be[0].bytes.split(b"\n")[7][3:].decode()) * 100)
            if iznos_hub == iznos_epc == iznos:
                slaganje += 1
            else:
                ostalo.append(f"{iznos}/{iznos_hub}/{iznos_epc}")
        if nepoznato == 10:
            print("NEPOZNATO H3 qr4d nedostupan 10/10 (nije prolaz ni pad)")
        else:
            ok("H3 HUB3 i GiroCode nose isti iznos kao događaj PRODAJA (n = 10)", slaganje == 10, f"{slaganje}/10, ostalo {ostalo}")

    c.close()
    try:
        H.psql("postgres", f"DROP DATABASE IF EXISTS {DB}"); H.psql("postgres", "DROP ROLE IF EXISTS prodaja_vlasnik")
    except Exception as e:                                                       # noqa: BLE001
        print(f"upozorenje: čišćenje nije uspjelo: {e}")
    print(f"\nUKUPNO {H.PASS + H.FAIL} · PROŠLO {H.PASS} · PALO {H.FAIL}")
    return 1 if H.FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
