"""HTTP rukovatelji za tamni dio: pretinci, rođenje dijela, slike, predradnje, spremanje, vrata prema svjetlu.

Sva logika je u ../prodaja/tamno.py i prodaja.py (jedna istina); ovdje samo provjera ulaza i oblik odgovora.
Konekcije su OBIČNE (tuple) jer tamno.py indeksira retke; postojeći ekran koristi dict_row posebno.
Svaka radnja je jedna transakcija; odgovor se šalje tek nakon commita (to osigurava `with veza_t()` u server.py).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prodaja"))
import prodaja as P  # noqa: E402
import tamno as T  # noqa: E402
from arhiva_spremnik import SpremnikGreska  # noqa: E402
from greske import Greska  # noqa: E402

MAX_SLIKA = 15 * 1024 * 1024
VRSTE_SLIKA = ("DIO", "POSLIJE_PRANJA", "PAKET", "POLICA")
TOKEN = re.compile(r"[A-Z2-7]{16}")
STATUSI_TAMNI = ("RODEN", "PREDRADNJE", "NA_STALAZI")


def _uvijek(f, *a, **k):
    """PoslovnaGreska → 409 s porukom za radnicu."""
    try:
        return f(*a, **k)
    except P.PoslovnaGreska as e:
        raise Greska(409, str(e))


def tip_slike(b: bytes) -> str | None:
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    return None


# ── pretinci ────────────────────────────────────────────────────────────────────────────────────
def pretinci_popis(con) -> dict:
    with con.cursor() as cur:
        cur.execute("""SELECT p.adresa, coalesce(p.opis, ''),
                              count(o.id) FILTER (WHERE o.status IN ('NA_STALAZI', 'NA_ZALIHI', 'REZERVIRAN'))
                       FROM pretinac p LEFT JOIN otpad_dio o ON o.pretinac_adresa = p.adresa
                       GROUP BY p.adresa, p.opis ORDER BY p.adresa""")
        return {"pretinci": [{"adresa": a, "opis": o, "dijelova": int(n)} for a, o, n in cur.fetchall()]}


def _cijeli(p: dict, ime: str, lo: int, hi: int, naziv: str) -> int:
    try:
        v = int(str(p.get(ime)).strip())
    except (TypeError, ValueError):
        raise Greska(400, f"{naziv}: upiši broj između {lo} i {hi}.")
    if not lo <= v <= hi:
        raise Greska(400, f"{naziv}: upiši broj između {lo} i {hi}.")
    return v


def pretinci_stvori(con, p: dict) -> dict:
    """Jedna polica odjednom: regal 01–99, polica 1–9, pretinaca 1–40 → R03-P2-01 … R03-P2-08."""
    regal = _cijeli(p, "regal", 1, 99, "Regal")
    polica = _cijeli(p, "polica", 1, 9, "Polica")
    n = _cijeli(p, "pretinaca", 1, 40, "Broj pretinaca")
    novi = 0
    with con.transaction(), con.cursor() as cur:
        for k in range(1, n + 1):
            cur.execute("INSERT INTO pretinac (adresa) VALUES (%s) ON CONFLICT DO NOTHING",
                        (f"R{regal:02d}-P{polica}-{k:02d}",))
            novi += cur.rowcount
    return {"nova": novi, "vec_postojala": n - novi,
            "poruka": f"Pretinci R{regal:02d}-P{polica}: dodano {novi}" + (f", već postoji {n - novi}." if n - novi else ".")}


def pretinac_sadrzaj(con, adresa: str) -> dict:
    with con.cursor() as cur:
        cur.execute("SELECT 1 FROM pretinac WHERE adresa=%s", (adresa,))
        if cur.fetchone() is None:
            raise Greska(404, f"Pretinac {adresa} ne postoji.")
        cur.execute("""SELECT o.id, coalesce(d.naziv_hr, 'Nepoznat dio'), o.broj_na_dijelu, o.status, o.token
                       FROM otpad_dio o LEFT JOIN dio d ON d.id = o.dio_id
                       WHERE o.pretinac_adresa=%s AND o.status IN ('NA_STALAZI', 'NA_ZALIHI', 'REZERVIRAN') ORDER BY o.id""",
                    (adresa,))
        return {"vrsta": "pretinac", "adresa": adresa,
                "dijelovi": [{"id": i, "naziv": n, "broj": b, "status": s, "token": t} for i, n, b, s, t in cur.fetchall()]}


# ── dio ─────────────────────────────────────────────────────────────────────────────────────────
def _checklist(cur, dio_id: int, pretinac: str | None) -> dict:
    dnevnik = T._dnevnik(cur, dio_id)
    testovi = [p.get("stanje") for v, p, _h in dnevnik if v == "TESTIRAN"]
    cur.execute("SELECT vrsta, count(*) FROM dio_slika WHERE otpad_dio_id=%s GROUP BY vrsta", (dio_id,))
    slike = {v: int(n) for v, n in cur.fetchall()}
    return {"slika_dio": slike.get("DIO", 0), "slika_dio_treba": T.MIN_SLIKA,
            "slika_pranje": slike.get("POSLIJE_PRANJA", 0) > 0, "slika_paket": slike.get("PAKET", 0) > 0,
            "opran": any(v == "OPRAN" for v, _p, _h in dnevnik),
            "test": testovi[-1] if testovi else None,
            "pakiran": any(v == "PAKIRAN" for v, _p, _h in dnevnik),
            "lokacija": pretinac}


def dio_kartica(con, dio_id: int) -> dict:
    with con.cursor() as cur:
        cur.execute("""SELECT o.id, o.token, o.status, o.broj_na_dijelu, o.pretinac_adresa, o.cijena, o.razred_jamstva,
                              coalesce(d.naziv_hr, ''), v.marka, v.model, v.generacija
                       FROM otpad_dio o LEFT JOIN dio d ON d.id = o.dio_id
                       LEFT JOIN otpad_vozilo ov ON ov.id = o.otpad_vozilo_id
                       LEFT JOIN vozilo_tip v ON v.id = ov.vozilo_tip_id WHERE o.id=%s""", (dio_id,))
        r = cur.fetchone()
        if r is None:
            raise Greska(404, f"Dio {dio_id} ne postoji.")
        (i, token, status, broj, pretinac, cijena, razred, naziv, marka, model, gen) = r
        cur.execute("SELECT id, vrsta, javna FROM dio_slika WHERE otpad_dio_id=%s ORDER BY id", (dio_id,))
        slike = [{"id": a, "vrsta": b, "javna": c} for a, b, c in cur.fetchall()]
        cur.execute("SELECT vrsta, vrijeme FROM dio_dogadjaj WHERE otpad_dio_id=%s ORDER BY id DESC LIMIT 12", (dio_id,))
        povijest = [{"vrsta": a, "vrijeme": b} for a, b in cur.fetchall()]
        return {"id": i, "token": token, "status": status, "broj": broj, "pretinac": pretinac,
                "naziv": naziv or "Nepoznat dio", "razred_jamstva": razred,
                "cijena_centi": int(round(cijena * 100)) if cijena is not None else None,
                "auto": " ".join(x for x in (marka, model, gen) if x), "slike": slike, "povijest": povijest,
                "checklist": _checklist(cur, dio_id, pretinac)}


def tamni_popis(con) -> dict:
    with con.cursor() as cur:
        cur.execute("""SELECT o.id, o.token, o.status, o.broj_na_dijelu, o.pretinac_adresa, coalesce(d.naziv_hr, 'Nepoznat dio')
                       FROM otpad_dio o LEFT JOIN dio d ON d.id = o.dio_id
                       WHERE o.status = ANY(%s) ORDER BY o.id DESC LIMIT 100""", (list(STATUSI_TAMNI),))
        redovi = cur.fetchall()
        izlaz = []
        for i, token, status, broj, pretinac, naziv in redovi:
            izlaz.append({"id": i, "token": token, "status": status, "broj": broj, "pretinac": pretinac, "naziv": naziv,
                          "checklist": _checklist(cur, i, pretinac)})
        return {"dijelovi": izlaz}


def nadji(con, q: str) -> dict:
    """Jedno polje za sve što skener ili tipkovnica upišu: adresa pretinca, token dijela, stari Code 128 ili broj na dijelu."""
    q = (q or "").strip()
    if len(q) < 2:
        raise Greska(400, "Upiši barem 2 znaka.")
    g = q.upper().replace(" ", "")
    if T.PRETINAC.fullmatch(g):
        return pretinac_sadrzaj(con, g)
    if TOKEN.fullmatch(g):
        with con.cursor() as cur:
            cur.execute("SELECT id FROM otpad_dio WHERE token=%s", (g,))
            r = cur.fetchone()
        if r:
            return {"vrsta": "dio", "dio": dio_kartica(con, r[0])}
    i = T.po_aliasu(con, q)
    if i:
        return {"vrsta": "dio", "dio": dio_kartica(con, i)}
    with con.cursor() as cur:
        cur.execute("""SELECT o.id FROM otpad_dio o WHERE o.broj_norm = norm_broj(%s) AND o.status <> 'SKART' ORDER BY o.id DESC LIMIT 20""", (q,))
        ids = [r[0] for r in cur.fetchall()]
    if ids:
        return {"vrsta": "dijelovi", "dijelovi": [dio_kartica(con, i) for i in ids]}
    return {"vrsta": "nista"}


def predradnja(con, dio_id: int, p: dict) -> dict:
    vrsta = str(p.get("vrsta") or "").upper()
    podaci = {}
    if vrsta == "TESTIRAN":
        podaci["stanje"] = str(p.get("stanje") or "").upper()
        if p.get("napomena"):
            podaci["napomena"] = str(p["napomena"]).strip()[:200]
    elif vrsta == "PAKIRAN":
        dim = str(p.get("dimenzije_cm") or "").strip().lower().replace(" ", "")
        if not re.fullmatch(r"\d{1,3}x\d{1,3}x\d{1,3}", dim):
            raise Greska(400, "Dimenzije upiši kao duljina x širina x visina u cm, npr. 30x20x15.")
        try:
            tez = int(str(p.get("tezina_g")).strip())
        except (TypeError, ValueError):
            raise Greska(400, "Težina u gramima mora biti broj, npr. 3200.")
        if not 0 < tez <= 500_000:
            raise Greska(400, "Težina mora biti između 1 i 500000 g.")
        podaci = {"dimenzije_cm": dim, "tezina_g": tez}
    elif vrsta != "OPRAN":
        raise Greska(400, "Nepoznata predradnja.")
    r = _uvijek(T.predradnja, con, dio_id, vrsta, **podaci)
    return {"status": r["status"], "poruka": {"OPRAN": "Označeno kao oprano.", "PAKIRAN": "Pakiranje je upisano.",
            "TESTIRAN": "Test je upisan." + (" Dio je otišao u škart." if r["status"] == "SKART" else "")}[vrsta]}


def spremi_u_pretinac(con, dio_id: int, p: dict) -> dict:
    adresa = str(p.get("adresa") or "").strip().upper()
    if not T.PRETINAC.fullmatch(adresa):
        raise Greska(400, "Odaberi pretinac (oblik R03-P2-04).")
    r = _uvijek(T.spremi, con, dio_id, adresa)
    return {"status": r["status"], "poruka": f"Dio je u pretincu {adresa}."}


def slika_spremi(con, dio_id: int, vrsta: str, sadrzaj: bytes, spremnik) -> dict:
    if spremnik is None:
        raise Greska(503, "Spremnik slika nije podešen na poslužitelju. Javi Ivanu; podaci nisu spremljeni.")
    if vrsta not in VRSTE_SLIKA:
        raise Greska(400, "Nepoznata vrsta slike.")
    if not sadrzaj:
        raise Greska(400, "Slika je prazna.")
    if tip_slike(sadrzaj) is None:
        raise Greska(415, "Slika mora biti JPEG, PNG ili WebP.")
    try:
        sha, ref = spremnik.spremi(sadrzaj)
    except SpremnikGreska as e:
        raise Greska(502, str(e))
    try:
        r = _uvijek(T.zabiljezi_sliku, con, dio_id, vrsta, sha, ref)
    except Greska:
        raise
    except Exception as e:                                                  # noqa: BLE001
        if "dio_slika_otpad_dio_id_sha256_key" in str(e):
            raise Greska(409, "Ta je slika već dodana ovom dijelu.")
        raise
    return {"slika": r["slika"], "poruka": "Slika je spremljena."}


def slika_citaj(con, slika_id: int, spremnik) -> tuple[bytes, str]:
    if spremnik is None:
        raise Greska(503, "Spremnik slika nije podešen.")
    with con.cursor() as cur:
        cur.execute("SELECT ref FROM dio_slika WHERE id=%s", (slika_id,))
        r = cur.fetchone()
    try:
        b = spremnik.dohvati(r[0]) if r else None
    except SpremnikGreska as e:
        raise Greska(502, str(e))
    if b is None:
        raise Greska(404, "Slika ne postoji.")
    return b, tip_slike(b) or "application/octet-stream"


def u_prodaju(con, dio_id: int, p: dict) -> dict:
    try:
        cijena = int(round(float(str(p.get("cijena")).replace(",", ".")) * 100))
    except (TypeError, ValueError):
        raise Greska(400, "Cijena nije ispravan broj. Upiši npr. 45 ili 45,50.")
    razred = str(p.get("razred_jamstva") or "")
    javne = [int(x) for x in (p.get("javne_slike") or []) if str(x).isdigit()]
    razlozi = T.provjere_vrata(con, dio_id, cijena, razred, javne)
    if razlozi:
        raise Greska(409, "Dio još ne smije u prodaju.", razlozi=razlozi)
    r = _uvijek(T.stavi_u_prodaju, con, dio_id, cijena, razred, javne)
    return {"token": r["token"], "poruka": "Dio je u prodaji. Atom svjetla i oglas čekaju u izlaznom redu."}


def obilazak(con, adresa: str, p: dict) -> dict:
    if not T.PRETINAC.fullmatch(adresa):
        raise Greska(400, "Neispravna adresa pretinca (oblik R03-P2-04).")
    try:
        nadjeni = [int(x) for x in (p.get("nadjeni") or [])]
    except (TypeError, ValueError):
        raise Greska(400, "Neispravan popis pronađenih dijelova.")
    viska = [str(x) for x in (p.get("viska") or [])][:20]
    if any(not TOKEN.fullmatch(t.strip().upper()) for t in viska if t.strip()):
        raise Greska(400, "Oznaka dijela ima 16 znakova (slova A–Z i brojke 2–7).")
    r = _uvijek(T.obilazak, con, adresa, nadjeni, viska)
    dijelovi = len(r["nadjeno"]) + len(r["nedostaje"])
    if not r["nedostaje"] and not r["viska"] and not r["nepoznato"]:
        poruka = f"Sve je na mjestu ({dijelovi})." if dijelovi else "Pretinac je prazan, kako i treba biti."
    else:
        dijelovi_txt = []
        if r["nedostaje"]:
            dijelovi_txt.append(f"nedostaje {len(r['nedostaje'])}")
        if r["viska"]:
            dijelovi_txt.append(f"višak {len(r['viska'])} (vodi se u drugom pretincu)")
        if r["nepoznato"]:
            dijelovi_txt.append(f"nepoznata oznaka {len(r['nepoznato'])}")
        poruka = "Obilazak upisan: " + ", ".join(dijelovi_txt) + "."
    return {**r, "poruka": poruka}
