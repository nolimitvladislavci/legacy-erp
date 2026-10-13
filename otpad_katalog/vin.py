"""Validator VIN-a (broj šasije) za otpad_katalog. Samo standardna biblioteka.

Presuđuje kod, ne AI. Trostanje (Ustav §6):
  DRZI       VIN smije u bazu (po ovom sloju)
  NEPOZNATO  čitanje je nepotpuno ili nečitko (prazno, '?', prekratko, predugo); nitko nije kriv, ponovi slikanje
  PAD        potpuno pročitan niz proturječi pravilima (znak I/O/Q, kontrolna znamenka ne štima)
Nikad se ne ispravlja tiho (O→0 i sl.): `prijedlozi` samo nudi radnici, ona potvrđuje.

Slojevi (vidi KELAVA_BRIEF_ZA_FABLE.md):
  1 oblik        `provjeri`
  2 dva čitanja  `uskladi_citanja`
  3 unakrsno     kontrolna znamenka (samo Sj. Amerika, WMI počinje 1–5), `provjeri_godiste`, `provjeri_marku`
  4 čovjek       `potvrda_zadnjih_6`
  5 jedinstvenost je u bazi (UNIQUE + vin_provjera.sql)
`prihvati` spaja slojeve 1, 2 i 4: VIN smije u bazu samo kad su sva tri DRZI.
"""
from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass, field

DOZVOLJENI = re.compile(r"[A-HJ-NPR-Z0-9]{17}")        # bez I, O, Q
_ZABRANJENI = set("IOQ")
_TRANSLIT = {**{str(i): i for i in range(10)},
             **dict(zip("ABCDEFGH", range(1, 9))), **dict(zip("JKLMN", range(1, 6))),
             "P": 7, "R": 9, **dict(zip("STUVWXYZ", (2, 3, 4, 5, 6, 7, 8, 9)))}
_TEZINE = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)
_GODINE = dict(zip("ABCDEFGHJKLMNPRSTVWXY", range(1980, 2001))) | {str(i): 2000 + i for i in range(1, 10)}
WMI_DATOTEKA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wmi.csv")


@dataclass
class Presuda:
    stanje: str                       # DRZI | PAD | NEPOZNATO
    razlog: str = ""
    vin: str = ""                     # normaliziran (velika slova, bez razmaka i crtica)
    kontrolna: str = "NE_PRIMJENJIVO"   # DRZI | PAD | NE_PRIMJENJIVO (europski VIN nema obvezu kontrolne znamenke)
    detalji: dict = field(default_factory=dict)


def normaliziraj(t: str | None) -> str:
    return re.sub(r"[\s\-_.]", "", (t or "")).upper()


def kontrolna_znamenka(vin: str) -> str:
    """Očekivana kontrolna znamenka (9. znak) po 49 CFR 565. Pretpostavlja ispravne znakove."""
    s = sum(_TRANSLIT[c] * w for c, w in zip(vin, _TEZINE)) % 11
    return "X" if s == 10 else str(s)


def sjeverna_amerika(vin: str) -> bool:
    return vin[:1] in "12345"


def provjeri(t: str | None) -> Presuda:
    vin = normaliziraj(t)
    if not vin:
        return Presuda("NEPOZNATO", "prazno čitanje", vin)
    if re.search(r"[^A-Z0-9]", vin):
        return Presuda("NEPOZNATO", "nečitki znakovi u čitanju", vin)
    if len(vin) != 17:
        return Presuda("NEPOZNATO", f"nepotpuno čitanje: {len(vin)} znakova umjesto 17", vin)
    lose = sorted(set(vin) & _ZABRANJENI)
    if lose:
        return Presuda("PAD", f"znak {'/'.join(lose)} ne postoji u VIN-u (vjerojatno pogrešno pročitan)", vin)
    if not DOZVOLJENI.fullmatch(vin):
        return Presuda("PAD", "VIN smije imati samo A–Z (bez I, O, Q) i 0–9", vin)
    if sjeverna_amerika(vin):
        ocekivana = kontrolna_znamenka(vin)
        if vin[8] != ocekivana:
            return Presuda("PAD", f"kontrolna znamenka (9. znak) je {vin[8]}, a treba biti {ocekivana}", vin, "PAD")
        return Presuda("DRZI", "", vin, "DRZI")
    return Presuda("DRZI", "", vin, "NE_PRIMJENJIVO")


def prijedlozi(t: str | None) -> list[str]:
    """Moguće ispravke za radnicu (I→1, O→0, Q→0), svaka mora sama proći `provjeri`. Nikad automatski."""
    vin = normaliziraj(t)
    if len(vin) != 17 or not (set(vin) & _ZABRANJENI):
        return []
    zamjena = {"I": "1", "O": "0", "Q": "0"}
    kandidat = "".join(zamjena.get(c, c) for c in vin)
    return [kandidat] if provjeri(kandidat).stanje == "DRZI" else []


