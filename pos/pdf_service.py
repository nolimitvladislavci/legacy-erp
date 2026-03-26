"""
pos/pdf_service.py
Z-izvještaj PDF generacija.
Koristi xhtml2pdf (već u projektu) umjesto reportlab.
"""
import logging
from io import BytesIO
from django.template.loader import render_to_string

logger = logging.getLogger('pos.pdf')


def generate_z_report_pdf(report):
    """Generira Z-izvještaj PDF. Vraća bytes."""
    html = render_to_string('pos/z_report_pdf.html', {
        'report': report,
        'terminal': report.terminal,
        'company': report.terminal.company if report.terminal else None,
    })

    try:
        from xhtml2pdf import pisa
        buf = BytesIO()
        pisa.CreatePDF(html, dest=buf)
        buf.seek(0)
        return buf.read()
    except ImportError:
        logger.warning('xhtml2pdf not installed — returning HTML')
        return html.encode('utf-8')
