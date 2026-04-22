"""
evalidator/views_invoice.py — E-Invoice builder views
Stateless: POST → generiraj XML/PDF → vrati download, bez DB zapisa.
Rate limit: 10 generiranja/sat po IP-u.
"""
import json
import logging
from datetime import date, timedelta

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.core.cache import cache

from .invoice_service import compute_item, compute_totals, build_ubl_xml, build_pdf, make_filename

logger = logging.getLogger("fenix.evalidator.invoice")

_CURRENCIES  = ["EUR", "HRK", "USD", "GBP", "CHF", "CZK", "PLN", "HUF", "RON", "BGN"]
_PAY_METHODS = {
    "T": {"hr": "Transakcijski račun", "de": "Überweisung", "en": "Bank transfer"},
    "G": {"hr": "Gotovina",            "de": "Barzahlung",  "en": "Cash"},
    "K": {"hr": "Kartica",             "de": "Karte",       "en": "Card"},
    "O": {"hr": "Ostalo",              "de": "Sonstige",    "en": "Other"},
}
_DOC_TYPES = {
    "INV": {"hr": "Račun",     "de": "Rechnung",    "en": "Invoice"},
    "OFF": {"hr": "Ponuda",    "de": "Angebot",     "en": "Quote"},
    "CRD": {"hr": "Odobrenje", "de": "Gutschrift",  "en": "Credit note"},
    "PRO": {"hr": "Predračun", "de": "Proforma",    "en": "Proforma"},
}
_TAX_RATES = ["25", "13", "5", "0"]
_UNITS = ["kom", "sat", "dan", "mj", "m", "m2", "m3", "kg", "L", "paus", "usl",
          "pcs", "h", "St", "Std", "Tag", "Mon", "Psch"]


def _rate_ok_invoice(request, limit=10, window=3600):
    """10 generiranja/sat po IP-u."""
    ip  = request.META.get("REMOTE_ADDR", "x")
    key = "ev_inv_rate:" + ip
    n   = cache.get(key, 0)
    if n >= limit:
        return False
    cache.set(key, n + 1, window)
    return True


def _detect_lang(request) -> str:
    """Detektiraj jezik iz Accept-Language ili query param."""
    lang = request.GET.get("lang") or request.POST.get("lang") or ""
    lang = lang.lower()[:2]
    if lang in ("hr", "de", "en"):
        return lang
    accept = request.META.get("HTTP_ACCEPT_LANGUAGE", "").lower()
    for code in ("de", "hr", "en"):
        if code in accept:
            return code
    return "hr"


@require_GET
def invoice_builder(request):
    """GET /invoice/ — forma za kreiranje e-računa."""
    lang    = _detect_lang(request)
    today   = date.today()
    due     = today + timedelta(days=8)
    ctx = {
        "lang":         lang,
        "currencies":   _CURRENCIES,
        "pay_methods":  _PAY_METHODS,
        "doc_types":    _DOC_TYPES,
        "tax_rates":    _TAX_RATES,
        "units":        _UNITS,
        "today":        today.isoformat(),
        "due_default":  due.isoformat(),
    }
    return render(request, "evalidator/invoice/builder.html", ctx)


