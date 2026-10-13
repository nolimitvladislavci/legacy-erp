#!/usr/bin/env python3
"""Zakrpa za api/arhiva_core.py (EU, produkcija): za app_id "kelava-dijelovi" preskoči obradu u pozadini (OCR + dva AI poziva).

PRIMIJENJENA na EU 2026-10-13 (Ivanov DA), ali ne ovom skriptom: MAX nema exec, pa je ista izmjena napravljena pisanjem cijele datoteke
(vidi FENIX_SOBA.md). Skripta ostaje kao provjerljiv opis izmjene i za DE/ES/NEW. Radi ciljanu zamjenu (ne prepisuje datoteku): svaki sidreni niz mora postojati TOČNO jednom, pravi .bak.<UTC>,
nakon izmjene py_compile, ispisuje sha256 prije/poslije za RAČUN atom, i ispisuje rollback naredbu.
Korištenje:  python3 primijeni_zakrpu.py /var/www/genesis/api/arhiva_core.py [--suho]     (--suho: ništa ne piše)
Poslije primjene treba restart servisa `genesis` (A4) i mjerenje (vidi README.md).
"""
import sys

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


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 2
    sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
    import zakrpa_lib
    return zakrpa_lib.primijeni(sys.argv[1], [("SIDRO_1", SIDRO_1, NOVO_1), ("SIDRO_2", SIDRO_2, NOVO_2)],
                                "_APP_ID_BEZ_AI", suho="--suho" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
