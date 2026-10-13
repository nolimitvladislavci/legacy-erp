#!/usr/bin/env python3
"""Testovi validatora VIN-a (vin.py). Kriteriji upisani prije pokretanja; svaki red je jedan zaseban slučaj.
Pokretanje:  python3 -I test_vin.py   (DB dio traži runuser -u postgres; preskače se bez njega kao NEPOZNATO)
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vin as V  # noqa: E402

PASS = FAIL = 0


def ok(naziv, uvjet, detalj=""):
    global PASS, FAIL
    if uvjet:
        PASS += 1; print(f"PROŠLO  {naziv}")
    else:
        FAIL += 1; print(f"PALO    {naziv} | {detalj}")


NA = "1M8GDM9AXKP042788"                    # standardni primjer s kontrolnom znamenkom X
EU = "WVWZZZ1JZ3W386752"                    # europski oblik, bez obveze kontrolne znamenke

# sloj 1: oblik i kontrolna znamenka
ok("NA VIN s ispravnom kontrolnom znamenkom → DRZI", V.provjeri(NA).stanje == "DRZI" and V.provjeri(NA).kontrolna == "DRZI", str(V.provjeri(NA)))
ok("NA VIN s jednim promijenjenim znakom → PAD (kontrolna)", V.provjeri("1M8GDM9AXKP042789").stanje == "PAD")
ok("1111…1 (17 jedinica) je valjan NA VIN", V.provjeri("1" * 17).stanje == "DRZI")
ok("EU VIN → DRZI, kontrolna NE_PRIMJENJIVO", V.provjeri(EU).stanje == "DRZI" and V.provjeri(EU).kontrolna == "NE_PRIMJENJIVO")
ok("mala slova, razmaci i crtice se normaliziraju", V.provjeri("wvw zzz-1jz 3w386752").stanje == "DRZI")
ok("16 znakova → NEPOZNATO (nepotpuno)", V.provjeri(EU[:-1]).stanje == "NEPOZNATO")
ok("18 znakova → NEPOZNATO", V.provjeri(EU + "1").stanje == "NEPOZNATO")
ok("prazno → NEPOZNATO", V.provjeri("").stanje == "NEPOZNATO" and V.provjeri(None).stanje == "NEPOZNATO")
ok("nečitki znak '?' → NEPOZNATO, nikad PAD", V.provjeri("WVWZZZ1JZ3W38675?").stanje == "NEPOZNATO")
ok("slovo O u VIN-u → PAD", V.provjeri("WVWZZZ1JZ3WO86752").stanje == "PAD")
ok("slova I i Q → PAD", V.provjeri("WVWZZZ1JZ3WI86752").stanje == "PAD" and V.provjeri("WVWZZZ1JZ3WQ86752").stanje == "PAD")
ok("prijedlog za 'O' je 0, ali samo kao prijedlog", V.prijedlozi("WVWZZZ1JZ3WO86752") == ["WVWZZZ1JZ3W086752"], str(V.prijedlozi("WVWZZZ1JZ3WO86752")))
ok("prijedlozi ne dira ispravan VIN", V.prijedlozi(EU) == [])
ok("provjeri() NE ispravlja sam (O ostaje PAD)", V.provjeri("WVWZZZ1JZ3WO86752").vin == "WVWZZZ1JZ3WO86752")

# sloj 2: dva čitanja
ok("dva ista čitanja → DRZI", V.uskladi_citanja(EU, EU.lower()).stanje == "DRZI")
r = V.uskladi_citanja(EU, "WVWZZZ1JZ3W386753")
ok("razlika u jednom znaku → NEPOZNATO s mjestom razlike", r.stanje == "NEPOZNATO" and r.detalji.get("razlike") == [17], str(r))
ok("jedno čitanje nevaljano → NEPOZNATO", V.uskladi_citanja(EU, "WVWZZZ1JZ3W3867").stanje == "NEPOZNATO")

# sloj 3: godište i marka
ok("godina iz 10. znaka: '3' → 2003 ili 2033", V.godine_iz_vin(EU) == [2003, 2033], str(V.godine_iz_vin(EU)))
ok("NA VIN 7. znak '9' (broj) → 1989", V.godine_iz_vin(NA) == [1989], str(V.godine_iz_vin(NA)))
ok("godište 2003 odgovara → DRZI", V.provjeri_godiste(EU, 2003).stanje == "DRZI")
ok("EU: neslaganje godišta je NEPOZNATO, ne PAD", V.provjeri_godiste(EU, 2015).stanje == "NEPOZNATO")
ok("NA: neslaganje godišta je PAD", V.provjeri_godiste(NA, 2019).stanje == "PAD")
ok("godište nije pročitano → NEPOZNATO", V.provjeri_godiste(EU, None).stanje == "NEPOZNATO")
ok("marka: WMI nije u tablici → NEPOZNATO", V.provjeri_marku(EU, "Volkswagen", wmi={}).stanje == "NEPOZNATO")
ok("marka: WMI u tablici i odgovara → DRZI", V.provjeri_marku(EU, "volkswagen", wmi={"WVW": "volkswagen"}).stanje == "DRZI")
ok("marka: WMI ne odgovara marki → NEPOZNATO (nikad PAD)", V.provjeri_marku(EU, "Audi", wmi={"WVW": "volkswagen"}).stanje == "NEPOZNATO")

# sloj 4: potvrda zadnjih 6
ok("potvrda točna (i s malim slovima/razmakom)", V.potvrda_zadnjih_6(EU, "386 752").stanje == "DRZI")
ok("potvrda kriva → PAD", V.potvrda_zadnjih_6(EU, "386753").stanje == "PAD")
ok("potvrda prekratka/prazna → NEPOZNATO", V.potvrda_zadnjih_6(EU, "3867").stanje == "NEPOZNATO" and V.potvrda_zadnjih_6(EU, None).stanje == "NEPOZNATO")

# prihvati: sve zajedno
ok("prihvati: dva čitanja + potvrda → DRZI", V.prihvati(EU, EU, "386752", godina=2003, marka="Volkswagen", wmi={}).stanje == "DRZI")
ok("prihvati: bez potvrde → NIJE DRZI", V.prihvati(EU, EU, None).stanje != "DRZI")
ok("prihvati: kriva potvrda → NIJE DRZI", V.prihvati(EU, EU, "000000").stanje != "DRZI")
ok("prihvati: čitanja se razlikuju → NIJE DRZI", V.prihvati(EU, "WVWZZZ1JZ3W386753", "386752").stanje != "DRZI")
ok("prihvati: NA s krivim godištem → NIJE DRZI", V.prihvati(NA, NA, NA[-6:], godina=2019).stanje != "DRZI")
ok("prihvati: EU s neslaganjem godišta ipak DRZI, ali s upozorenjem", (lambda r: r.stanje == "DRZI" and r.detalji["godiste"] == "NEPOZNATO")(
    V.prihvati(EU, EU, "386752", godina=2015)))

# baza: tvrda provjera znakova
def psql(baza, sql=None, f=None):
    cmd = ["runuser", "-u", "postgres", "--", "psql", "-X", "-q", "-tA", "-v", "ON_ERROR_STOP=1", "-d", baza] + (["-f", f] if f else ["-c", sql])
    return subprocess.run(cmd, capture_output=True, text=True)

AQ = os.path.dirname(os.path.abspath(__file__))
if psql("postgres", "select 1").returncode:
    print("NEPOZNATO baza: PostgreSQL nedostupan, DB provjera preskočena")
else:
    psql("postgres", "DROP DATABASE IF EXISTS otpad_vin_test"); psql("postgres", "CREATE DATABASE otpad_vin_test")
    for f in ("schema.sql", "vin_provjera.sql", "vin_provjera.sql"):
        assert psql("otpad_vin_test", f=os.path.join(AQ, f)).returncode == 0
    ins = lambda v: psql("otpad_vin_test", f"INSERT INTO otpad_vozilo (vin) VALUES ('{v}')")
    ok("DB: ispravan VIN prolazi", ins(EU).returncode == 0)
    ok("DB: VIN sa slovom O odbijen", ins("WVWZZZ1JZ3WO86752").returncode != 0)
    ok("DB: 16 znakova odbijeno", ins(EU[:-1]).returncode != 0)
    ok("DB: duplikat odbijen", ins(EU).returncode != 0)
    ok("DB: mala slova odbijena (VIN se sprema normaliziran)", ins(EU.lower()).returncode != 0)
    psql("postgres", "DROP DATABASE IF EXISTS otpad_vin_test")

print(f"\nUKUPNO {PASS + FAIL} · PROŠLO {PASS} · PALO {FAIL}")
sys.exit(1 if FAIL else 0)
