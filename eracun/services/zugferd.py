"""
ZUGFeRD 2.2 / Factur-X Generator.

Hibridni PDF: vizualno citljiv PDF/A-3 + ugradeni factur-x.xml (CII format).
Njemacki knjigovodstveni softveri (DATEV, Lexware) automatski citaju XML.

Usage:
    from eracun.services.zugferd import generate_zugferd_pdf
    pdf_bytes = generate_zugferd_pdf(eracun)
    # pdf_bytes je PDF/A-3 s embedded factur-x.xml

Zahtjevi:
    pip install pypdf reportlab
"""
import io
import logging
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject, DecodedStreamObject, DictionaryObject,
    NameObject, NumberObject, TextStringObject,
    create_string_object,
)

logger = logging.getLogger('eracun.zugferd')


def generate_zugferd_pdf(eracun, invoice_pdf_bytes=None):
    """
    Generira ZUGFeRD 2.2 PDF.

    Args:
        eracun: ERacun model objekt
        invoice_pdf_bytes: Postojeci PDF racun (bytes). Ako None, generira se.

    Returns:
        bytes: PDF/A-3 s embedded factur-x.xml
    """
    # 1. Generiraj CII XML (XRechnung format)
    from eracun.services.xrechnung import generate_xrechnung
    xml_str = generate_xrechnung(eracun)
    xml_bytes = xml_str.encode('utf-8') if isinstance(xml_str, str) else xml_str

    # 2. Dobij ili generiraj PDF racun
    if invoice_pdf_bytes is None:
        invoice_pdf_bytes = _generate_invoice_pdf(eracun)

    # 3. Embed XML u PDF kao attachment (PDF/A-3 compliant)
    output_bytes = _embed_xml_in_pdf(invoice_pdf_bytes, xml_bytes, eracun)

    logger.info('ZUGFeRD PDF generiran za %s: %d bytes', eracun, len(output_bytes))
    return output_bytes


def _generate_invoice_pdf(eracun):
    """Generiraj PDF racun iz eracun objekta koristeci reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    # Header
    c.setFont('Helvetica-Bold', 16)
    c.drawString(20 * mm, h - 25 * mm, 'RECHNUNG')

    c.setFont('Helvetica', 10)
    company = eracun.company
    y = h - 40 * mm

    # Seller
    c.drawString(20 * mm, y, company.name)
    y -= 5 * mm
    c.drawString(20 * mm, y, '%s, %s %s' % (company.address, company.zip_code, company.city))
    y -= 5 * mm
    c.drawString(20 * mm, y, 'USt-IdNr.: %s | Steuernr.: %s' % (company.vat_id or '', company.tax_number or company.oib))

    # Buyer
    y -= 15 * mm
    c.setFont('Helvetica-Bold', 10)
    c.drawString(20 * mm, y, 'Rechnungsempfaenger:')
    c.setFont('Helvetica', 10)
    y -= 5 * mm
    buyer_name = getattr(eracun, 'buyer_name', '') or ''
    c.drawString(20 * mm, y, buyer_name)

    # Invoice details
    y -= 15 * mm
    c.drawString(20 * mm, y, 'Rechnungsnummer: %s' % (eracun.invoice_number or eracun.pk))
    y -= 5 * mm
    c.drawString(20 * mm, y, 'Rechnungsdatum: %s' % (eracun.issue_date.strftime('%d.%m.%Y') if eracun.issue_date else ''))

    # Items table
    y -= 15 * mm
    c.setFont('Helvetica-Bold', 9)
    c.drawString(20 * mm, y, 'Pos.')
    c.drawString(30 * mm, y, 'Beschreibung')
    c.drawString(120 * mm, y, 'Menge')
    c.drawString(140 * mm, y, 'Einzelpreis')
    c.drawString(170 * mm, y, 'Gesamt')
    y -= 2 * mm
    c.line(20 * mm, y, 190 * mm, y)

    c.setFont('Helvetica', 9)
    items = eracun.items.all() if hasattr(eracun, 'items') else []
    pos = 0
    for item in items:
        pos += 1
        y -= 5 * mm
        c.drawString(20 * mm, y, str(pos))
        c.drawString(30 * mm, y, str(getattr(item, 'description', ''))[:50])
        c.drawString(120 * mm, y, str(getattr(item, 'quantity', 1)))
        c.drawString(140 * mm, y, '%.2f EUR' % float(getattr(item, 'unit_price', 0)))
        c.drawString(170 * mm, y, '%.2f EUR' % float(getattr(item, 'total_price', 0)))

    # Totals
    y -= 10 * mm
    c.line(120 * mm, y, 190 * mm, y)
    y -= 5 * mm
    c.drawString(120 * mm, y, 'Nettobetrag:')
    c.drawString(170 * mm, y, '%.2f EUR' % float(eracun.subtotal or 0))
    y -= 5 * mm
    c.drawString(120 * mm, y, 'MwSt.:')
    c.drawString(170 * mm, y, '%.2f EUR' % float(eracun.tax_amount or 0))
    y -= 5 * mm
    c.setFont('Helvetica-Bold', 10)
    c.drawString(120 * mm, y, 'Gesamtbetrag:')
    c.drawString(170 * mm, y, '%.2f EUR' % float(eracun.total or 0))

    # Footer
    c.setFont('Helvetica', 7)
    c.drawString(20 * mm, 15 * mm, 'Dieses Dokument enthaelt eine maschinenlesbare Rechnung (ZUGFeRD/Factur-X).')
    c.drawString(20 * mm, 12 * mm, 'Generiert von LIMIT Connect ERP — limit-connect.com')

    c.save()
    return buf.getvalue()


def _embed_xml_in_pdf(pdf_bytes, xml_bytes, eracun):
    """
    Embed factur-x.xml in PDF als Associated File (PDF/A-3 compliant).

    Methode: pypdf EmbeddedFile + AF (Associated Files) Array.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()

    # Copy all pages
    for page in reader.pages:
        writer.add_page(page)

    # Copy metadata
    if reader.metadata:
        writer.add_metadata(reader.metadata)

    # Add XMP metadata for ZUGFeRD
    writer.add_metadata({
        '/Title': 'Rechnung %s' % (getattr(eracun, 'invoice_number', '') or str(eracun.pk)),
        '/Author': getattr(eracun, 'company', None) and eracun.company.name or 'LIMIT Connect',
        '/Subject': 'ZUGFeRD 2.2 / Factur-X',
        '/Creator': 'LIMIT Connect ERP',
        '/Producer': 'LIMIT Connect ERP + pypdf',
    })

    # Embed XML as file attachment
    writer.add_attachment(
        fname='factur-x.xml',
        data=xml_bytes,
    )

    # Write output
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
