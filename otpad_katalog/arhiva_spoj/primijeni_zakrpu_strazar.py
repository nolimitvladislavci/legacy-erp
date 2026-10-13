#!/usr/bin/env python3
"""Zakrpa za services/arhiva_core/strazar_ophodnja.py (EU, produkcija): ophodnja stražara preskače app_id "kelava-dijelovi".

NIJE PRIMIJENJENA (A4, traži Ivanov DA). Zašto: ophodnja svakih 10 min uzima 200 NAJNOVIJIH nezapečaćenih dokumenata iz zadnjih 14 dana.
Masovni upload fotografija dijelova izgurao bi stvarne račune iz tog prozora, pa ih stražar ne bi provjeravao.
Popis: env STRAZAR_BEZ_APP_ID (zarezom odvojeno), zadano kelava-dijelovi. Isti postupak i jamstva kao primijeni_zakrpu.py.
Korištenje:  python3 primijeni_zakrpu_strazar.py /var/www/genesis/services/arhiva_core/strazar_ophodnja.py [--suho]
"""
import os
import sys

SIDRO_1 = "from sqlalchemy import select\n"
NOVO_1 = "from sqlalchemy import func, select\n"
SIDRO_2 = 'PO_KRUGU = int(os.getenv("STRAZAR_PO_KRUGU", "200"))\n'
NOVO_2 = SIDRO_2 + '''# Fotografije dijelova (Kelava) nisu papiri za knjigovođu: bez ovoga bi izgurale stvarne račune iz prozora od PO_KRUGU dokumenata.
_APP_ID_BEZ_STRAZARA = tuple(x for x in os.getenv("STRAZAR_BEZ_APP_ID", "kelava-dijelovi").split(",") if x)
'''
SIDRO_3 = '            .where(ArhivaCoreDokumentORM.faza != "zapecaceno")\n'
NOVO_3 = SIDRO_3 + '            .where(func.coalesce(ArhivaCoreDokumentORM.app_id, "").notin_(_APP_ID_BEZ_STRAZARA))\n'


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import zakrpa_lib
    return zakrpa_lib.primijeni(sys.argv[1], [("SIDRO_1", SIDRO_1, NOVO_1), ("SIDRO_2", SIDRO_2, NOVO_2), ("SIDRO_3", SIDRO_3, NOVO_3)],
                                "_APP_ID_BEZ_STRAZARA", suho="--suho" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
