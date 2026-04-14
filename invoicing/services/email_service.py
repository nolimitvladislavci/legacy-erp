"""Invoice email sending service — Sprint 2A: HTML + tracking."""

import hashlib
import hmac
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import DatabaseError
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


def _generate_tracking_url(entry_pk):
    """Generate HMAC-signed tracking pixel URL."""
    pk_str = str(entry_pk)
    sig = hmac.new(settings.SECRET_KEY[:32].encode(), pk_str.encode(), hashlib.sha256).hexdigest()[:16]
    base_url = getattr(settings, "SITE_URL", "https://limit-connect.com")
    return f"{base_url}/invoicing/track/{pk_str}.{sig}/"


def send_invoice_email(invoice):
    """
    Generate PDF and email it to the invoice client.
    Returns (ok: bool, message: str).
    """
    if not invoice.client_email:
        return False, "Klijent nema email adresu!"

    is_hr = getattr(invoice, "is_hr", invoice.country == "HR" if hasattr(invoice, "country") else True)
    # Tracking pixel
    tracking_pixel_url = ""
    entry = None
    try:
        from documents.models import ArhivaEntry

        entry = ArhivaEntry.objects.filter(
            source_type="invoice_out", source_id=str(invoice.pk), company=invoice.company
        ).first()
        if entry:
            tracking_pixel_url = _generate_tracking_url(entry.pk)
    except DatabaseError as e:
        logger.debug("Tracking pixel setup: %s", e)

    # Client portal URL — koristi centralnu get_portal_url()
    from invoicing.utils import get_portal_url

    client_portal_url = ""
    if hasattr(invoice, "client_token") and invoice.client_token:
        lang = "de" if not is_hr else "hr"
        client_portal_url = get_portal_url(invoice, lang=lang)

    # Render HTML template
    ctx = {
        "lang": "hr" if is_hr else "de",
        "client_name": invoice.client_name,
        "invoice_number": invoice.number,
        "total": str(invoice.total),
        "currency": invoice.currency,
        "date_due": invoice.date_due.strftime("%d.%m.%Y") if invoice.date_due else None,
        "issuer_name": getattr(invoice, "issuer_name", "") or "",
        "issuer_address": getattr(invoice, "issuer_address", "") or "",
        "issuer_email": getattr(invoice, "issuer_email", "") or "",
        "issuer_iban": getattr(invoice, "issuer_iban", "") or "",
        "client_portal_url": client_portal_url,
        "tracking_pixel_url": tracking_pixel_url,
        "doc_label": "Rechnung" if not is_hr else "Racun",
        "greeting": "Sehr geehrte/r" if not is_hr else "Postovani",
        "intro_text": "im Anhang finden Sie:" if not is_hr else "u privitku se nalazi dokument:",
        "due_label": "Falligkeitsdatum" if not is_hr else "Rok placanja",
        "payment_label": "Zahlungsdaten" if not is_hr else "Podaci za placanje",
        "reference_label": "Verwendungszweck" if not is_hr else "Poziv na broj",
        "cta_text": "Rechnung online ansehen" if not is_hr else "Pregledaj racun online",
        "auto_notice": (
            "Diese Nachricht wurde automatisch generiert."
            if not is_hr
            else "Ova poruka je automatski generirana iz sustava LIMIT CONNECT."
        ),
    }
    html_body = render_to_string("emails/invoice_email.html", ctx)

    # Plain text fallback
    if is_hr:
        subject = f"Racun {invoice.number} - {invoice.issuer_name}"
        text_body = (
            f"Postovani {invoice.client_name},\n\n"
            f"u privitku se nalazi racun broj {invoice.number} "
            f"u iznosu {invoice.total} {invoice.currency}.\n\n"
            f"Rok placanja: {invoice.date_due or 'Po dogovoru'}\n"
            f"IBAN: {invoice.issuer_iban}\n\n"
            f"Hvala na povjerenju!\n{invoice.issuer_name}"
        )
    else:
        subject = f"Rechnung {invoice.number} - {invoice.issuer_name}"
        text_body = (
            f"Sehr geehrte/r {invoice.client_name},\n\n"
            f"im Anhang finden Sie die Rechnung Nr. {invoice.number} "
            f"uber {invoice.total} {invoice.currency}.\n\n"
            f"Falligkeitsdatum: {invoice.date_due or 'Sofort'}\n"
            f"IBAN: {invoice.issuer_iban}\n\n"
            f"Mit freundlichen Grussen,\n{invoice.issuer_name}"
        )

    try:
        # Generate PDF (with fallback)
        pdf_bytes = None
        try:
            from invoicing.services.pdf_service import generate_invoice_pdf

            pdf_bytes, _ = generate_invoice_pdf(invoice)
        except ImportError as pdf_err:
            logger.warning("PDF generation failed for %s: %s", invoice.number, pdf_err)

        # Build email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[invoice.client_email],
        )
        email.attach_alternative(html_body, "text/html")

        if pdf_bytes:
            email.attach(f"racun_{invoice.number}.pdf", pdf_bytes, "application/pdf")
        else:
            # Notify in body that PDF couldn't be generated
            email.body += "\n\nNapomena: PDF nije mogao biti generiran. Koristite online link za pregled."

        email.send(fail_silently=False)

        # Update invoice status
        invoice.status = "SENT"
        invoice.save(update_fields=["status"])

        # Update ArhivaEntry email tracking
        if entry:
            entry.email_sent_at = timezone.now()
            entry.email_sent_to = invoice.client_email
            entry.save(update_fields=["email_sent_at", "email_sent_to"])

        return True, f"Racun poslan na {invoice.client_email}"

    except Exception as e:
        logger.error("Email send failed for %s: %s", invoice.number, e)
        return False, f"Greska pri slanju: {e}"
