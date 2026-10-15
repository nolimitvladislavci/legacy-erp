"""Prodaja, isporuka, povrat i reklamacija dijela s otpada (otpad_katalog).

Tok: NA_ZALIHI → PRODAN → ISPORUCEN → POVRAT_ZATRAZEN → NA_ZALIHI | SKART.
Dio ulazi u račun/fiskalizaciju/lanac TEK pri prodaji (izlaz_flota, cilj RACUN + DOKARH).
Povrat piše STORNO u isti red; fiskalni storno radi postojeći modul flote, ne mi.

Svaki korak je jedna transakcija: promjena statusa + događaj u lancu + izlazni red, ili ništa.
Osobni podaci kupca ostaju u otpad_dio.kupac i NE ulaze ni u događaje ni u izlazni red.

Zakonske granice (NAPISANO, potvrditi s knjigovođom/odvjetnikom): za fizičku osobu rabljeno ≥ 12 mj.
(ZZP/EU 2019/771), odustanak 14 dana samo kod prodaje na daljinu.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone

import psycopg

import qr4d_klijent

GENEZA = "GENEZA"
MIN_JAMSTVO_FIZICKA = 12
ODUSTANAK_DANA = 14


class PoslovnaGreska(Exception):
    """Radnja nije dopuštena u trenutnom stanju dijela (poruka je za radnicu, hrvatski)."""


def _kanon(podaci: dict) -> str:
    return json.dumps(podaci, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(prev: str, dio_id: int, vrsta: str, podaci: dict, vrijeme: str) -> str:
    return hashlib.sha256(f"{prev}|{dio_id}|{vrsta}|{_kanon(podaci)}|{vrijeme}".encode()).hexdigest()


def _dogadjaj(cur, dio_id: int, vrsta: str, podaci: dict) -> tuple[int, str]:
    cur.execute("SELECT hash FROM dio_dogadjaj WHERE otpad_dio_id=%s ORDER BY id DESC LIMIT 1", (dio_id,))
    r = cur.fetchone()
    prev = r[0] if r else GENEZA
    vrijeme = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    h = _hash(prev, dio_id, vrsta, podaci, vrijeme)
    cur.execute("INSERT INTO dio_dogadjaj (otpad_dio_id, vrsta, vrijeme, podaci, prev_hash, hash) "
                "VALUES (%s,%s,%s,%s::jsonb,%s,%s) RETURNING id",
                (dio_id, vrsta, vrijeme, _kanon(podaci), prev, h))
    return cur.fetchone()[0], h


def _izlaz(cur, dogadjaj_id: int, cilj: str, podaci: dict) -> None:
    cur.execute("INSERT INTO izlaz_flota (dogadjaj_id, cilj, podaci) VALUES (%s,%s,%s::jsonb)",
                (dogadjaj_id, cilj, _kanon(podaci)))


def _zakljucaj(cur, dio_id: int) -> dict:
    cur.execute("""SELECT d.id, d.status, d.broj_norm, d.polica, d.cijena, d.jamstvo_mjeseci, d.kupac_fizicka_osoba,
                          d.prodano_na_daljinu, d.prodajna_cijena_centi, d.datum_prodaje, d.povrat_do,
                          coalesce(k.naziv_hr, '')
                   FROM otpad_dio d LEFT JOIN dio k ON k.id = d.dio_id
                   WHERE d.id = %s FOR UPDATE OF d""", (dio_id,))
    r = cur.fetchone()
    if r is None:
        raise PoslovnaGreska(f"Dio {dio_id} ne postoji.")
    k = ("id", "status", "broj_norm", "polica", "cijena", "jamstvo_mjeseci", "fizicka", "daljinska",
         "cijena_centi", "datum_prodaje", "povrat_do", "naziv")
    return dict(zip(k, r))


def _kod_placanja(conn, d: dict, iznos_centi: int) -> dict:
    """Kod za plaćanje preko qr4d servisa flote. Zove se NAKON commita prodaje (mrežni poziv ne drži zaključan redak).
    Nedostupan servis = NEPOZNATO, prodaja ipak ostaje valjana."""
    primatelj, iban = os.environ.get("KELAVA_PRIMATELJ", ""), os.environ.get("KELAVA_IBAN", "")
    if not primatelj or not iban:
        return {"stanje": "NEPOZNATO", "razlog": "KELAVA_PRIMATELJ / KELAVA_IBAN nisu postavljeni"}
    opis = re.sub(r"[^0-9A-Za-zČĆĐŠŽčćđšž ,.:+?'/()-]", "", f"Dio {d['id']} {d['broj_norm'] or ''}")[:35]
    try:
        k = qr4d_klijent.uplatnica(primatelj[:25], iban, iznos_centi, opis)
    except qr4d_klijent.Qr4dNedostupan as e:
        return {"stanje": "NEPOZNATO", "razlog": str(e)}
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT 1 FROM otpad_dio WHERE id=%s FOR UPDATE", (d["id"],))
        _dogadjaj(cur, d["id"], "PLACANJE_KOD", {"oblik": k["oblik"], "provjera": k["provjera"],
                                                  "png_sha256": k["sha256"], "iznos_centi": iznos_centi})
    return {"stanje": k["provjera"], "png": k["png"], "oblik": k["oblik"]}


def prodaj(conn: psycopg.Connection, dio_id: int, iznos_centi: int, kupac: str, *, fizicka_osoba: bool = True,
           na_daljinu: bool = False, jamstvo_mjeseci: int | None = None) -> dict:
    """PRODAJA: status PRODAN + događaj + izlaz RACUN i DOKARH + kod plaćanja. Vraća {hash, kod}."""
    if iznos_centi <= 0:
        raise PoslovnaGreska("Cijena mora biti veća od 0.")
    if not kupac.strip():
        raise PoslovnaGreska("Upiši kupca.")
    with conn.transaction(), conn.cursor() as cur:
        d = _zakljucaj(cur, dio_id)
        if d["status"] not in ("NA_ZALIHI", "REZERVIRAN"):
            raise PoslovnaGreska(f"Dio nije na zalihi (stanje: {d['status']}).")
        jamstvo = d["jamstvo_mjeseci"] if jamstvo_mjeseci is None else jamstvo_mjeseci
        if fizicka_osoba and jamstvo < MIN_JAMSTVO_FIZICKA:
            raise PoslovnaGreska(f"Fizičkoj osobi jamstvo ne može biti kraće od {MIN_JAMSTVO_FIZICKA} mjeseci.")
        cur.execute("""UPDATE otpad_dio SET status='PRODAN', kupac=%s, kupac_fizicka_osoba=%s, prodano_na_daljinu=%s,
                       prodajna_cijena_centi=%s, jamstvo_mjeseci=%s, datum_prodaje=now() WHERE id=%s""",
                    (kupac.strip(), fizicka_osoba, na_daljinu, iznos_centi, jamstvo, dio_id))
        podaci = {"dio": dio_id, "broj": d["broj_norm"], "iznos_centi": iznos_centi, "jamstvo_mjeseci": jamstvo,
                  "fizicka_osoba": fizicka_osoba, "na_daljinu": na_daljinu}
        did, h = _dogadjaj(cur, dio_id, "PRODAJA", podaci)
        stavka = {"naziv": d["naziv"] or f"Dio {d['broj_norm']}", "broj": d["broj_norm"], "kolicina": 1,
                  "cijena_centi": iznos_centi, "jamstvo_mjeseci": jamstvo, "kupac_ref": f"otpad_dio:{dio_id}",
                  "lanac_hash": h}
        _izlaz(cur, did, "RACUN", stavka)
        _izlaz(cur, did, "DOKARH", {"tip": "PRODAJA_DIJELA", "dio": dio_id, "lanac_hash": h})
    kod = _kod_placanja(conn, d, iznos_centi)
    return {"hash": h, "kod": kod}


def isporuci(conn: psycopg.Connection, dio_id: int) -> dict:
    """ISPORUKA: PRODAN → ISPORUCEN. Kod prodaje na daljinu od tada teče 14 dana za odustanak."""
    with conn.transaction(), conn.cursor() as cur:
        d = _zakljucaj(cur, dio_id)
        if d["status"] != "PRODAN":
            raise PoslovnaGreska(f"Dio nije prodan (stanje: {d['status']}).")
        cur.execute("""UPDATE otpad_dio SET status='ISPORUCEN',
                       povrat_do = CASE WHEN prodano_na_daljinu THEN current_date + %s ELSE NULL END
                       WHERE id=%s RETURNING povrat_do""", (ODUSTANAK_DANA, dio_id))
        povrat_do = cur.fetchone()[0]
        _, h = _dogadjaj(cur, dio_id, "ISPORUKA", {"dio": dio_id, "povrat_do": povrat_do.isoformat() if povrat_do else None})
    return {"hash": h, "povrat_do": povrat_do}


def zatrazi_povrat(conn: psycopg.Connection, dio_id: int, razlog: str, *, vrsta: str = "REKLAMACIJA") -> dict:
    """POVRAT: ODUSTANAK (14 dana, samo na daljinu) ili REKLAMACIJA (unutar jamstvenog roka)."""
    if vrsta not in ("ODUSTANAK", "REKLAMACIJA"):
        raise PoslovnaGreska("Vrsta mora biti ODUSTANAK ili REKLAMACIJA.")
    if not razlog.strip():
        raise PoslovnaGreska("Upiši razlog povrata.")
    with conn.transaction(), conn.cursor() as cur:
        d = _zakljucaj(cur, dio_id)
        if d["status"] not in ("PRODAN", "ISPORUCEN"):
            raise PoslovnaGreska(f"Za ovaj dio povrat nije moguć (stanje: {d['status']}).")
        if vrsta == "ODUSTANAK":
            cur.execute("SELECT prodano_na_daljinu, povrat_do >= current_date FROM otpad_dio WHERE id=%s", (dio_id,))
            daljinska, u_roku = cur.fetchone()
            if not daljinska:
                raise PoslovnaGreska("Pravo na odustanak od 14 dana vrijedi samo za prodaju na daljinu.")
            if d["status"] == "ISPORUCEN" and not u_roku:
                raise PoslovnaGreska("Rok za odustanak (14 dana od isporuke) je istekao.")
        else:
            cur.execute("SELECT now() <= datum_prodaje + make_interval(months => jamstvo_mjeseci) "
                        "FROM otpad_dio WHERE id=%s", (dio_id,))
            if not cur.fetchone()[0]:
                raise PoslovnaGreska("Jamstveni rok je istekao.")
        cur.execute("UPDATE otpad_dio SET status='POVRAT_ZATRAZEN' WHERE id=%s", (dio_id,))
        _, h = _dogadjaj(cur, dio_id, "POVRAT_ZATRAZEN", {"dio": dio_id, "vrsta": vrsta, "razlog": razlog.strip()[:200]})
    return {"hash": h}


def zaprimi_povrat(conn: psycopg.Connection, dio_id: int, ispravan: bool) -> dict:
    """ZAPRIMLJEN: ispravan dio ide natrag na zalihu, neispravan u škart. Uvijek se piše STORNO za flotu."""
    with conn.transaction(), conn.cursor() as cur:
        d = _zakljucaj(cur, dio_id)
        if d["status"] != "POVRAT_ZATRAZEN":
            raise PoslovnaGreska(f"Povrat nije zatražen (stanje: {d['status']}).")
        novi = "NA_ZALIHI" if ispravan else "SKART"
        cur.execute("""UPDATE otpad_dio SET status=%s, kupac=NULL, kupac_fizicka_osoba=NULL, prodano_na_daljinu=NULL,
                       prodajna_cijena_centi=NULL, datum_prodaje=NULL, povrat_do=NULL WHERE id=%s""", (novi, dio_id))
        did, h = _dogadjaj(cur, dio_id, "POVRAT_ZAPRIMLJEN", {"dio": dio_id, "ishod": novi, "iznos_centi": d["cijena_centi"]})
        _izlaz(cur, did, "STORNO", {"dio": dio_id, "iznos_centi": d["cijena_centi"], "kupac_ref": f"otpad_dio:{dio_id}",
                                    "lanac_hash": h})
        _izlaz(cur, did, "DOKARH", {"tip": "POVRAT_DIJELA", "dio": dio_id, "ishod": novi, "lanac_hash": h})
    return {"hash": h, "ishod": novi}


def provjeri_lanac(conn: psycopg.Connection, dio_id: int) -> tuple[str, str]:
    """Trostanje: DRZI | PAD | NEPOZNATO (prazan lanac je NEPOZNATO, nikad PAD). Presuđuje kod, ne AI."""
    with conn.cursor() as cur:
        cur.execute("SELECT vrsta, vrijeme, podaci, prev_hash, hash FROM dio_dogadjaj WHERE otpad_dio_id=%s ORDER BY id",
                    (dio_id,))
        redovi = cur.fetchall()
    if not redovi:
        return "NEPOZNATO", "dio nema događaja"
    prev = GENEZA
    for i, (vrsta, vrijeme, podaci, prev_hash, h) in enumerate(redovi, 1):
        if prev_hash != prev:
            return "PAD", f"događaj {i}: prev_hash ne odgovara prethodnom"
        if _hash(prev, dio_id, vrsta, podaci, vrijeme) != h:
            return "PAD", f"događaj {i}: sadržaj ne odgovara hashu"
        prev = h
    return "DRZI", ""
