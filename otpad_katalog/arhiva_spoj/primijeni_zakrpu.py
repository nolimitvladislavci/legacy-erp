#!/usr/bin/env python3
"""Zakrpa za api/arhiva_core.py (EU, produkcija): za app_id "kelava-dijelovi" preskoči obradu u pozadini (OCR + dva AI poziva).

NIJE PRIMIJENJENA. Primjena je A4 (produkcija) i traži Ivanov `DA primijeni-zakrpu-bez-ai eu-genesis` + INTENT atom.
Skripta radi ciljanu zamjenu (ne prepisuje datoteku): svaki sidreni niz mora postojati TOČNO jednom, pravi .bak.<UTC>,
nakon izmjene py_compile, ispisuje sha256 prije/poslije za RAČUN atom, i ispisuje rollback naredbu.
Korištenje:  python3 primijeni_zakrpu.py /var/www/genesis/api/arhiva_core.py [--suho]     (--suho: ništa ne piše)
Poslije primjene treba restart servisa `genesis` (A4) i mjerenje (vidi README.md).
"""
import hashlib
import py_compile
import shutil
import sys
import time

SIDRO_1 = 'router = APIRouter(prefix="/api/v1/arhiva-core", tags=["arhiva_core"])\n'
NOVO_1 = SIDRO_1 + '''
# Fotografije dijelova (Kelava) nisu knjigovodstveni dokumenti, a AI obrada košta (limit troška = 0 dok nije upisan u lanac):
# za ove app_id upload ne pokreće obradu u pozadini. Popis: env ARHIVA_BEZ_AI_APP_ID (zarezom odvojeno), zadano kelava-dijelovi.
_APP_ID_BEZ_AI = frozenset(x for x in __import__("os").environ.get("ARHIVA_BEZ_AI_APP_ID", "kelava-dijelovi").split(",") if x)
'''
SIDRO_2 = '    background_tasks.add_task(_obradi_u_pozadini, dokument.weise3_id)\n    return _serialize(dokument)\n'
NOVO_2 = ('    if app_id not in _APP_ID_BEZ_AI:\n'
          '        background_tasks.add_task(_obradi_u_pozadini, dokument.weise3_id)\n'
          '    return _serialize(dokument)\n')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 2
    put, suho = sys.argv[1], "--suho" in sys.argv
    original = open(put, "rb").read()
    tekst = original.decode("utf-8")
    if "_APP_ID_BEZ_AI" in tekst:
        print("VEĆ PRIMIJENJENO (nađen _APP_ID_BEZ_AI), ništa ne radim"); return 0
    for ime, sidro in (("SIDRO_1", SIDRO_1), ("SIDRO_2", SIDRO_2)):
        n = tekst.count(sidro)
        if n != 1:
            print(f"STOP: {ime} nađen {n} puta (treba točno 1). Datoteka se razlikuje od pročitane; ništa nije mijenjano."); return 1
    novo = tekst.replace(SIDRO_1, NOVO_1, 1).replace(SIDRO_2, NOVO_2, 1)
    print("sha256 prije :", sha(original))
    print("sha256 poslije:", sha(novo.encode("utf-8")))
    if suho:
        print("SUHO: ništa nije upisano"); return 0
    bak = f"{put}.bak.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    shutil.copy2(put, bak)
    open(put, "w", encoding="utf-8").write(novo)
    try:
        py_compile.compile(put, doraise=True)
    except py_compile.PyCompileError as e:
        shutil.copy2(bak, put)
        print(f"py_compile pao, vraćeno iz {bak}: {e}"); return 1
    print(f"OK. rollback: cp -p {bak} {put}  (pa restart servisa)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
