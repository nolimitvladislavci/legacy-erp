"""
rental/evisitor.py — eVisitor XML export za prijavu gostiju

Generira XML prema HTZ formatu. Iznajmljivač ga uploadira na eVisitor.hr.
Buduće: direktni API poziv kad dobijemo ključ.
"""
import xml.etree.ElementTree as ET
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


def build_evisitor_xml(booking, guests=None) -> str:
    """
    Generira eVisitor XML za prijavu dolaska gostiju.

    Returns: XML string spreman za upload na eVisitor.hr
    """
    if guests is None:
        guests = booking.guests.all()

    root = ET.Element('eVisitorImport')
    root.set('version', '1.0')

    for guest in guests:
        prijava = ET.SubElement(root, 'Prijava')

        ET.SubElement(prijava, 'VrstaPrijave').text = 'DOLAZAK'
        ET.SubElement(prijava, 'NazivObjekta').text = booking.rental_property.name
        ET.SubElement(prijava, 'DatumDolaska').text = booking.check_in.strftime('%Y-%m-%d')
        ET.SubElement(prijava, 'DatumOdlaska').text = booking.check_out.strftime('%Y-%m-%d')

        ET.SubElement(prijava, 'Ime').text = guest.first_name
        ET.SubElement(prijava, 'Prezime').text = guest.last_name
        ET.SubElement(prijava, 'DatumRodenja').text = (
            guest.date_of_birth.strftime('%Y-%m-%d') if guest.date_of_birth else ''
        )
        ET.SubElement(prijava, 'Spol').text = guest.sex or 'M'
        ET.SubElement(prijava, 'Drzavljanstvo').text = guest.nationality or 'HRV'
        ET.SubElement(prijava, 'VrstaDokumenta').text = guest.document_type or 'putovnica'
        ET.SubElement(prijava, 'BrojDokumenta').text = guest.document_number or ''
        ET.SubElement(prijava, 'DrzavaIzdavanjaDokumenta').text = (
            guest.document_country or guest.nationality or 'HRV'
        )
        ET.SubElement(prijava, 'DrzavaBoravistaStanovnistva').text = (
            guest.residence_country or guest.nationality or 'HRV'
        )

    ET.indent(root, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')


def build_departure_xml(booking, guests=None) -> str:
    """Generira eVisitor XML za odjavu odlaska gostiju."""
    if guests is None:
        guests = booking.guests.all()

    root = ET.Element('eVisitorImport')
    root.set('version', '1.0')

    for guest in guests:
        odjava = ET.SubElement(root, 'Prijava')
        ET.SubElement(odjava, 'VrstaPrijave').text = 'ODLAZAK'
        ET.SubElement(odjava, 'NazivObjekta').text = booking.rental_property.name
        ET.SubElement(odjava, 'DatumDolaska').text = booking.check_in.strftime('%Y-%m-%d')
        ET.SubElement(odjava, 'DatumOdlaska').text = (
            booking.actual_check_out.strftime('%Y-%m-%d')
            if booking.actual_check_out
            else booking.check_out.strftime('%Y-%m-%d')
        )
        ET.SubElement(odjava, 'Ime').text = guest.first_name
        ET.SubElement(odjava, 'Prezime').text = guest.last_name
        ET.SubElement(odjava, 'BrojDokumenta').text = guest.document_number or ''

    ET.indent(root, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')
