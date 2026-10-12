#!/usr/bin/env python3
"""Pretvara popis vozila iz paketa auto-parts-db (brands.js) u SQL INSERT-e za vozilo_tip.

Datoteka se ČITA KAO TEKST (JSON isječak), ne izvršava se nikakav kod iz paketa.
Izlaz je idempotentan (ON CONFLICT DO NOTHING).

Korištenje:
    python3 uvezi_vozila.py <putanja/do/brands.js> > vozila.sql
"""
import json
import sys


def sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main(putanja: str) -> int:
    tekst = open(putanja, encoding="utf-8").read()
    marke = json.loads(tekst[tekst.index("["): tekst.rindex("]") + 1])

    print("-- generirano iz auto-parts-db (MIT); porijeklo originalnih podataka nije provjereno")
    print("INSERT INTO izvor (naziv, verzija, licenca, napomena) VALUES "
          "('auto-parts-db', '3.0.0', 'MIT', "
          "'Popis marki, modela i generacija. Nema brojeva dijelova.') "
          "ON CONFLICT (naziv) DO NOTHING;")
    print("BEGIN;")
    redaka = 0
    for m in marke:
        for mod in m["models"]:
            for g in mod["generations"]:
                od, do = g["yearFrom"], g["yearTo"]
                print(
                    "INSERT INTO vozilo_tip (marka, model, generacija, godina_od, godina_do, izvor_id) "
                    f"SELECT {sql_str(m['brand'])}, {sql_str(mod['name'])}, {sql_str(g['name'])}, "
                    f"{int(od)}, {'NULL' if do is None else int(do)}, id "
                    "FROM izvor WHERE naziv = 'auto-parts-db' "
                    "ON CONFLICT (marka, model, generacija, godina_od) DO NOTHING;"
                )
                redaka += 1
    print("COMMIT;")
    print(f"-- redaka u ulazu: {redaka}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
