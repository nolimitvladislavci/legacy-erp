"""
core/smart_import_pdf_patch.py
Vision fallback za skenirane PDF-ove u smart_import.
"""

import base64
import logging

logger = logging.getLogger(__name__)


def _pdf_to_images_b64(file_path, max_pages=4, dpi=150):
    try:
        import fitz

        doc = fitz.open(file_path)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        result = []
        for i in range(min(len(doc), max_pages)):
            pix = doc[i].get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            b64 = base64.standard_b64encode(pix.tobytes("png")).decode()
            result.append((b64, "image/png"))
        return result
    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.error("PDF->image failed: %s", e)
        return []


def apply_vision_patch():
    """Monkey-patch smart_import.services.parse_pdf s Vision fallbackom."""
    try:
        import smart_import.services as svc

        if getattr(svc, "_vision_patched", False):
            return

        _orig_extract = svc._extract_pdf_text
        _parse_json = svc._parse_json_rows
        _claude_lines = svc._claude_extract_lines

        def _vision_parse(file_path):
            images = _pdf_to_images_b64(file_path)
            if not images:
                return []
            prompt = (
                "You are an invoice parser. Extract ALL line items from this invoice. "
                "Return ONLY a JSON array, no other text. Each element: "
                '{"vendor_name": "<n>", "quantity": <number>, "purchase_price": <price>}. '
                "Include every product/service row. Use 0 for missing prices."
            )
            blocks = [
                {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}} for b64, mt in images
            ]
            blocks.append({"type": "text", "text": prompt})
            try:
                import anthropic
                from django.conf import settings

                client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=2048,
                    messages=[{"role": "user", "content": blocks}],
                )
                return _parse_json(msg.content[0].text.strip())
            except (IntegrityError, DatabaseError) as e:
                logger.error("Vision PDF failed: %s", e)
                return []

        def patched_parse_pdf(file_path):
            text = _orig_extract(file_path)
            if text.strip():
                rows = _claude_lines(text, source_type="pdf")
                if rows:
                    return rows
                logger.warning("PDF text ok but no rows, Vision fallback: %s", file_path)
            else:
                logger.info("PDF text empty, Vision fallback: %s", file_path)
            return _vision_parse(file_path)

        svc.parse_pdf = patched_parse_pdf
        svc._vision_patched = True
        logger.info("[smart_import] parse_pdf Vision patch applied OK")
    except (IntegrityError, DatabaseError) as e:
        logger.error("[smart_import] Vision patch failed: %s", e)
