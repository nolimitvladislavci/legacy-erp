"""smart_import/services.py -- Parse XML/PDF/Image invoices, match items.
   v2 - 2026-03-17: Enhanced image fallback, better error handling, Gemini usage logging.
"""
import base64
import os
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from io import BytesIO

logger = logging.getLogger(__name__)

# Register HEIC/HEIF opener for iPhone photos
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass


# -- XML (UBL e-Racun) ---------------------------------------------------------

def parse_xml(file_path):
    try:
        from lxml import etree
    except ImportError:
        import xml.etree.ElementTree as etree

    tree = etree.parse(file_path)
    root = tree.getroot()

    ns = {
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    }

    rows = []
    lines = root.findall(".//cac:InvoiceLine", ns) or root.findall(".//InvoiceLine")
    for line in lines:
        name = _xml_text(line, [
            "cac:Item/cbc:Name", "Item/Name", "cbc:Description",
        ], ns)
        qty_str   = _xml_text(line, ["cbc:InvoicedQuantity", "InvoicedQuantity"], ns)
        price_str = _xml_text(line, [
            "cac:Price/cbc:PriceAmount", "Price/PriceAmount", "cbc:LineExtensionAmount",
        ], ns)
        if not name:
            continue
        rows.append({
            "vendor_name":    name.strip(),
            "quantity":       _to_decimal(qty_str, 1),
            "purchase_price": _to_decimal(price_str, 0),
        })

    if not rows:
        rows = _generic_xml_scan(root)
    return rows


def _xml_text(element, paths, ns):
    for path in paths:
        try:
            el = element.find(path, ns)
            if el is not None and el.text:
                return el.text
        except Exception:
            pass
    return ""


def _generic_xml_scan(root):
    rows = []
    for el in root.iter():
        tag = re.sub(r"\{.*?\}", "", (el.tag or "")).lower()
        if tag in ("item", "line", "invoiceline", "orderline", "row"):
            name = qty = price = ""
            for child in el.iter():
                ctag = re.sub(r"\{.*?\}", "", (child.tag or "")).lower()
                if ctag in ("name", "description", "itemname", "naziv") and child.text:
                    name = child.text
                elif ctag in ("quantity", "invoicedquantity", "qty", "kolicina") and child.text:
                    qty = child.text
                elif ctag in ("price", "priceamount", "unitprice", "cijena") and child.text:
                    price = child.text
            if name:
                rows.append({
                    "vendor_name":    name.strip(),
                    "quantity":       _to_decimal(qty, 1),
                    "purchase_price": _to_decimal(price, 0),
                })
    return rows


# -- PDF -----------------------------------------------------------------------

def parse_pdf(file_path):
    text = _extract_pdf_text(file_path)
    if text.strip():
        return _claude_extract_lines(text, source_type="pdf")

    logger.info("PDF text empty, trying image fallback for %s", file_path)
    return _pdf_image_fallback(file_path)


