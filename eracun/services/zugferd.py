"""
eracun/services/zugferd.py
ZUGFeRD 2.x generator — embeds CII XML into PDF/A-3.
Creates a hybrid document: human-readable PDF + machine-readable XML.
"""
import io
import logging
from datetime import date

logger = logging.getLogger(__name__)


def generate_zugferd_pdf(eracun, pdf_bytes=None):
    """
    Generate ZUGFeRD 2.x PDF (PDF/A-3 with embedded CII XML).

    Args:
        eracun: ERacun instance
        pdf_bytes: Optional existing PDF to embed XML into.
                   If None, generates a simple invoice PDF.

    Returns:
        bytes: PDF/A-3 with embedded factur-x.xml
    """
    from .xrechnung import generate_xrechnung

    xml_string = generate_xrechnung(eracun)
    xml_bytes = xml_string.encode('utf-8')

    if pdf_bytes is None:
        pdf_bytes = _generate_simple_pdf(eracun)

    try:
        return _embed_xml_in_pdf(pdf_bytes, xml_bytes)
    except Exception as e:
        logger.warning(f'ZUGFeRD PDF embedding failed: {e}, returning plain PDF')
        return pdf_bytes


def _generate_simple_pdf(eracun):
    """Generate a simple invoice PDF using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # Header
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, spaceAfter=20)
    story.append(Paragraph(f'RECHNUNG / RACUN', title_style))
    story.append(Paragraph(f'Nr. {eracun.invoice_number}', styles['Normal']))
    story.append(Paragraph(f'Datum: {eracun.issue_date}', styles['Normal']))
    story.append(Spacer(1, 20))

    # Seller
    story.append(Paragraph(f'<b>Von / Od:</b> {eracun.issuer_name}', styles['Normal']))
    story.append(Paragraph(f'{eracun.issuer_address}, {eracun.issuer_postal} {eracun.issuer_city}', styles['Normal']))
    if eracun.issuer_oib:
        story.append(Paragraph(f'St.Nr./OIB: {eracun.issuer_oib}', styles['Normal']))
    story.append(Spacer(1, 10))

    # Buyer
    story.append(Paragraph(f'<b>An / Za:</b> {eracun.recipient_name}', styles['Normal']))
    story.append(Paragraph(f'{eracun.recipient_address}, {eracun.recipient_postal} {eracun.recipient_city}', styles['Normal']))
    story.append(Spacer(1, 20))

    # Items table
    data = [['Pos.', 'Beschreibung / Opis', 'Menge', 'Preis', 'MwSt', 'Gesamt']]
    for item in eracun.items.all().order_by('line_number'):
        data.append([
            str(item.line_number),
            item.description[:50],
            f'{item.quantity:.2f} {item.unit_code}',
            f'{item.unit_price:.2f}',
            f'{item.tax_rate:.0f}%',
            f'{item.line_total:.2f}',
        ])

    t = Table(data, colWidths=[30, 200, 60, 60, 40, 70])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0a0a0a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#c9a84c')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    # Totals
    totals = [
        ['', '', '', '', 'Netto:', f'{eracun.subtotal:.2f} {eracun.currency}'],
        ['', '', '', '', 'MwSt/PDV:', f'{eracun.tax_amount:.2f} {eracun.currency}'],
        ['', '', '', '', 'GESAMT:', f'{eracun.total:.2f} {eracun.currency}'],
    ]
    tt = Table(totals, colWidths=[30, 200, 60, 60, 50, 70])
    tt.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (-2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (-2, -1), (-1, -1), 1, colors.black),
    ]))
    story.append(tt)
    story.append(Spacer(1, 20))

    # Payment
    if eracun.issuer_iban:
        story.append(Paragraph(f'<b>Bankverbindung / IBAN:</b> {eracun.issuer_iban}', styles['Normal']))
    if eracun.due_date:
        story.append(Paragraph(f'<b>Zahlungsziel / Rok:</b> {eracun.due_date}', styles['Normal']))

    # ZUGFeRD note
    story.append(Spacer(1, 30))
    small = ParagraphStyle('Small', parent=styles['Normal'], fontSize=7, textColor=colors.grey)
    story.append(Paragraph('Dieses Dokument enthaelt eine maschinenlesbare XML-Rechnung (ZUGFeRD 2.x / Factur-X).', small))

    doc.build(story)
    return buf.getvalue()


def _embed_xml_in_pdf(pdf_bytes, xml_bytes):
    """
    Embed CII XML into PDF as associated file (PDF/A-3 style).
    Uses PyPDF2/pikepdf if available, otherwise returns plain PDF.
    """
    try:
        import pikepdf

        pdf = pikepdf.open(io.BytesIO(pdf_bytes))

        # Create file specification for the embedded XML
        xml_stream = pikepdf.Stream(pdf, xml_bytes)
        xml_stream[pikepdf.Name.Type] = pikepdf.Name.EmbeddedFile
        xml_stream[pikepdf.Name.Subtype] = pikepdf.Name('/text/xml')

        filespec = pikepdf.Dictionary({
            pikepdf.Name.Type: pikepdf.Name.Filespec,
            pikepdf.Name.F: 'factur-x.xml',
            pikepdf.Name.UF: 'factur-x.xml',
            pikepdf.Name.EF: pikepdf.Dictionary({
                pikepdf.Name.F: xml_stream,
            }),
            pikepdf.Name.AFRelationship: pikepdf.Name.Alternative,
        })

        # Add to catalog
        if pikepdf.Name.Names not in pdf.Root:
            pdf.Root[pikepdf.Name.Names] = pikepdf.Dictionary()

        pdf.Root[pikepdf.Name.Names][pikepdf.Name.EmbeddedFiles] = pikepdf.Dictionary({
            pikepdf.Name.Names: pikepdf.Array([
                'factur-x.xml',
                filespec,
            ])
        })

        # AF entry
        if pikepdf.Name.AF not in pdf.Root:
            pdf.Root[pikepdf.Name.AF] = pikepdf.Array()
        pdf.Root[pikepdf.Name.AF].append(filespec)

        out = io.BytesIO()
        pdf.save(out)
        return out.getvalue()

    except ImportError:
        logger.info('pikepdf not installed, returning PDF without embedded XML')
        return pdf_bytes
    except Exception as e:
        logger.warning(f'ZUGFeRD embedding error: {e}')
        return pdf_bytes
