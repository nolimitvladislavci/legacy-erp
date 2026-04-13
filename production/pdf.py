"""
production/pdf.py — PDF generacija za radne naloge
WeasyPrint ako je dostupan, fallback na HTML-to-response.
"""

import logging

from django.http import HttpResponse
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def generate_order_pdf(order, request=None):
    """
    Generiraj PDF za radni nalog.
    Pokušaj WeasyPrint, fallback na HTML printable.
    """
    context = {
        "order": order,
        "bom": order.bom,
        "lines": order.bom.lines.select_related("item").order_by("sort_order"),
        "steps": order.steps.all().order_by("step_number"),
        "qc_checks": order.quality_checks.all().order_by("-checked_at"),
        "logs": order.logs.all().order_by("-created_at")[:20],
        "requirements": order.calculate_material_requirements(),
        "company": order.company,
    }

    html = render_to_string("production/order_pdf.html", context, request=request)

    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=html, base_url="https://limit-connect.com").write_pdf()
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="RN-{order.order_number}.pdf"'
        return response
    except ImportError:
        logger.info("WeasyPrint not available, returning HTML")
        response = HttpResponse(html, content_type="text/html")
        return response
    except ImportError as e:
        logger.error(f"PDF generation error: {e}")
        response = HttpResponse(html, content_type="text/html")
        return response
