"""
evalidator/seal_service.py — DocumentSeal generator

Generira kriptografski pečat za arhivske dokumente.
Pečat = SHA-256 hash + unique token + QR kod + metapodaci.

Zakonska osnova:
- eIDAS Art. 41: elektronički vremenski žig = presumpcija integriteta
- GoBD §14b (DE): neopoziv, vremenski označen, dostupan 10g.
- ZED HR (NN 150/05): digitalni dokument s timestampom = original

Upotreba:
    from evalidator.seal_service import generate_seal, get_or_create_seal
    seal = generate_seal(arhiva_entry, user=request.user, channel='email')
    qr_png_bytes = seal_to_qr_png(seal)
"""

import hashlib
import io
import logging
import os

from django.utils import timezone

logger = logging.getLogger("evalidator.seal")


def _sha256_file(file_path: str) -> str:
    """SHA-256 hex digest fajla. Vraća '' ako fajl ne postoji."""
    if not file_path or not os.path.exists(file_path):
        return ""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def _sha256_content(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def generate_seal(arhiva_entry, user=None, channel: str = "", viral_code: str = "") -> "DocumentSeal":
    """
    Kreira novi DocumentSeal za ArhivaEntry.

    Args:
        arhiva_entry: ArhivaEntry instance
        user: Django User (optional, za audit)
        channel: 'email' | 'whatsapp' | 'portal' | 'datev' | ''
        viral_code: pre-generated viral code (optional)

    Returns:
        DocumentSeal instance (saved)
    """
    from evalidator.models import DocumentSeal

    # SHA-256 hash fajla
    file_path = ""
    if hasattr(arhiva_entry, "file_path") and arhiva_entry.file_path:
        import os

        base_dir = "/var/www/fina-connect"
        fp = arhiva_entry.file_path
        if not fp.startswith("/"):
            fp = os.path.join(base_dir, fp.lstrip("/"))
        file_path = fp

    sha256 = _sha256_file(file_path)
    if not sha256:
        # Fallback: hash metapodataka dokumenta
        meta = f"{arhiva_entry.doc_number}|{arhiva_entry.doc_date}|{arhiva_entry.amount}|{arhiva_entry.company_id}"
        sha256 = _sha256_content(meta.encode())

    # GoBD: 10 godina čuvanje
    from datetime import timedelta

    expires = timezone.now() + timedelta(days=3652)

    # Viral code
    if not viral_code:
        viral_code = _gen_viral_code()

    company = arhiva_entry.company
    seal = DocumentSeal.objects.create(
        sha256_hash=sha256,
        arhiva_entry_id=arhiva_entry.pk,
        arhiva_company_id=company.pk if company else None,
        doc_number=arhiva_entry.doc_number or "",
        doc_date=arhiva_entry.doc_date,
        partner_name=arhiva_entry.partner_name or "",
        amount=arhiva_entry.amount,
        currency=arhiva_entry.currency or "EUR",
        issuer_name=company.name if company else "",
        issuer_country=getattr(company, "country", "HR") or "HR",
        sealed_by_user_id=user.pk if user else None,
        sealed_by_username=user.username if user else "",
        expires_at=expires,
        send_channel=channel,
        viral_code=viral_code,
    )
    logger.info("Seal %s generated for entry %s (channel=%s)", seal.seal_token, arhiva_entry.pk, channel)
    return seal


def get_or_create_seal(arhiva_entry, user=None, channel: str = "") -> tuple:
    """
    Vraća postojeći seal za entry ili kreira novi.
    Returns: (seal, created: bool)
    """
    from evalidator.models import DocumentSeal

    existing = (
        DocumentSeal.objects.filter(
            arhiva_entry_id=arhiva_entry.pk,
            expires_at__isnull=False,
        )
        .order_by("-sealed_at")
        .first()
    )

    if existing and existing.is_valid:
        return existing, False

    return generate_seal(arhiva_entry, user=user, channel=channel), True


def seal_to_qr_png(seal, box_size: int = 6, border: int = 2) -> bytes:
    """
    Generira QR kod za verify URL kao PNG bytes.
    Vraća prazni bytes ako qrcode nije instaliran.
    """
    try:
        import qrcode

    except ImportError:
        logger.warning("qrcode nije instaliran — QR generation preskočen")
        return b""

    url = seal.verify_url
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def seal_to_qr_base64(seal) -> str:
    """QR PNG kao base64 data URI za embed u HTML/email."""
    import base64

    png = seal_to_qr_png(seal)
    if not png:
        return ""
    b64 = base64.b64encode(png).decode()
    return f"data:image/png;base64,{b64}"


def embed_seal_in_pdf(pdf_bytes: bytes, seal) -> bytes:
    """
    Dodaje pečat footer u PDF (pečat = token + QR mini + URL).
    Koristi PyMuPDF (fitz). Vraća originalni PDF ako fitz nije dostupan.
    """
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF nije instaliran — PDF seal embed preskočen")
        return pdf_bytes

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            rect = page.rect
            # Footer područje — zadnjih 20pt stranice
            footer_rect = fitz.Rect(20, rect.height - 22, rect.width - 20, rect.height - 4)
            seal_text = (
                f"eValidator Pečat: {seal.seal_token}  |  "
                f"SHA-256: {seal.sha256_hash[:16]}...  |  "
                f"Verifikacija: evalidator.eu/verify/{seal.seal_token}/  |  "
                f"Pečaćeno: {seal.sealed_at.strftime('%d.%m.%Y %H:%M')} UTC"
            )
            page.insert_textbox(
                footer_rect,
                seal_text,
                fontsize=5.5,
                color=(0.4, 0.4, 0.4),
                align=0,  # left
            )
            # Tanka linija iznad footera
            page.draw_line(
                fitz.Point(20, rect.height - 24),
                fitz.Point(rect.width - 20, rect.height - 24),
                color=(0.6, 0.6, 0.6),
                width=0.3,
            )
        result = doc.tobytes()
        doc.close()
        return result
    except Exception as e:
        logger.error("PDF seal embed failed: %s", e)
        return pdf_bytes


def _gen_viral_code() -> str:
    """LC-XXXX format — 4 random uppercase alphanumeric chars."""
    import secrets
    import string

    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(4))
    return f"LC{suffix}"


def record_verify(seal_token: str, request=None) -> bool:
    """Bilježi otvaranje verify stranice. Returns True ako seal postoji."""
    from evalidator.models import DocumentSeal

    try:
        seal = DocumentSeal.objects.get(seal_token=seal_token)
        DocumentSeal.objects.filter(pk=seal.pk).update(
            verify_count=seal.verify_count + 1,
            last_verified_at=timezone.now(),
        )
        return True
    except DocumentSeal.DoesNotExist:
        return False