def uskladi_citanja(a: str | None, b: str | None) -> Presuda:
    """Sloj 2: dva neovisna čitanja (OCR + AI). DRZI samo ako su obje ispravna i ISTA znak po znak."""
    pa, pb = provjeri(a), provjeri(b)
    if pa.stanje != "DRZI" or pb.stanje != "DRZI":
        return Presuda("NEPOZNATO", f"čitanja nisu oba valjana (1: {pa.stanje} {pa.razlog}; 2: {pb.stanje} {pb.razlog})",
                       pa.vin if pa.stanje == "DRZI" else pb.vin)
    if pa.vin != pb.vin:
        razlike = [i + 1 for i, (x, y) in enumerate(zip(pa.vin, pb.vin)) if x != y]
        return Presuda("NEPOZNATO", f"čitanja se razlikuju na mjestima {razlike}", "", detalji={"razlike": razlike})
    return Presuda("DRZI", "", pa.vin, pa.kontrolna)


def godine_iz_vin(vin: str) -> list[int]:
    """10. znak = godina modela: dvije mogućnosti u ciklusu od 30 godina. Za Sj. Ameriku 7. znak sužava na jednu."""
    z = vin[9]
    if z not in _GODINE:
        return []
    g = _GODINE[z]
    kandidati = [g, g + 30]
    if sjeverna_amerika(vin):
        kandidati = [k for k in kandidati if (k >= 2010) == vin[6].isalpha()] or kandidati
    return kandidati


def provjeri_godiste(vin: str, godina: int | None) -> Presuda:
    """Sloj 3: 10. znak prema godištu iz knjižice. Izvan Sj. Amerike proizvođač ne mora kodirati godinu,
    pa nepodudaranje tamo je NEPOZNATO (upozorenje), nikad PAD."""
    if godina is None:
        return Presuda("NEPOZNATO", "godište nije pročitano", vin)
    kand = godine_iz_vin(vin)
    if not kand:
        return Presuda("NEPOZNATO", "10. znak ne kodira godinu", vin)
    if godina in kand or (godina - 1) in kand:        # model-godina može biti godinu dana prije/poslije prve registracije
        return Presuda("DRZI", "", vin, detalji={"kandidati": kand})
    stanje = "PAD" if sjeverna_amerika(vin) else "NEPOZNATO"
    return Presuda(stanje, f"10. znak daje godinu {kand}, a knjižica {godina}", vin, detalji={"kandidati": kand})


def ucitaj_wmi(datoteka: str = WMI_DATOTEKA) -> dict[str, str]:
    """wmi.csv: wmi,marka,provjereno. Prazna ili nepostojeća tablica = nijedna marka nije potvrđena."""
    if not os.path.exists(datoteka):
        return {}
    with open(datoteka, newline="", encoding="utf-8") as f:
        return {r["wmi"].strip().upper(): r["marka"].strip().lower() for r in csv.DictReader(f) if r.get("wmi")}


def provjeri_marku(vin: str, marka: str | None, wmi: dict[str, str] | None = None) -> Presuda:
    """Sloj 3: prva tri znaka (WMI) prema marki iz knjižice. DRZI samo kad je WMI u tablici i marka odgovara.
    Nepoznat WMI ili neslaganje daju NEPOZNATO: tablica je mala, pa nikad PAD."""
    tablica = ucitaj_wmi() if wmi is None else wmi
    if not marka:
        return Presuda("NEPOZNATO", "marka nije pročitana", vin)
    ocekivana = tablica.get(vin[:3])
    if ocekivana is None:
        return Presuda("NEPOZNATO", f"WMI {vin[:3]} nije u tablici", vin)
    if ocekivana == marka.strip().lower():
        return Presuda("DRZI", "", vin)
    return Presuda("NEPOZNATO", f"WMI {vin[:3]} je {ocekivana}, a knjižica kaže {marka}", vin)


def potvrda_zadnjih_6(vin: str, upisano: str | None) -> Presuda:
    """Sloj 4: radnica upiše zadnjih 6 znakova VIN-a s knjižice; moraju odgovarati pročitanom VIN-u."""
    u = normaliziraj(upisano)
    if len(u) < 6:
        return Presuda("NEPOZNATO", "potvrda nije upisana (treba 6 znakova)", vin)
    return Presuda("DRZI", "", vin) if u == vin[-6:] else Presuda("PAD", "upisanih 6 znakova ne odgovara pročitanom VIN-u", vin)


def prihvati(citanje_a: str | None, citanje_b: str | None, potvrda6: str | None, *,
             godina: int | None = None, marka: str | None = None, wmi: dict[str, str] | None = None) -> Presuda:
    """Jedina funkcija koju zove ekran. DRZI = VIN smije u bazu. Slojevi 1, 2 i 4 su OBAVEZNI;
    godište i marka idu u `detalji` kao upozorenja (ne blokiraju, jer europski VIN ne mora nositi godinu)."""
    u = uskladi_citanja(citanje_a, citanje_b)
    if u.stanje != "DRZI":
        return u
    p = potvrda_zadnjih_6(u.vin, potvrda6)
    if p.stanje != "DRZI":
        return p
    g, m = provjeri_godiste(u.vin, godina), provjeri_marku(u.vin, marka, wmi)
    if g.stanje == "PAD":                                  # samo Sj. Amerika: proturječje s knjižicom
        return Presuda("NEPOZNATO", g.razlog, u.vin, u.kontrolna, {"godiste": g.stanje, "marka": m.stanje})
    return Presuda("DRZI", "", u.vin, u.kontrolna,
                   {"godiste": g.stanje, "godiste_razlog": g.razlog, "marka": m.stanje, "marka_razlog": m.razlog})
