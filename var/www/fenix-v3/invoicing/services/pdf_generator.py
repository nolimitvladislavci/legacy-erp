"""
Fenix V3 — InvoicePDFGenerator
Generira PDF račun iz Invoice model instance.
Podržava 3 globalna formata ispisa × 2 jezika: viskovic / modern / datev × hr / de
"""

import logging

logger = logging.getLogger("fenix.invoicing.pdf")


class InvoicePDFGenerator:
    """
    Generira PDF račun iz Invoice model instance.

    Upotreba:
        gen   = InvoicePDFGenerator(invoice)
        pdf   = gen.generate()    # bytes
        fname = gen.filename      # "Racun_R-2025-0001.pdf"
    """

    def __init__(self, invoice):
        self.invoice = invoice
        self.company = invoice.company
        self.items = list(invoice.items.filter(is_deleted=False).order_by("sort_order"))

    @property
    def lang(self) -> str:
        country = (getattr(self.company, "country", None) or "HR").upper()
        return "de" if country in ("DE", "AT", "CH") else "hr"

    @property
    def filename(self) -> str:
        num = self.invoice.number.replace("/", "-").replace(" ", "_")
        return f"Racun_{num}.pdf"

    @property
    def _template(self) -> str:
        from core.pdf_templates import get_invoice_template

        return get_invoice_template(self.company, lang=self.lang)

    def generate(self) -> bytes:
        from django.template.loader import render_to_string
        from django.conf import settings
        from collections import defaultdict
        from decimal import Decimal
        import weasyprint

        tax_breakdown = defaultdict(lambda: {"taxable": Decimal("0"), "tax": Decimal("0")})
        for item in self.items:
            rate = str(item.tax_rate)
            tax_breakdown[rate]["taxable"] += item.subtotal
            tax_breakdown[rate]["tax"] += item.tax_amount

        # company_logo_src — base64 ili URL za WeasyPrint
        company_logo_src = None
        if self.company.logo:
            try:
                import base64

                with open(self.company.logo.path, "rb") as fh:
                    ext = self.company.logo.name.rsplit(".", 1)[-1].lower()
                    mime = "image/png" if ext == "png" else "image/jpeg"
                    company_logo_src = f"data:{mime};base64,{base64.b64encode(fh.read()).decode()}"
            except Exception:
                company_logo_src = None

        context = {
            "invoice": self.invoice,
            "company": self.company,
            "items": self.items,
            "tax_breakdown": dict(tax_breakdown),
            "is_draft": self.invoice.status == "draft",
            "lang": self.lang,
            "company_logo_src": company_logo_src,
            "BASE_URL": getattr(settings, "BASE_URL", "https://limit-connect.com"),
        }

        html_string = render_to_string(self._template, context)
        base_url = getattr(settings, "BASE_URL", None)

        try:
            return weasyprint.HTML(string=html_string, base_url=base_url).write_pdf()
        except Exception as exc:
            logger.error("WeasyPrint PDF generation failed [template=%s]: %s", self._template, exc)
            raise
