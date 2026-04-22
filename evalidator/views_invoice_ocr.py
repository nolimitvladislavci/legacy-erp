"""
evalidator/views_invoice_ocr.py — OCR import iz slike/PDF u invoice builder
POST /invoice/ocr-import/ — multipart file → Gemini Vision → JSON polja za formu
Rate limit: 5 OCR/sat po IP-u (Gemini API trošak)
"""
import base64
import json
import logging
import mimetypes

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger("fenix.evalidator.invoice_ocr")

_OCR_PROMPT = """
You are an invoice data extraction AI. Extract ALL fields from this invoice image/PDF.

Return a valid JSON object with this exact structure (use empty string for missing fields):
{
  "doc_type": "INV",
  "number": "",
  "issue_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "currency": "EUR",
  "payment_method": "T",
  "note": "",
  "seller_name": "",
  "seller_oib": "",
  "seller_vat_id": "",
  "seller_address": "",
  "seller_city": "",
  "seller_country": "HR",
  "seller_email": "",
  "seller_iban": "",
  "seller_bic": "",
  "buyer_name": "",
  "buyer_oib": "",
  "buyer_address": "",
  "buyer_city": "",
  "buyer_country": "HR",
  "items": [
    {
      "description": "",
      "quantity": 1,
      "unit": "kom",
      "unit_price": 0.00,
      "discount_percent": 0,
      "tax_rate": 25
    }
  ]
}

Rules:
- doc_type: INV=invoice/račun, OFF=quote/ponuda, CRD=credit note/odobrenje
- payment_method: T=bank transfer, G=cash/gotovina, K=card/kartica
- Dates in ISO format YYYY-MM-DD
- Amounts as numbers (not strings)
- tax_rate: 25, 13, 5, or 0 (Croatian/EU VAT rates)
- unit: kom, sat, dan, mj, m, m2, m3, kg, L, paus, usl
- seller_country / buyer_country: ISO 2-letter (HR, DE, AT, SI, IT, FR...)
- Extract IBAN without spaces
- If seller_country is DE/AT/CH, use "de" tax terminology
- Return ONLY the JSON, no explanation, no markdown
"""


def _rate_ok_ocr(request, limit=5, window=3600):
    ip  = request.META.get("REMOTE_ADDR", "x")
    key = "ev_ocr_rate:" + ip
    n   = cache.get(key, 0)
    if n >= limit:
        return False
    cache.set(key, n + 1, window)
    return True


def _call_gemini_vision(image_bytes: bytes, mime_type: str) -> dict:
    """Pozovi Gemini Vision za ekstrakciju polja iz slike/PDF."""
    from django.conf import settings
    import google.generativeai as genai

    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # Gemini: inline data
    image_part = {
        "inline_data": {
            "mime_type": mime_type,
            "data": base64.b64encode(image_bytes).decode("utf-8"),
        }
    }

    response = model.generate_content(
        [_OCR_PROMPT, image_part],
        generation_config={"temperature": 0, "max_output_tokens": 2048},
    )

    text = response.text.strip()
    # Strip markdown code blocks if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    return json.loads(text)


@csrf_exempt
def invoice_ocr_import(request):
    """
    POST /invoice/ocr-import/
    multipart: file (image/jpeg, image/png, image/webp, application/pdf)
    Returns: JSON s poljima za pre-popunu forme
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    if not _rate_ok_ocr(request):
        return JsonResponse({
            "error": "Rate limit: 5 OCR imports/hour.",
            "upgrade": "https://evalidator.eu/pricing/"
        }, status=429)

    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "No file uploaded."}, status=400)

    allowed_types = {
        "image/jpeg":       "image/jpeg",
        "image/png":        "image/png",
        "image/webp":       "image/webp",
        "application/pdf":  "application/pdf",
    }

    ct = uploaded.content_type or ""
    # Fallback: detect from filename
    if ct not in allowed_types:
        guessed, _ = mimetypes.guess_type(uploaded.name or "")
        ct = guessed or ct

    if ct not in allowed_types:
        return JsonResponse({
            "error": f"Unsupported file type: {ct}. Use JPG, PNG, WebP or PDF."
        }, status=400)

    if uploaded.size > 10 * 1024 * 1024:
        return JsonResponse({"error": "File too large. Max 10 MB."}, status=400)

    try:
        image_bytes = uploaded.read()
        result = _call_gemini_vision(image_bytes, allowed_types[ct])
    except json.JSONDecodeError as exc:
        logger.warning("Gemini OCR JSON parse error: %s", exc)
        return JsonResponse({"error": "AI returned invalid data. Please try again."}, status=502)
    except Exception as exc:
        logger.error("Gemini OCR error: %s", exc)
        return JsonResponse({"error": f"OCR failed: {exc}"}, status=502)

    # Sanitize: ensure items list
    if not isinstance(result.get("items"), list) or not result["items"]:
        result["items"] = [{
            "description": "", "quantity": 1, "unit": "kom",
            "unit_price": 0, "discount_percent": 0, "tax_rate": 25
        }]

    # Detect language from seller_country
    sc = str(result.get("seller_country", "HR")).upper()
    result["lang"] = "de" if sc in ("DE", "AT", "CH") else "hr"

    logger.info("Invoice OCR import: seller=%s, items=%d",
                result.get("seller_name", "?"), len(result.get("items", [])))

    return JsonResponse({"ok": True, "data": result})
