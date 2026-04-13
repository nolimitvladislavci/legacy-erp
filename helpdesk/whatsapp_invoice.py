"""
helpdesk/whatsapp_invoice.py — WhatsApp → Smart Import bridge

Tok:
  1. Korisnik pošalje sliku/PDF računa na WhatsApp
  2. WAHA webhook → whatsapp_webhook.py detektira media → pozove process_wa_invoice
  3. Slika se skida s WAHA-e, sprema u ImportBatch
  4. Celery task parsira (Gemini + Claude fallback)
  5. Odgovor natrag na WhatsApp: "✅ Račun od Konzuma, 450€, PDV 25%"
"""

import logging
import os

import requests
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger("helpdesk.whatsapp")


def download_waha_media(media_url):
    """Download media from WAHA API. Returns (bytes, mimetype) or (None, None)."""
    if not media_url:
        return None, None

    try:
        headers = {}
        api_key = getattr(settings, "WAHA_API_KEY", "")
        if api_key:
            headers["X-Api-Key"] = api_key

        # WAHA may return relative URLs
        if media_url.startswith("/"):
            media_url = f"{settings.WAHA_API_URL}{media_url}"

        resp = requests.get(media_url, timeout=30, headers=headers)
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            return resp.content, content_type
    except requests.RequestException as e:
        logger.error("WAHA media download failed: %s", e)

    return None, None


def _find_company_by_phone(phone):
    """Map WhatsApp phone number to a company.

    Lookup chain:
    1. UserProfile with matching phone
    2. Company with matching phone in contacts
    3. Partner with matching phone → partner.company
    """
    from accounts.models import UserProfile
    from companies.models import Company

    # 1. Check UserProfile phone
    profile = UserProfile.objects.filter(phone__endswith=phone[-9:]).first()
    if profile and profile.company:
        return profile.company, profile.user

    # 2. Check Company contacts
    company = Company.objects.filter(phone__endswith=phone[-9:]).first()
    if company:
        return company, None

    # 3. Check Partner phone
    from partners.models import Partner

    partner = Partner.objects.filter(phone__endswith=phone[-9:]).first()
    if partner and hasattr(partner, "company") and partner.company:
        return partner.company, None

    return None, None


def process_wa_invoice(phone, media_data, mimetype, caption=""):
    """Process an incoming WhatsApp invoice image/PDF.

    Args:
        phone: Normalized phone number (digits only)
        media_data: Raw bytes of the media file
        mimetype: MIME type (image/jpeg, application/pdf, etc.)
        caption: Optional caption text from the WhatsApp message

    Returns:
        dict with keys: success, message (reply text), batch_id
    """
    from smart_import.models import ImportBatch
    from smart_import.tasks import process_import_batch

    # Determine file type
    is_pdf = "pdf" in mimetype.lower()
    is_xml = "xml" in mimetype.lower()
    is_image = any(t in mimetype.lower() for t in ("image", "jpeg", "png", "webp", "heic"))

    if not (is_pdf or is_xml or is_image):
        return {
            "success": False,
            "message": "📎 Podržani formati: slika (JPG/PNG), PDF ili XML račun.",
            "batch_id": None,
        }

    # Find company by phone
    company, user = _find_company_by_phone(phone)
    if not company:
        return {
            "success": False,
            "message": (
                "❓ Vaš broj nije povezan s nijednom tvrtkom u sustavu.\n"
                "Registrirajte se na https://limit-connect.com/hr/register/ "
                "i dodajte WhatsApp broj u profil."
            ),
            "batch_id": None,
        }

    # Determine file extension
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "application/pdf": ".pdf",
        "text/xml": ".xml",
        "application/xml": ".xml",
    }
    ext = ext_map.get(mimetype.lower(), ".jpg")
    file_type = "pdf" if is_pdf else ("xml" if is_xml else "image")

    # Create ImportBatch
    filename = f"whatsapp_{phone[-4:]}_{os.urandom(4).hex()}{ext}"
    batch = ImportBatch(
        company=company,
        file_type=file_type,
        status="pending",
        original_filename=filename,
        created_by=user,
        status_message="Primljeno putem WhatsApp",
    )
    batch.file.save(filename, ContentFile(media_data), save=False)
    batch.save()

    # Kick off Celery processing
    process_import_batch.delay(batch.pk)

    logger.info(
        "WA invoice batch #%d created for company %s (phone %s)",
        batch.pk,
        company.name,
        phone,
    )

    return {
        "success": True,
        "message": (
            f"📄 Račun primljen! Obrađujem...\n"
            f"Firma: {company.name}\n"
            f"Ref: WA-{batch.pk}\n\n"
            f"Javim se čim AI završi analizu (obično < 60 sekundi)."
        ),
        "batch_id": batch.pk,
    }


def send_batch_result(phone, batch_id):
    """Send parsed batch results back to WhatsApp.
    Called by Celery task after processing completes.
    """
    from core.whatsapp import send_text
    from smart_import.models import ImportBatch

    try:
        batch = ImportBatch.objects.get(pk=batch_id)
    except ImportBatch.DoesNotExist:
        return

    if batch.status == "error":
        send_text(
            f"+{phone}",
            f"⚠️ Ref WA-{batch.pk}: Nismo uspjeli pročitati račun.\n"
            f"Pokušajte s boljom slikom (jasnije, bez sjena).\n"
            f"Ili uploadajte na: https://limit-connect.com/hr/smart-import/",
        )
        return

    if batch.status in ("ready", "confirmed"):
        items = batch.items.all()
        total = sum((item.quantity or 1) * (item.purchase_price or 0) for item in items)
        supplier_name = batch.supplier.name if batch.supplier else "Nepoznat"

        lines = [f"✅ Račun obrađen! Ref: WA-{batch.pk}"]
        lines.append(f"Dobavljač: {supplier_name}")
        lines.append(f"Stavki: {items.count()}")
        lines.append(f"Ukupno: {total:.2f} €")

        if items.count() <= 5:
            lines.append("")
            for item in items[:5]:
                qty = item.quantity or 1
                price = item.purchase_price or 0
                lines.append(f"  • {item.vendor_name}: {qty}x {price:.2f}€")

        lines.append(f"\nPregled: https://limit-connect.com/hr/smart-import/{batch.pk}/")
        send_text(f"+{phone}", "\n".join(lines))
