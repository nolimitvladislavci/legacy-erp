from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
"""
invoicing/services/pdf.py
PDF generation for invoices — placeholder, delegates to existing logic.
"""


def generate_invoice_pdf(invoice):
    """
    Generate PDF for invoice. Returns bytes.
    Delegates to existing template-based PDF rendering.
    """
    # This is a thin wrapper — the actual PDF logic stays in views for now
    # because it depends on Django template rendering (request context).
    # Phase 2 will fully extract this.
    raise NotImplementedError("Use views.generate_pdf() for now — PDF extraction in Phase 2")
