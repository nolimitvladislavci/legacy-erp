"""
ZAMP obrazac za prijavu izvođenih glazbenih djela.
Ne koristi ZAMP API (ne postoji). Generira strukturirani XML.
Rezultat: XML koji organizator šalje na prijavadj@zamp.hr
"""

from datetime import date
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring


def generiraj_zamp_obrazac(company, dogadjaj, set_lista: list) -> bytes:
    """
    set_lista = [
        {"naslov": "Lijepa naša", "izvodjac": "KUD Dukat", "autor": "Josip Runjanin",
         "trajanje_min": 4, "broj_izvedbi": 1, "vrsta": "folk"},
        ...
    ]
    Vraća UTF-8 XML bytes.
    """
    root = Element("ZAMPPrijava")
    root.set("verzija", "1.0")
    root.set("datum", date.today().isoformat())

    org = SubElement(root, "Organizator")
    SubElement(org, "Naziv").text = company.name
    SubElement(org, "OIB").text = company.oib or ""
    SubElement(org, "Adresa").text = getattr(company, "address", "") or ""

    ev = SubElement(root, "Dogadjaj")
    SubElement(ev, "Naziv").text = dogadjaj.name if dogadjaj else "Nastup"
    SubElement(ev, "Datum").text = (
        dogadjaj.date.isoformat()
        if dogadjaj and hasattr(dogadjaj, "date") and dogadjaj.date
        else date.today().isoformat()
    )
    SubElement(ev, "Lokacija").text = (getattr(dogadjaj, "location", "") if dogadjaj else "") or ""

    djela = SubElement(root, "IzvodjenaDjela")
    for i, stavka in enumerate(set_lista, 1):
        djelo = SubElement(djela, "Djelo")
        djelo.set("rbr", str(i))
        SubElement(djelo, "Naslov").text = stavka.get("naslov", "")
        SubElement(djelo, "Izvodjac").text = stavka.get("izvodjac", "")
        SubElement(djelo, "Autor").text = stavka.get("autor", "")
        SubElement(djelo, "TrajanjeSekundi").text = str(stavka.get("trajanje_min", 0) * 60)
        SubElement(djelo, "BrojIzvedbi").text = str(stavka.get("broj_izvedbi", 1))
        SubElement(djelo, "VrstaDjela").text = stavka.get("vrsta", "glazba")

    raw = tostring(root, encoding="utf-8", xml_declaration=True)
    return minidom.parseString(raw).toprettyxml(indent="  ", encoding="utf-8")
