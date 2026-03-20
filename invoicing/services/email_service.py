"""Invoice email sending service."""
import base64
from django.conf import settings


def send_invoice_email(invoice):
    """
    Generate PDF and email it to the invoice client.
    Returns (ok: bool, message: str).
    """
    from invoicing.services.pdf_service import generate_invoice_pdf

    if not invoice.client_email:
        return False, 'Klijent nema email adresu!'

    try:
        pdf_bytes, _ = generate_invoice_pdf(invoice)

        if invoice.is_hr:
            subject = f'Račun {invoice.number} - {invoice.issuer_name}'
            body = (
                f'Poštovani {invoice.client_name},\n\n'
                f'u privitku se nalazi račun broj {invoice.number} '
                f'u iznosu {invoice.total} {invoice.currency}.\n\n'
                f'Rok plaćanja: {invoice.date_due or "Po dogovoru"}\n'
                f'IBAN: {invoice.issuer_iban}\n\n'
                f'Hvala na povjerenju!\n{invoice.issuer_name}'
            )
        else:
            subject = f'Rechnung {invoice.number} - {invoice.issuer_name}'
            body = (
                f'Sehr geehrte/r {invoice.client_name},\n\n'
                f'im Anhang finden Sie die Rechnung Nr. {invoice.number} '
                f'über {invoice.total} {invoice.currency}.\n\n'
                f'Fälligkeitsdatum: {invoice.date_due or "Sofort"}\n'
                f'IBAN: {invoice.issuer_iban}\n\n'
                f'Mit freundlichen Grüßen,\n{invoice.issuer_name}'
            )

        from invoicing.tasks import send_email_with_attachment_task
        send_email_with_attachment_task.delay(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_list=[invoice.client_email],
            attachment_name=f'racun_{invoice.number}.pdf',
            attachment_content_b64=base64.b64encode(pdf_bytes).decode(),
            content_type='application/pdf',
        )

        invoice.status = 'SENT'
        invoice.save(update_fields=['status'])
        return True, f'Račun poslan na {invoice.client_email}'

    except Exception as e:
        return False, f'Greška pri slanju: {e}'
