"""
Invoicing utility functions.
"""

from django.conf import settings


def get_portal_url(invoice, lang: str = "hr") -> str:
    """
    Vrati apsolutni HTTPS URL za javnu kupčevu sobu (ponuda).

    Jedina funkcija koja generira ovaj URL — koriste je email, WhatsApp,
    PDF, template, view. Nema više hardkodiranih URL-ova.

    Args:
        invoice: Invoice instance s client_token UUID poljem
        lang: ISO jezik prefix (default 'hr')

    Returns:
        Npr. "https://limit-connect.com/hr/ponuda/UUID/"
    """
    base = getattr(settings, "SITE_URL", "https://limit-connect.com").rstrip("/")
    return f"{base}/{lang}/ponuda/{invoice.client_token}/"
