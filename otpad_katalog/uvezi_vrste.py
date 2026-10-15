#!/usr/bin/env python3
"""vrste_dijelova.tsv -> SQL za tablicu dio (popis vrsta dijelova za automatsko dovršavanje naziva u ekranu).

Izvor: auto-parts-db 3.0.0 `parts.js` (MIT), 1530 zapisa (ruski nazivi, bez kataloških brojeva, uz potrošnu robu),
ručno očišćeno i prevedeno u 295 hrvatskih naziva vrsta dijelova (strana lijevo/desno se upisuje u nazivu pri unosu).
NE sadrži kataloške brojeve: dio_broj ostaje prazan. Idempotentno: ne dira nazive koji već postoje.
Pokretanje: python3 -I uvezi_vrste.py [--parts parts.json]   (provjerava da svaki slug postoji u parts.js ako je zadan)
"""
import json
import sys
from pathlib import Path

TSV = Path(__file__).with_name("vrste_dijelova.tsv")


def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main() -> int:
    rows = [l.rstrip("\n").split("\t") for l in TSV.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    for r in rows:
        if len(r) != 3 or not all(r):
            print("PAD neispravan redak:", r, file=sys.stderr); return 1
    if len({r[1] for r in rows}) != len(rows):
        print("PAD dupli nazivi", file=sys.stderr); return 1
    if "--parts" in sys.argv:
        slugovi = {p["slug"] for p in json.loads(Path(sys.argv[sys.argv.index("--parts") + 1]).read_text(encoding="utf-8"))}
        nema = [r[0] for r in rows if r[0] not in slugovi]
        if nema:
            print("PAD slug ne postoji u parts.js:", nema, file=sys.stderr); return 1
    print("-- generirano iz vrste_dijelova.tsv (auto-parts-db parts.js, MIT, očišćeno i prevedeno); bez kataloških brojeva")
    print("BEGIN;")
    print("INSERT INTO izvor (naziv, verzija, licenca, napomena) VALUES ('auto-parts-db parts.js (vrste dijelova)', '3.0.0', 'MIT', "
          "'Samo nazivi vrsta dijelova, bez kataloških brojeva; očišćeno i prevedeno') ON CONFLICT (naziv) DO NOTHING;")
    print("INSERT INTO dio (naziv_hr, kategorija)")
    print("SELECT v.n, v.k FROM (VALUES")
    print(",\n".join(f"  ({q(r[1])}, {q(r[2])})" for r in rows))
    print(") AS v(n, k) WHERE NOT EXISTS (SELECT 1 FROM dio d WHERE d.naziv_hr = v.n);")
    print("COMMIT;")
    return 0


if __name__ == "__main__":
    sys.exit(main())
