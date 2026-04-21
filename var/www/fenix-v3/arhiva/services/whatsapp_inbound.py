"""
Fenix v3 — PLAN_032: WAHA WhatsApp inbound webhook
Kada komitent pošalje sliku/PDF na WhatsApp broj firme → automatski u arhivu.

Flow:
  WAHA → POST /wh/arhiva/waha/ → WAHAWebhookProcessor
       → pronađi firmu po whatsapp_number
       → preuzmi medij od WAHA API
       → kreiraj ArhivaEntry(source=WHATSAPP)
       → pokrni fenixscan_ocr_task
"""

import hashlib
import hmac
import logging
import re

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger("fenix.arhiva.waha")

WAHA_URL = getattr(settings, "WAHA_URL", "http://localhost:8080/api")
WAHA_SESSION = getattr(settings, "WAHA_SESSION", "default")
WAHA_WEBHOOK_SECRET = getattr(settings, "WAHA_WEBHOOK_SECRET", "")

# Podržani MIME tipovi za auto-OCR
SUPPORTED_MEDIA = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}


def _normalize_phone(raw: str) -> str:
    """'385912345678@c.us' → '385912345678' → '+385912345678'"""
    digits = re.sub(r"\D", "", raw.split("@")[0])
    if digits and not digits.startswith("+"):
        digits = "+" + digits
    return digits


def _find_company(sender_phone: str):
    """
    Pronađi firmu čiji whatsapp_number odgovara broju pošiljatelja.
    Vraća Company ili None.
    Uspoređuje normalizirane oblike (samo znamenke).
    """
    from companies.models import Company

    sender_digits = re.sub(r"\D", "", sender_phone)
    # Dohvati sve firme koje imaju whatsapp_enabled i whatsapp_number
    for company in Company.objects.filter(whatsapp_enabled=True).exclude(whatsapp_number=""):
        stored_digits = re.sub(r"\D", "", company.whatsapp_number)
        if stored_digits and stored_digits == sender_digits:
            return company
    return None


def _download_media(media_url: str, message_id: str) -> tuple[bytes, str, str]:
    """
    Preuzme medij od WAHA API-ja.
    Vraća (content_bytes, filename, mimetype).
    """
    try:
        r = requests.get(media_url, timeout=30, stream=True)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()
        # Odredi ekstenziju
        ext_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/heic": "heic",
            "application/pdf": "pdf",
        }
        ext = ext_map.get(content_type, "bin")
        filename = f"waha_{message_id[:16]}.{ext}"
        return r.content, filename, content_type
    except Exception as exc:
        logger.error("WAHA media download failed: %s", exc)
        raise


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Opcionalna HMAC provjera ako WAHA_WEBHOOK_SECRET nije prazan."""
    if not WAHA_WEBHOOK_SECRET:
        return True  # bez secretsa — prihvati sve
    expected = hmac.new(WAHA_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature or "")


class WAHAWebhookProcessor:
    """
    Obrađuje jedan WAHA webhook event.
    Koristi se iz view-a.
    """

    def __init__(self, payload: dict):
        self.payload = payload

    def process(self) -> dict:
        """
        Vrati {'status': 'ok'|'skip'|'error', 'detail': str}.
        """
        event = self.payload.get("event", "")
        if event != "message":
            return {"status": "skip", "detail": f"event={event}"}

        msg = self.payload.get("payload", {})
        has_media = msg.get("hasMedia", False)
        if not has_media:
            return {"status": "skip", "detail": "no media"}

        sender_raw = msg.get("from", "")
        sender_phone = _normalize_phone(sender_raw)
        message_id = msg.get("id", "") or f"waha_{timezone.now().timestamp()}"
        body_text = msg.get("body", "")

        company = _find_company(sender_phone)
        if not company:
            logger.info("WAHA: nepoznat pošiljatelj %s", sender_phone)
            return {"status": "skip", "detail": f"unknown sender {sender_phone}"}

        media_url = msg.get("mediaUrl") or self._build_media_url(message_id)
        if not media_url:
            return {"status": "error", "detail": "no mediaUrl"}

        try:
            content, filename, mimetype = _download_media(media_url, message_id)
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

        if mimetype not in SUPPORTED_MEDIA:
            logger.info("WAHA: nepodrzan MIME %s od %s", mimetype, sender_phone)
            return {"status": "skip", "detail": f"unsupported mime {mimetype}"}

        entry = self._create_entry(company, filename, content, mimetype, sender_phone, body_text)
        self._trigger_ocr(entry)

        logger.info("WAHA: ArhivaEntry %s kreiran za firmu %s od %s", entry.pk, company.name, sender_phone)
        return {"status": "ok", "entry_id": str(entry.pk)}

    def _build_media_url(self, message_id: str) -> str:
        """Fallback: WAHA v1 pattern za dohvat medija po ID-u."""
        return f"{WAHA_URL}/messages/{message_id}/download/{WAHA_SESSION}"

    def _create_entry(self, company, filename, content, mimetype, sender_phone, caption):
        from arhiva.models import ArhivaEntry

        title = (
            caption.strip()[:200]
            if caption.strip()
            else f"WhatsApp — {sender_phone} — {timezone.now().strftime('%d.%m.%Y %H:%M')}"
        )

        entry = ArhivaEntry(
            company=company,
            title=title,
            file_name=filename,
            file_size=len(content),
            file_type=mimetype,
            source=ArhivaEntry.Source.WHATSAPP,
            document_date=timezone.now().date(),
        )
        entry.file.save(filename, ContentFile(content), save=False)
        entry.save()
        return entry

    def _trigger_ocr(self, entry):
        try:
            from arhiva.tasks import fenixscan_ocr_task

            fenixscan_ocr_task.delay(str(entry.pk))
        except Exception as exc:
            logger.warning("WAHA: OCR task failed to queue: %s", exc)