def _pdf_image_fallback(file_path):
    """Render PDF pages as images and send to Claude Vision."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF not installed, cannot process scanned PDF")
        return []

    all_rows = []
    try:
        doc = fitz.open(file_path)
        for page_num in range(min(len(doc), 5)):
            page = doc[page_num]
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            b64 = base64.standard_b64encode(img_bytes).decode()

            rows = _gemini_vision_extract(b64, "image/png")
            all_rows.extend(rows)
        doc.close()
    except Exception as e:
        logger.error("PDF image fallback failed: %s", e)

    # If Gemini failed on all pages, try Claude on the original PDF rendered as image
    if not all_rows:
        logger.info("Gemini PDF fallback produced no results, trying Claude for %s", file_path)
        all_rows = _claude_vision_extract(file_path)

    return all_rows


def _extract_pdf_text(file_path):
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception as e:
        logger.error("PDF extract failed: %s", e)
        return ""


# -- Image (Gemini Vision) -----------------------------------------------------

def parse_image(file_path):
    """Primary image parser: Gemini Vision with Claude fallback."""
    image_b64, media_type = _encode_image(file_path)
    if not image_b64:
        return []

    # Try Gemini first
    rows = _gemini_vision_extract(image_b64, media_type)
    if rows:
        return rows

    # Fallback to Claude Vision
    logger.info("Gemini returned no results, trying Claude Vision fallback for %s", file_path)
    rows = _claude_vision_extract(file_path)
    if rows:
        return rows

    return []


def parse_image_enhanced(file_path):
    """Enhanced image parser: higher contrast, grayscale, retry with different prompt."""
    image_b64, media_type = _encode_image_enhanced(file_path)
    if not image_b64:
        return []
    return _gemini_vision_extract_enhanced(image_b64, media_type)




def _claude_vision_extract(file_path):
    """Fallback: use Claude Haiku Vision for invoice extraction when Gemini fails."""
    try:
        import anthropic
        from django.conf import settings

        api_key = getattr(settings, "ANTHROPIC_API_KEY", None) or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not configured, skipping Claude fallback")
            return []

        image_b64, media_type = _encode_image(file_path)
        if not image_b64:
            return []

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Ovo je slika racuna/fakture. Izvuci SVE stavke. "
                            "Tekst moze biti na hrvatskom, njemackom ili engleskom. "
                            "Vrati ISKLJUCIVO JSON array bez ikakvog drugog teksta. "
                            "Svaki element: "
                            '{"vendor_name": "<naziv stavke>", "quantity": <broj>, "purchase_price": <jedinicna cijena>}. '
                            "Ako cijena nije vidljiva, koristi 0. Ukljuci SVAKU stavku."
                        ),
                    },
                ],
            }],
        )

        text = message.content[0].text.replace("```json", "").replace("```", "").strip()
        rows = _parse_json_rows(text)
        if rows:
            logger.info("Claude Vision extracted %d items (fallback)", len(rows))
        else:
            logger.warning("Claude Vision returned no parseable items. Raw: %s", text[:200])
        return rows

    except Exception as e:
        logger.error("Claude Vision fallback failed: %s", e)
        return []

def _gemini_vision_extract(image_b64, media_type):
    """Send a base64 image to Gemini Vision and extract invoice lines."""
    prompt = (
        "You are an expert invoice/receipt OCR parser. This image is a business document (invoice, receipt, delivery note). "
        "The text may be in Croatian, German, or English. "
        "Common Croatian terms: racun=invoice, faktura=invoice, dobavljac=supplier, "
        "artikl/naziv=item name, kolicina/kom/kol=quantity, cijena=price, iznos/ukupno=total, "
        "PDV=VAT, popust=discount, OIB=tax ID. "
        "Extract ALL line items from this document. "
        "Return ONLY a JSON array, no other text. Each element must have exactly: "
        '{"vendor_name": "<item name>", "quantity": <number>, "purchase_price": <unit price number>}. '
        "If unit price not visible, use 0. Include every row you can find. "
        "If you cannot find line items, try to extract at least the document header info as a single item."
    )

    try:
        from google import genai as _genai
        from django.conf import settings
        from PIL import Image as PILImage
        import io

        api_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not configured")
            return []

        _client = _genai.Client(api_key=api_key)
        image_data = base64.standard_b64decode(image_b64)
        img = PILImage.open(io.BytesIO(image_data))

        response = _client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, img])
        text = response.text.replace("```json", "").replace("```", "").strip()

        _log_gemini_usage(response, "smart_import_vision")

        rows = _parse_json_rows(text)
        if rows:
            logger.info("Gemini Vision extracted %d items", len(rows))
        else:
            logger.warning("Gemini Vision returned no parseable items. Raw: %s", text[:200])
        return rows
    except Exception as e:
        logger.error("Gemini Vision parse failed: %s", e)
        return []


def _gemini_vision_extract_enhanced(image_b64, media_type):
    """Enhanced extraction with more detailed prompt for difficult invoices."""
    prompt = (
        "You are an expert invoice OCR system. This image is an invoice or receipt. "
        "CAREFULLY extract ALL line items. Look for item names, quantities, and prices. "
        "The text may be in Croatian/German/English. "
        "Common patterns: artikl/naziv = item name, kol/kom/kolicina = quantity, "
        "cijena/price/EUR = price. "
        "Return ONLY a JSON array. Each element: "
        '{"vendor_name": "<item name>", "quantity": <number>, "purchase_price": <unit price as number>}. '
        "If you cannot read a price clearly, use 0. Extract EVERY line item you can find."
    )

    try:
        from google import genai as _genai
        from django.conf import settings
        from PIL import Image as PILImage
        import io

        api_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return []

        _client = _genai.Client(api_key=api_key)
        image_data = base64.standard_b64decode(image_b64)
        img = PILImage.open(io.BytesIO(image_data))

        response = _client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, img])
        text = response.text.replace("```json", "").replace("```", "").strip()

        _log_gemini_usage(response, "smart_import_vision_enhanced")

        rows = _parse_json_rows(text)
        logger.info("Enhanced Gemini Vision extracted %d items", len(rows))
        return rows
    except Exception as e:
        logger.error("Enhanced Gemini Vision failed: %s", e)
        return []


def _log_gemini_usage(response, caller):
    """Log Gemini API usage for cost tracking."""
    try:
        from smart_import.models import GeminiUsageLog
        usage = getattr(response, "usage_metadata", None)
        if usage:
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or 0
            # Gemini 2.5 Flash pricing: ~$0.15/1M input, ~$0.60/1M output
            cost = (input_tokens * 0.00000015) + (output_tokens * 0.0000006)
            GeminiUsageLog.objects.create(
                caller=caller,
                model="gemini-2.5-flash",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_eur=Decimal(str(round(cost, 8))),
                success=True,
            )
    except Exception as e:
        logger.debug("Failed to log Gemini usage: %s", e)


def _encode_image(file_path):
    try:
        from PIL import Image as PILImage, ImageEnhance, ImageFilter
        img = PILImage.open(file_path)

        # Auto-rotate based on EXIF (mobile camera photos)
        try:
            from PIL import ExifTags
            exif = img._getexif()
            if exif:
                for tag, val in exif.items():
                    if ExifTags.TAGS.get(tag) == "Orientation":
                        if val == 3:
                            img = img.rotate(180, expand=True)
                        elif val == 6:
                            img = img.rotate(270, expand=True)
                        elif val == 8:
                            img = img.rotate(90, expand=True)
                        break
        except Exception:
            pass

        img.thumbnail((2048, 2048), PILImage.LANCZOS)
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Sharpness(img).enhance(1.5)

        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        buf = BytesIO()
        fmt = img.format or "JPEG"
        if fmt not in ("JPEG", "PNG", "GIF", "WEBP"):
            fmt = "JPEG"
        save_kwargs = {"format": fmt}
        if fmt in ("JPEG", "WEBP"):
            save_kwargs["quality"] = 92
        img.save(buf, **save_kwargs)
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        return b64, "image/{}".format(fmt.lower())
    except Exception as e:
        logger.error("Image encode failed: %s", e)
        return None, None


def _encode_image_enhanced(file_path):
    """Enhanced encoding: grayscale, higher contrast, larger resolution for OCR."""
    try:
        from PIL import Image as PILImage, ImageEnhance, ImageFilter, ImageOps
        img = PILImage.open(file_path)

        # Auto-rotate
        try:
            from PIL import ExifTags
            exif = img._getexif()
            if exif:
                for tag, val in exif.items():
                    if ExifTags.TAGS.get(tag) == "Orientation":
                        if val == 3:
                            img = img.rotate(180, expand=True)
                        elif val == 6:
                            img = img.rotate(270, expand=True)
                        elif val == 8:
                            img = img.rotate(90, expand=True)
                        break
        except Exception:
            pass

        # Higher resolution for OCR
        img.thumbnail((3072, 3072), PILImage.LANCZOS)

        # Convert to grayscale for better OCR
        img = ImageOps.grayscale(img)

        # Stronger contrast and sharpening
        img = ImageEnhance.Contrast(img).enhance(1.8)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)

        # Convert back to RGB for API
        img = img.convert("RGB")

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=95)
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        return b64, "image/jpeg"
    except Exception as e:
        logger.error("Enhanced image encode failed: %s", e)
        return None, None


# -- Gemini text extraction ----------------------------------------------------

def _claude_extract_lines(text, source_type="text"):
    prompt = (
        "You are an invoice parser. Text extracted from a {}. "
        "Extract ALL line items. Return ONLY a JSON array, no other text. "
        'Each element: {{"vendor_name": "<name>", "quantity": <number>, "purchase_price": <unit price number>}}. '
        "If unit price unclear, use 0.\n\n---\n{}"
    ).format(source_type, text[:6000])
    try:
        from google import genai as _genai
        from django.conf import settings

        api_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not configured")
            return []

        _client = _genai.Client(api_key=api_key)
        response = _client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        result = response.text.replace("```json", "").replace("```", "").strip()

        _log_gemini_usage(response, "smart_import_text")

        return _parse_json_rows(result)
    except Exception as e:
        logger.error("Gemini text parse failed: %s", e)
        return []


def _parse_json_rows(raw):
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
            except Exception:
                return []
        else:
            return []
    if not isinstance(data, list):
        return []
    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("vendor_name") or item.get("name") or "").strip()
        if not name:
            continue
        rows.append({
            "vendor_name":    name,
            "quantity":       _to_decimal(item.get("quantity"), 1),
            "purchase_price": _to_decimal(item.get("purchase_price") or item.get("price"), 0),
        })
    return rows


# -- Item matching -------------------------------------------------------------

def match_items(batch):
    """Fuzzy-match ImportBatchItems to InventoryItems.
    Score: 1.0=exact mapping, >=0.8 green, 0.6-0.8 yellow, <0.6 red."""
    from smart_import.models import VendorItemMapping
    from inventory.models import InventoryItem

    company  = batch.company
    supplier = batch.supplier

    inv_items = list(InventoryItem.objects.filter(company=company, is_active=True))
    inv_names = [it.name.lower() for it in inv_items]

    for batch_item in batch.items.all():
        vname = batch_item.vendor_name.lower().strip()

        # 1. Learned mapping
        mapping_qs = VendorItemMapping.objects.filter(
            company=company, vendor_item_name__iexact=vname
        )
        if supplier:
            mapping_qs = mapping_qs.filter(partner=supplier)
        mapping = mapping_qs.first()
        if mapping:
            batch_item.matched_item = mapping.inventory_item
            batch_item.match_score  = 1.0
            batch_item.save(update_fields=["matched_item", "match_score"])
            continue

        # 2. Fuzzy match
        best_score = 0.0
        best_item  = None
        for idx, inv_name in enumerate(inv_names):
            score = SequenceMatcher(None, vname, inv_name).ratio()
            if score > best_score:
                best_score = score
                best_item  = inv_items[idx]

        batch_item.matched_item = best_item if best_score >= 0.4 else None
        batch_item.match_score  = round(best_score, 4)
        batch_item.save(update_fields=["matched_item", "match_score"])


# -- Helpers -------------------------------------------------------------------

def _to_decimal(value, default=0):
    if value is None:
        return str(default)
    s = str(value).strip()
    # Handle European format: 1.234,56 -> 1234.56
    # If comma is present and after the last dot, comma is decimal separator
    if "," in s:
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        if last_dot >= 0 and last_comma > last_dot:
            # European: 1.234,56 -> remove dots, replace comma with dot
            s = s.replace(".", "").replace(",", ".")
        else:
            # Simple comma decimal: 0,99 or no dots
            s = s.replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    # If still multiple dots (edge case), keep only last as decimal
    if s.count(".") > 1:
        parts = s.rsplit(".", 1)
        s = parts[0].replace(".", "") + "." + parts[1]
    try:
        return str(Decimal(s))
    except InvalidOperation:
        return str(default)


# ── Zaglavlje računa (header OCR) ────────────────────────────────────────────

def extract_invoice_header(file_path):
    """
    Izvuci zaglavlje računa (dobavljač, OIB, datum, iznos, PDV) iz slike.
    Vraća dict ili {} ako AI nije uspio.
    Inovacija: strukturirani JSON sa svim meta-podacima računa u jednom pozivu.
    """
    image_b64, media_type = _encode_image(file_path)
    if not image_b64:
        return {}

    prompt = (
        "You are an expert invoice header extractor. Extract ONLY the document header (not line items). "
        "Return ONLY a single JSON object with these exact keys: "
        '{"supplier_name": "<company name>", "supplier_oib": "<OIB/VAT number digits only, no spaces>", '
        '"invoice_number": "<document number>", "invoice_date": "<YYYY-MM-DD or empty>", '
        '"total_amount": <total number or null>, "vat_amount": <VAT/PDV number or null>, '
        '"base_amount": <base/osnovica number or null>, "currency": "<EUR|HRK|USD|...>", '
        '"confidence": <0.0-1.0 how confident you are>}. '
        "Croatian: OIB=tax ID, PDV=VAT, Iznos=Amount, Račun br.=Invoice no., Datum=Date. "
        "German: USt-IdNr=VAT ID, Rechnungsnummer=Invoice number, Betrag=Amount, MwSt=VAT. "
        "If a field is not visible, use null or empty string. "
        "IMPORTANT: Return ONLY valid JSON, no other text."
    )

    try:
        from google import genai as _genai
        from django.conf import settings
        from PIL import Image as PILImage
        import io, json

        api_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {}

        _client = _genai.Client(api_key=api_key)
        image_data = base64.standard_b64decode(image_b64)
        img = PILImage.open(io.BytesIO(image_data))

        response = _client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, img])
        text = response.text.replace("```json", "").replace("```", "").strip()
        _log_gemini_usage(response, "smart_import_header")

        header = json.loads(text)
        logger.info(
            "Header extracted: supplier=%s OIB=%s total=%s",
            header.get("supplier_name", "?"), header.get("supplier_oib", "?"), header.get("total_amount")
        )
        return header
    except Exception as e:
        logger.error("extract_invoice_header failed: %s", e)
        return {}


# ── UNIFIED OCR — stavke + header u jednom pozivu (cost-efficient) ──────────

def extract_unified(file_path):
    """
    Jedan Gemini poziv koji vraća i header i stavke.
    Inovacija: duplo jeftiniji od split pristupa (1 poziv umjesto 2).
    Returns: { 'header': {...}, 'items': [...] }
    """
    image_b64, media_type = _encode_image(file_path)
    if not image_b64:
        return {'header': {}, 'items': []}

    prompt = (
        "You are an expert invoice OCR system. Extract BOTH the document header AND all line items. "
        "Return ONLY a single JSON object with exactly two keys: "
        '"header" and "items". '
        "header must contain: "
        '{"supplier_name": "<company>", "supplier_oib": "<OIB/VAT digits only>", '
        '"invoice_number": "<number>", "invoice_date": "<YYYY-MM-DD or empty>", '
        '"total_amount": <number or null>, "vat_amount": <number or null>, '
        '"base_amount": <number or null>, "currency": "<EUR|HRK|USD>", '
        '"confidence": <0.0-1.0>}. '
        "items must be an array where each element has: "
        '{"vendor_name": "<item name>", "quantity": <number>, "purchase_price": <unit price>}. '
        "Croatian: OIB=tax ID, PDV=VAT, Iznos=Amount, Račun=Invoice, Datum=Date. "
        "German: USt-IdNr=VAT ID, Rechnungsnr=Invoice number, MwSt=VAT. "
        "If any field is not visible, use null or empty. Return ONLY valid JSON."
    )

    try:
        from google import genai as _genai
        from django.conf import settings
        from PIL import Image as PILImage
        import io

        api_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {'header': {}, 'items': []}

        _client = _genai.Client(api_key=api_key)
        image_data = base64.standard_b64decode(image_b64)
        img = PILImage.open(io.BytesIO(image_data))

        response = _client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, img])
        text = response.text.replace("```json", "").replace("```", "").strip()
        _log_gemini_usage(response, "smart_import_unified")

        data = json.loads(text)
        header = data.get('header', {})
        items = data.get('items', [])

        # Normalize items
        rows = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get('vendor_name') or item.get('name') or '').strip()
            if not name:
                continue
            rows.append({
                'vendor_name': name,
                'quantity': _to_decimal(item.get('quantity'), 1),
                'purchase_price': _to_decimal(item.get('purchase_price') or item.get('price'), 0),
            })

        logger.info("Unified OCR: header=%s items=%d", header.get('supplier_name', '?'), len(rows))
        return {'header': header, 'items': rows}
    except Exception as e:
        logger.error("Unified OCR failed: %s", e)
        return {'header': {}, 'items': []}
