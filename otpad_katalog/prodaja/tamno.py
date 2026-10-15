"""Tamni dio: rođenje dijela, predradnje, stalaža i vrata prema svjetlu (KELAVA_PLAN_K2).

RODEN → PREDRADNJE → NA_STALAZI → [STAVI_U_PRODAJU] → NA_ZALIHI → (prodaja.py: PRODAN → …)
Sve do vrata živi u privatnoj bazi, u istom hash-lancu događaja kao prodaja (dio_dogadjaj). Na vratima ide JEDAN atom
u izlazni red (LANAC_SVJETLO) s Merkle korijenom cijelog privatnog dnevnika, bez sadržaja. Modul ne piše u flotu.

Slika prepoznaje TIP, ne primjerak: primjerak razlikuje donor-vozilo + pretinac + token. Slike su ovdje samo veza i otisak.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets

import psycopg

import prodaja as P
from prodaja import PoslovnaGreska

PRIJE_VRATA = ("RODEN", "PREDRADNJE", "NA_STALAZI")
JAMSTVO_RAZRED = {"POTROSAC_12M": 12, "POTROSAC_24M": 24, "PRAVNA_BEZ": 0}
MIN_SLIKA = 3
PRETINAC = re.compile(r"R(\d{2})-P(\d)-(\d{2})")


# ── Merkle ──────────────────────────────────────────────────────────────────────────────────────
def merkle_koren(hasheve: list[str]) -> str | None:
    """Binarni Merkle nad hex-hashevima (list redoslijedom); neparni zadnji se udvostručuje. Prazno → None."""
    if not hasheve:
        return None
    sloj = [bytes.fromhex(h) for h in hasheve]
    while len(sloj) > 1:
        if len(sloj) % 2:
            sloj.append(sloj[-1])
        sloj = [hashlib.sha256(sloj[i] + sloj[i + 1]).digest() for i in range(0, len(sloj), 2)]
    return sloj[0].hex()


def _dnevnik(cur, dio_id: int) -> list[tuple[str, dict, str]]:
    cur.execute("SELECT vrsta, podaci, hash FROM dio_dogadjaj WHERE otpad_dio_id=%s ORDER BY id", (dio_id,))
    return cur.fetchall()


def _token() -> str:
    return base64.b32encode(secrets.token_bytes(10)).decode()          # 16 znakova A–Z2–7, nasumično


# ── rođenje i predradnje ────────────────────────────────────────────────────────────────────────
def rodi(conn: psycopg.Connection, donor_vozilo_id: int, *, broj_na_dijelu: str | None = None,
         dio_id_tip: int | None = None, prepoznavanje: str = "NEPOZNATO") -> dict:
    """Dio se rađa uvijek, i kad tip nije prepoznat (NEPOZNATO nije razlog da dio ne postoji)."""
    if prepoznavanje not in ("OCR", "SLIKA", "RUCNO", "NEPOZNATO"):
        raise PoslovnaGreska("Način prepoznavanja mora biti OCR, SLIKA, RUCNO ili NEPOZNATO.")
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT 1 FROM otpad_vozilo WHERE id=%s", (donor_vozilo_id,))
        if cur.fetchone() is None:
            raise PoslovnaGreska(f"Donor-vozilo {donor_vozilo_id} ne postoji.")
        token = _token()
        cur.execute("INSERT INTO otpad_dio (otpad_vozilo_id, dio_id, broj_na_dijelu, status, token) "
                    "VALUES (%s,%s,%s,'RODEN',%s) RETURNING id", (donor_vozilo_id, dio_id_tip, broj_na_dijelu, token))
        dio = cur.fetchone()[0]
        _, h = P._dogadjaj(cur, dio, "RODEN", {"token": token, "donor": donor_vozilo_id, "prepoznavanje": prepoznavanje})
    return {"id": dio, "token": token, "hash": h}


def _dopusti(d: dict, stanja: tuple[str, ...]) -> None:
    if d["status"] not in stanja:
        raise PoslovnaGreska(f"Radnja nije moguća u stanju {d['status']}.")


def zabiljezi_sliku(conn: psycopg.Connection, dio_id: int, vrsta: str, sha256: str, ref: str) -> dict:
    """Slika dijela/pranja/paketa/police. Sadržaj ide u ARHIVA 2030, ovdje samo otisak i veza."""
    with conn.transaction(), conn.cursor() as cur:
        d = P._zakljucaj(cur, dio_id)
        _dopusti(d, PRIJE_VRATA + ("NA_ZALIHI",))
        cur.execute("INSERT INTO dio_slika (otpad_dio_id, vrsta, sha256, ref) VALUES (%s,%s,%s,%s) RETURNING id",
                    (dio_id, vrsta, sha256, ref))
        sid = cur.fetchone()[0]
        if d["status"] == "RODEN":
            cur.execute("UPDATE otpad_dio SET status='PREDRADNJE' WHERE id=%s", (dio_id,))
        _, h = P._dogadjaj(cur, dio_id, "SLIKAN", {"slika": sid, "vrsta": vrsta, "sha256": sha256})
    return {"slika": sid, "hash": h}


def _ima_sliku(cur, dio_id: int, vrsta: str) -> bool:
    cur.execute("SELECT count(*) FROM dio_slika WHERE otpad_dio_id=%s AND vrsta=%s", (dio_id, vrsta))
    return cur.fetchone()[0] > 0


def predradnja(conn: psycopg.Connection, dio_id: int, vrsta: str, **podaci) -> dict:
    """OPRAN (traži sliku POSLIJE_PRANJA), TESTIRAN (stanje DRZI|PAD|NEPOZNATO; PAD → SKART),
    PAKIRAN (traži sliku PAKET + dimenzije_cm + tezina_g). Svaka je dokaz u privatnom dnevniku."""
    if vrsta not in ("OPRAN", "TESTIRAN", "PAKIRAN"):
        raise PoslovnaGreska("Predradnja mora biti OPRAN, TESTIRAN ili PAKIRAN.")
    with conn.transaction(), conn.cursor() as cur:
        d = P._zakljucaj(cur, dio_id)
        _dopusti(d, PRIJE_VRATA)
        novi = None
        if vrsta == "OPRAN":
            if not _ima_sliku(cur, dio_id, "POSLIJE_PRANJA"):
                raise PoslovnaGreska("Prvo slikaj dio nakon pranja.")
        elif vrsta == "TESTIRAN":
            if podaci.get("stanje") not in ("DRZI", "PAD", "NEPOZNATO"):
                raise PoslovnaGreska("Test mora imati stanje DRZI, PAD ili NEPOZNATO.")
            if podaci["stanje"] == "PAD":
                novi = "SKART"
        else:
            if not _ima_sliku(cur, dio_id, "PAKET"):
                raise PoslovnaGreska("Prvo slikaj zapakirani dio.")
            if not podaci.get("dimenzije_cm") or int(podaci.get("tezina_g") or 0) <= 0:
                raise PoslovnaGreska("Upiši dimenzije (cm) i težinu (g) paketa.")
        if d["status"] == "RODEN" and novi is None:
            cur.execute("UPDATE otpad_dio SET status='PREDRADNJE' WHERE id=%s", (dio_id,))
        if novi:
            cur.execute("UPDATE otpad_dio SET status=%s WHERE id=%s", (novi, dio_id))
        _, h = P._dogadjaj(cur, dio_id, vrsta, {k: podaci[k] for k in sorted(podaci)})
    return {"hash": h, "status": novi or d["status"]}


# ── stalaža ─────────────────────────────────────────────────────────────────────────────────────
def spremi(conn: psycopg.Connection, dio_id: int, adresa: str) -> dict:
    """Spremanje ili premještanje u pretinac. Zadnja poznata lokacija je uvijek zadnji događaj."""
    with conn.transaction(), conn.cursor() as cur:
        d = P._zakljucaj(cur, dio_id)
        _dopusti(d, PRIJE_VRATA + ("NA_ZALIHI",))
        cur.execute("SELECT 1 FROM pretinac WHERE adresa=%s", (adresa,))
        if cur.fetchone() is None:
            raise PoslovnaGreska(f"Pretinac {adresa} ne postoji.")
        cur.execute("SELECT pretinac_adresa FROM otpad_dio WHERE id=%s", (dio_id,))
        staro = cur.fetchone()[0]
        novi_status = "NA_STALAZI" if d["status"] in ("RODEN", "PREDRADNJE") else d["status"]
        cur.execute("UPDATE otpad_dio SET pretinac_adresa=%s, status=%s WHERE id=%s", (adresa, novi_status, dio_id))
        vrsta = "SPREMLJEN" if staro is None else "PREMJESTEN"
        _, h = P._dogadjaj(cur, dio_id, vrsta, {"od": staro, "na": adresa})
    return {"hash": h, "status": novi_status}


def kljuc_puta(adresa: str) -> tuple[int, int, int]:
    m = PRETINAC.fullmatch(adresa)
    if not m:
        raise PoslovnaGreska(f"Neispravna adresa pretinca: {adresa}")
    return int(m[1]), int(m[2]), int(m[3])


def put_po_hali(adrese: list[str]) -> list[str]:
    """Redoslijed obilaska: regal, polica, pretinac."""
    return sorted(adrese, key=kljuc_puta)


def kartica(conn: psycopg.Connection, dio_id: int) -> dict:
    """Kartica dijela za pretragu: adresa, slika dijela u pretincu (zadnja POLICA), stanje."""
    with conn.cursor() as cur:
        cur.execute("SELECT token, status, pretinac_adresa, broj_na_dijelu FROM otpad_dio WHERE id=%s", (dio_id,))
        r = cur.fetchone()
        if r is None:
            raise PoslovnaGreska(f"Dio {dio_id} ne postoji.")
        cur.execute("SELECT ref FROM dio_slika WHERE otpad_dio_id=%s AND vrsta='POLICA' ORDER BY id DESC LIMIT 1", (dio_id,))
        s = cur.fetchone()
    k = dict(zip(("token", "status", "pretinac", "broj"), r))
    k["slika_police"] = s[0] if s else None
    if k["pretinac"]:
        k["regal"], k["polica"], k["mjesto"] = kljuc_puta(k["pretinac"])
    return k


def obilazak(conn: psycopg.Connection, adresa: str, nadjeni_ids: list[int], viska_tokeni: list[str] | None = None) -> dict:
    """Inventura jednog pretinca: radnica potvrdi što stvarno vidi. Bez naljepnice na dijelu, krivo vraćen dio inače nestaje.
    Svaki očekivani dio dobiva događaj OBILAZAK (nadjen: da/ne). Višak (dio koji je tu, a vodi se drugdje) se NE premješta sam:
    vraća se radnici. -> {nadjeno, nedostaje, viska:[{id, pretinac}], nepoznato:[oznake]}"""
    viska_tokeni = [t.strip().upper() for t in (viska_tokeni or []) if t and t.strip()]
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pretinac WHERE adresa=%s", (adresa,))
        if cur.fetchone() is None:
            raise PoslovnaGreska(f"Pretinac {adresa} ne postoji.")
        cur.execute("""SELECT id FROM otpad_dio WHERE pretinac_adresa=%s AND status IN ('NA_STALAZI', 'NA_ZALIHI', 'REZERVIRAN')
                       ORDER BY id FOR UPDATE""", (adresa,))
        ocekivani = [r[0] for r in cur.fetchall()]
        tudji = sorted(set(nadjeni_ids) - set(ocekivani))
        if tudji:
            raise PoslovnaGreska(f"Dio {tudji[0]} se ne vodi u pretincu {adresa}. Višak upiši preko oznake dijela.")
        nadjeno = [i for i in ocekivani if i in set(nadjeni_ids)]
        nedostaje = [i for i in ocekivani if i not in set(nadjeni_ids)]
        for i in ocekivani:
            _dogadjaj_obilazak(cur, i, adresa, i in set(nadjeni_ids), None)
        viska, nepoznato = [], []
        for t in viska_tokeni:
            cur.execute("SELECT id, pretinac_adresa, status FROM otpad_dio WHERE token=%s FOR UPDATE", (t,))
            r = cur.fetchone()
            if r is None:
                nepoznato.append(t); continue
            if r[0] in ocekivani:
                continue                                           # već je na popisu ovog pretinca
            if r[2] not in ("NA_STALAZI", "NA_ZALIHI", "REZERVIRAN", "RODEN", "PREDRADNJE"):
                nepoznato.append(t); continue                      # prodan/škart ne bi smio biti u pretincu: javi, ne diraj
            _dogadjaj_obilazak(cur, r[0], adresa, True, r[1])
            viska.append({"id": r[0], "pretinac": r[1]})
    return {"nadjeno": nadjeno, "nedostaje": nedostaje, "viska": viska, "nepoznato": nepoznato}


def _dogadjaj_obilazak(cur, dio_id: int, adresa: str, nadjen: bool, vodi_se_u: str | None) -> None:
    P._dogadjaj(cur, dio_id, "OBILAZAK", {"pretinac": adresa, "nadjen": nadjen, "vodi_se_u": vodi_se_u})


def dodaj_alias(conn: psycopg.Connection, alias: str, token: str, vrsta: str = "CODE128") -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO kod_alias (alias, token, vrsta) VALUES (%s,%s,%s)", (alias.strip(), token, vrsta))


def po_aliasu(conn: psycopg.Connection, alias: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT d.id FROM kod_alias a JOIN otpad_dio d ON d.token = a.token WHERE a.alias=%s", (alias.strip(),))
        r = cur.fetchone()
    return r[0] if r else None


# ── vrata prema svjetlu ─────────────────────────────────────────────────────────────────────────
def provjere_vrata(conn: psycopg.Connection, dio_id: int, cijena_centi: int | None, razred: str | None,
                   javne_slike: list[int]) -> list[str]:
    """Popis razloga zašto dio još ne smije van (prazan = smije). Presuđuje stroj, ne radnica."""
    razlozi = []
    with conn.cursor() as cur:
        cur.execute("SELECT status, pretinac_adresa FROM otpad_dio WHERE id=%s", (dio_id,))
        r = cur.fetchone()
        if r is None:
            return [f"Dio {dio_id} ne postoji."]
        status, pretinac = r
        if status != "NA_STALAZI":
            razlozi.append(f"dio mora biti na stalaži (stanje: {status})")
        cur.execute("SELECT count(*) FROM dio_slika WHERE otpad_dio_id=%s AND vrsta='DIO'", (dio_id,))
        if cur.fetchone()[0] < MIN_SLIKA:
            razlozi.append(f"treba najmanje {MIN_SLIKA} slike dijela")
        dnevnik = _dnevnik(cur, dio_id)
        testovi = [p.get("stanje") for v, p, _h in dnevnik if v == "TESTIRAN"]
        if not testovi or testovi[-1] != "DRZI":
            razlozi.append("zadnji test mora biti DRZI")
        if not any(v == "PAKIRAN" for v, _p, _h in dnevnik):
            razlozi.append("pakiranje nije gotovo")
        if not pretinac:
            razlozi.append("lokacija nije poznata")
        if not cijena_centi or cijena_centi <= 0:
            razlozi.append("cijena nije postavljena")
        if razred not in JAMSTVO_RAZRED:
            razlozi.append("razred jamstva nije odabran")
        if not javne_slike:
            razlozi.append("nije odabrana nijedna javna slika")
        else:
            cur.execute("SELECT count(*) FROM dio_slika WHERE otpad_dio_id=%s AND vrsta='DIO' AND id = ANY(%s)",
                        (dio_id, javne_slike))
            if cur.fetchone()[0] != len(set(javne_slike)):
                razlozi.append("javne slike moraju biti slike ovog dijela (vrsta DIO)")
    return razlozi


def stavi_u_prodaju(conn: psycopg.Connection, dio_id: int, cijena_centi: int, razred: str, javne_slike: list[int]) -> dict:
    """STAVI_U_PRODAJU: jedna transakcija. Atom LANAC_SVJETLO nosi Merkle korijen privatnog dnevnika, OGLAS javni dio."""
    with conn.transaction(), conn.cursor() as cur:
        P._zakljucaj(cur, dio_id)
        razlozi = provjere_vrata(conn, dio_id, cijena_centi, razred, javne_slike)
        if razlozi:
            raise PoslovnaGreska("Dio još ne smije u prodaju: " + "; ".join(razlozi) + ".")
        dnevnik = _dnevnik(cur, dio_id)
        koren = merkle_koren([h for _v, _p, h in dnevnik])
        cur.execute("""UPDATE otpad_dio SET status='NA_ZALIHI', cijena=%s, razred_jamstva=%s, jamstvo_mjeseci=%s
                       WHERE id=%s RETURNING token, broj_na_dijelu, coalesce((SELECT k.naziv_hr FROM dio k WHERE k.id = otpad_dio.dio_id), '')""",
                    (cijena_centi / 100, razred, JAMSTVO_RAZRED[razred], dio_id))
        token, broj, naziv = cur.fetchone()
        cur.execute("UPDATE dio_slika SET javna = (id = ANY(%s)) WHERE otpad_dio_id=%s AND vrsta='DIO'", (javne_slike, dio_id))
        did, h = P._dogadjaj(cur, dio_id, "STAVLJEN_U_PRODAJU",
                             {"merkle_koren": koren, "broj_dogadjaja": len(dnevnik), "cijena_centi": cijena_centi,
                              "razred_jamstva": razred})
        P._izlaz(cur, did, "LANAC_SVJETLO", {"token": token, "tip": naziv or None, "broj": broj, "cijena_centi": cijena_centi,
                                              "merkle_koren": koren, "broj_dogadjaja": len(dnevnik)})
        cur.execute("SELECT ref FROM dio_slika WHERE otpad_dio_id=%s AND javna ORDER BY id", (dio_id,))
        P._izlaz(cur, did, "OGLAS", {"token": token, "naziv": naziv or None, "broj": broj, "cijena_centi": cijena_centi,
                                      "jamstvo_mjeseci": JAMSTVO_RAZRED[razred], "slike": [r[0] for r in cur.fetchall()]})
    return {"hash": h, "merkle_koren": koren, "token": token}


def provjeri_svjetlo(conn: psycopg.Connection, dio_id: int) -> tuple[str, str]:
    """Trostanje: korijen u atomu svjetla mora odgovarati dnevniku PRIJE vrata. DRZI | PAD | NEPOZNATO.
    Korijen nad spremljenim hashevima nema smisla ako je sadržaj dnevnika mijenjan, pa se prvo provjerava cijeli lanac."""
    stanje, razlog = P.provjeri_lanac(conn, dio_id)
    if stanje == "PAD":
        return "PAD", f"dnevnik je mijenjan: {razlog}"
    with conn.cursor() as cur:
        dnevnik = _dnevnik(cur, dio_id)
    for i, (v, p, _h) in enumerate(dnevnik):
        if v == "STAVLJEN_U_PRODAJU":
            ocekivan = merkle_koren([h for _v, _p, h in dnevnik[:i]])
            return ("DRZI", "") if p.get("merkle_koren") == ocekivan else ("PAD", "Merkle korijen ne odgovara dnevniku")
    return "NEPOZNATO", "dio nije stavljen u prodaju"


def tjedni_korijen(conn: psycopg.Connection) -> dict:
    """Atom svih TAMNIH dnevnika (zadnji hash svakog dijela prije vrata), bez sadržaja: dokaz da su dijelovi postojali
    i ako se nikad ne prodaju."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("""SELECT d.id, (SELECT hash FROM dio_dogadjaj e WHERE e.otpad_dio_id = d.id ORDER BY e.id DESC LIMIT 1)
                       FROM otpad_dio d WHERE d.status = ANY(%s) ORDER BY d.id""", (list(PRIJE_VRATA),))
        redovi = [r for r in cur.fetchall() if r[1]]
        koren = merkle_koren([h for _i, h in redovi])
        if koren is None:
            return {"stanje": "NEPOZNATO", "razlog": "nema tamnih dijelova"}
        cur.execute("INSERT INTO izlaz_flota (dogadjaj_id, cilj, podaci) VALUES (NULL, 'LANAC_TJEDNI', %s::jsonb)",
                    (json.dumps({"merkle_koren": koren, "broj_dijelova": len(redovi)}, sort_keys=True),))
    return {"stanje": "DRZI", "merkle_koren": koren, "broj_dijelova": len(redovi)}


# ── isti događaj, svi slojevi (H3) ──────────────────────────────────────────────────────────────
def iznos_iz_dogadjaja(conn: psycopg.Connection, dio_id: int) -> tuple[int, str]:
    """Iznos se NE prepisuje: čita se iz događaja PRODAJA. -> (iznos_centi, hash događaja)."""
    with conn.cursor() as cur:
        cur.execute("SELECT podaci, hash FROM dio_dogadjaj WHERE otpad_dio_id=%s AND vrsta='PRODAJA' ORDER BY id DESC LIMIT 1",
                    (dio_id,))
        r = cur.fetchone()
    if r is None:
        raise PoslovnaGreska("Dio nije prodan.")
    return int(r[0]["iznos_centi"]), r[1]