@csrf_exempt
def invoice_generate(request):
    """
    POST /invoice/generate/
    Generiraj XML i/ili PDF e-račun.
    ?format=xml|pdf|both (default=both)
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    if not _rate_ok_invoice(request):
        return JsonResponse({"error": "Rate limit: 10 invoices/hour. Upgrade for more."}, status=429)

    # ── Parse POST data ──────────────────────────────────────────
    try:
        data = _parse_invoice_data(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    lang   = data.pop("lang", "hr")
    fmt    = request.GET.get("format", "both")

    # ── Compute items + totals ───────────────────────────────────
    raw_items = data.pop("items", [])
    if not raw_items:
        return JsonResponse({"error": "At least one item required."}, status=400)

    try:
        items  = [compute_item(it) for it in raw_items]
        totals = compute_totals(items)
    except Exception as exc:
        logger.warning("Invoice compute error: %s", exc)
        return JsonResponse({"error": f"Item calculation error: {exc}"}, status=400)

    # ── DocumentSeal (evalidator) ────────────────────────────────
    seal_token  = None
    seal_qr_b64 = None
    try:
        from .seal_service import generate_seal, seal_to_qr_base64
        import hashlib
        content_hash = hashlib.sha256(
            f"{data.get('seller_oib','')}{data.get('number','')}{totals['total']}".encode()
        ).hexdigest()
        seal = generate_seal(
            sha256_hash=content_hash,
            arhiva_entry_id=None,
            doc_number=data.get("number"),
            partner_name=data.get("buyer_name"),
            amount=totals["total"],
            currency=data.get("currency", "EUR"),
            issuer_name=data.get("seller_name"),
            issuer_country=data.get("seller_country", "HR"),
        )
        seal_token  = seal.seal_token
        seal_qr_b64 = seal_to_qr_base64(seal)
    except Exception as exc:
        logger.debug("Seal generation skipped: %s", exc)

    filename = make_filename(data)

    # ── Format dispatch ──────────────────────────────────────────
    if fmt == "xml":
        return _xml_response(data, items, totals, filename)
    elif fmt == "pdf":
        return _pdf_response(data, items, totals, lang, filename, seal_token, seal_qr_b64)
    else:
        # "both" → preview page s download linkovima in session
        request.session["ev_inv"] = json.dumps({
            "data":    _serializable(data),
            "items":   _serializable(items),
            "totals":  _serializable(totals),
            "lang":    lang,
            "seal_token": seal_token,
        })
        return render(request, "evalidator/invoice/preview.html", {
            "data":    data,
            "items":   items,
            "totals":  totals,
            "lang":    lang,
            "seal_token":   seal_token,
            "seal_qr_b64":  seal_qr_b64,
            "filename":     filename,
        })


@require_GET
def invoice_download(request):
    """
    GET /invoice/download/?fmt=xml|pdf
    Preuzmi generirani račun iz sessiona.
    """
    inv_json = request.session.get("ev_inv")
    if not inv_json:
        return JsonResponse({"error": "No invoice in session."}, status=404)

    try:
        inv = json.loads(inv_json)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid session data."}, status=400)

    data    = inv["data"]
    items   = [_restore_decimals(it) for it in inv["items"]]
    totals  = _restore_totals(inv["totals"])
    lang    = inv.get("lang", "hr")
    seal_token = inv.get("seal_token")
    filename   = make_filename(data)
    fmt        = request.GET.get("fmt", "pdf")

    seal_qr_b64 = None
    if seal_token:
        try:
            from .models import DocumentSeal
            from .seal_service import seal_to_qr_base64
            seal = DocumentSeal.objects.filter(seal_token=seal_token).first()
            if seal:
                seal_qr_b64 = seal_to_qr_base64(seal)
        except Exception:
            pass

    if fmt == "xml":
        return _xml_response(data, items, totals, filename)
    return _pdf_response(data, items, totals, lang, filename, seal_token, seal_qr_b64)


# ── Helpers ───────────────────────────────────────────────────────────────

def _xml_response(data, items, totals, filename):
    xml_bytes = build_ubl_xml(data, items, totals)
    resp = HttpResponse(xml_bytes, content_type="application/xml; charset=UTF-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}.xml"'
    return resp


def _pdf_response(data, items, totals, lang, filename, seal_token, seal_qr_b64):
    pdf_bytes = build_pdf(data, items, totals, lang=lang,
                          seal_token=seal_token, seal_qr_b64=seal_qr_b64)
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return resp


def _parse_invoice_data(request) -> dict:
    """Parsiraj multipart form ili JSON body u dict."""
    ct = request.content_type or ""
    if "application/json" in ct:
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON body")
    else:
        body = request.POST

    def g(k, default=""):
        v = body.get(k, default)
        return v.strip() if isinstance(v, str) else (v or default)

    today = date.today().isoformat()

    data = {
        "doc_type":        g("doc_type", "INV"),
        "number":          g("number") or f"1/{date.today().year}",
        "issue_date":      g("issue_date") or today,
        "due_date":        g("due_date") or "",
        "currency":        g("currency", "EUR"),
        "payment_method":  g("payment_method", "T"),
        "note":            g("note"),
        "lang":            g("lang", "hr"),

        "seller_name":     g("seller_name"),
        "seller_oib":      g("seller_oib", "").replace(" ", ""),
        "seller_vat_id":   g("seller_vat_id"),
        "seller_address":  g("seller_address"),
        "seller_city":     g("seller_city"),
        "seller_country":  g("seller_country", "HR"),
        "seller_email":    g("seller_email"),
        "seller_iban":     g("seller_iban", "").replace(" ", ""),
        "seller_bic":      g("seller_bic"),

        "buyer_name":      g("buyer_name"),
        "buyer_oib":       g("buyer_oib", "").replace(" ", ""),
        "buyer_address":   g("buyer_address"),
        "buyer_city":      g("buyer_city"),
        "buyer_country":   g("buyer_country", "HR"),
    }

    if not data["seller_name"]:
        raise ValueError("seller_name required")
    if not data["buyer_name"]:
        raise ValueError("buyer_name required")

    # Items — multipart: item_desc_0, item_qty_0, item_price_0, item_tax_0, item_unit_0, item_disc_0
    items = []
    if "application/json" in ct:
        items_raw = body.get("items", [])
        for it in items_raw:
            items.append({
                "description":    str(it.get("description", "")),
                "quantity":       it.get("quantity", 1),
                "unit":           str(it.get("unit", "kom")),
                "unit_price":     it.get("unit_price", 0),
                "discount_percent": it.get("discount_percent", 0),
                "tax_rate":       it.get("tax_rate", 25),
            })
    else:
        idx = 0
        while True:
            desc = g(f"item_desc_{idx}")
            if not desc:
                break
            items.append({
                "description":    desc,
                "quantity":       g(f"item_qty_{idx}", "1"),
                "unit":           g(f"item_unit_{idx}", "kom"),
                "unit_price":     g(f"item_price_{idx}", "0"),
                "discount_percent": g(f"item_disc_{idx}", "0"),
                "tax_rate":       g(f"item_tax_{idx}", "25"),
            })
            idx += 1

    if not items:
        raise ValueError("At least one item required")
    if len(items) > 50:
        raise ValueError("Max 50 items per invoice")

    data["items"] = items
    return data


def _serializable(obj):
    """Convert Decimal→str for JSON serialization."""
    from decimal import Decimal
    if isinstance(obj, dict):
        return {k: _serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serializable(v) for v in obj]
    if isinstance(obj, Decimal):
        return str(obj)
    return obj


def _restore_decimals(item: dict) -> dict:
    from decimal import Decimal
    decimal_keys = {"qty", "price", "disc", "subtotal", "tax_amount", "total", "tax_rate",
                    "unit_price", "quantity", "discount_percent"}
    return {k: Decimal(str(v)) if k in decimal_keys and v is not None else v
            for k, v in item.items()}


def _restore_totals(totals: dict) -> dict:
    from decimal import Decimal
    result = {
        "subtotal":  Decimal(str(totals["subtotal"])),
        "tax_total": Decimal(str(totals["tax_total"])),
        "total":     Decimal(str(totals["total"])),
        "tax_groups": {
            k: {"taxable": Decimal(str(v["taxable"])), "tax": Decimal(str(v["tax"]))}
            for k, v in totals.get("tax_groups", {}).items()
        },
    }
    return result
