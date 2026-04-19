import hashlib
import json
import time

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.oib_validator import validate_iban, validate_oib_hr, validate_vat_id


def _log(vtype, value, valid, api=False, ms=0):
    try:
        from evalidator.models import ValidationLog

        ValidationLog.objects.create(
            validation_type=vtype,
            input_hash=hashlib.sha256(value.encode()).hexdigest(),
            is_valid=valid,
            is_api_call=api,
            response_ms=ms,
        )
    except Exception:
        pass


def _rate_ok(request):
    from django.core.cache import cache

    ip = request.META.get("REMOTE_ADDR", "x")
    key = f"ev_rate:{ip}"
    n = cache.get(key, 0)
    if n >= 30:
        return False
    cache.set(key, n + 1, 60)
    return True


@require_GET
def landing(request):
    from django.core.cache import cache

    from evalidator.models import ValidationLog

    stats = cache.get("ev_stats") or {}
    if not stats:
        from django.utils import timezone

        stats = {
            "total": ValidationLog.objects.count(),
            "today": ValidationLog.objects.filter(created_at__date=timezone.now().date()).count(),
        }
        cache.set("ev_stats", stats, 300)
    return render(request, "evalidator/landing.html", {"stats": stats})


@csrf_exempt
@require_POST
def validate_oib(request):
    t0 = time.monotonic()
    oib = request.POST.get("oib", "").strip().replace(" ", "")
    r = {"oib": oib, "valid": False, "message": "", "suggestion": ""}
    if len(oib) == 11 and oib.isdigit():
        if validate_oib_hr(oib):
            r.update(valid=True, message="OIB je ispravan ✓")
        else:
            r["message"] = "Kontrolna znamenka ne odgovara (ISO 7064 MOD 11,10)"
            for i in range(10):
                c = oib[:10] + str(i)
                if validate_oib_hr(c):
                    r["suggestion"] = f"Možda: {c}?"
                    break
    elif oib:
        r["message"] = f"OIB mora imati 11 znamenki (uneseno: {len(oib)})"
    if oib:
        _log("oib_hr", oib, r["valid"], ms=int((time.monotonic() - t0) * 1000))
    return render(request, "evalidator/partials/result.html", r)


@csrf_exempt
@require_POST
def validate_iban_view(request):
    t0 = time.monotonic()
    iban = request.POST.get("iban", "").strip().replace(" ", "").upper()
    r = {"iban": iban, "valid": False, "message": ""}
    if iban:
        if validate_iban(iban):
            r.update(valid=True, message=f"IBAN je ispravan ({iban[:2]}) ✓")
        else:
            r["message"] = "IBAN nije ispravan (MOD 97 provjera)"
    if iban:
        _log("iban", iban, r["valid"], ms=int((time.monotonic() - t0) * 1000))
    return render(request, "evalidator/partials/result.html", r)


@csrf_exempt
@require_POST
def validate_vat_view(request):
    t0 = time.monotonic()
    vat = request.POST.get("vat", "").strip().upper()
    country = (request.POST.get("country", "") or vat[:2]).upper()
    r = {"vat": vat, "valid": False, "message": "", "country": country}
    if vat:
        if validate_vat_id(vat, country):
            r.update(valid=True, message=f"VAT ID ispravan ({country}) ✓")
        else:
            r["message"] = f"VAT ID nije ispravan za {country}"
    if vat:
        _log("vat_eu", vat, r["valid"], ms=int((time.monotonic() - t0) * 1000))
    return render(request, "evalidator/partials/result.html", r)


@csrf_exempt
def api_oib(request):
    if not _rate_ok(request):
        return JsonResponse({"error": "Rate limit", "upgrade": "https://evalidator.eu/pricing/"}, status=429)
    oib = (
        request.GET.get("oib") or (json.loads(request.body or b"{}").get("oib", "") if request.method == "POST" else "")
    ).strip()
    if not oib:
        return JsonResponse({"error": "Missing oib"}, status=400)
    valid = validate_oib_hr(oib)
    _log("oib_hr", oib, valid, api=True)
    return JsonResponse({"oib": oib, "valid": valid, "algorithm": "ISO 7064 MOD 11,10", "country": "HR"})


@require_GET
def api_docs(request):
    return render(request, "evalidator/docs.html")


@require_GET
def pricing(request):
    return render(request, "evalidator/pricing.html")


@csrf_exempt
def api_batch(request):
    return JsonResponse({"status": "coming_soon", "eta": "Q3 2026", "contact": "api@evalidator.eu"}, status=501)


def _resolve_api_key(request):
    """Vrati APIKey objekt ili None. Prihvaća X-API-Key header i ?api_key= param."""
    raw = (request.META.get("HTTP_X_API_KEY") or request.GET.get("api_key") or "").strip()
    if not raw:
        return None
    from evalidator.models import APIKey

    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return APIKey.objects.filter(key_hash=key_hash, is_active=True).first()


@csrf_exempt
@require_GET
def api_status(request):
    """
    GET /api/status/
    Javno: vraća verziju i health bez ključa.
    S ključem: dodaje plan, kvotu i usage.
    """
    from django.utils import timezone

    now = timezone.now()
    payload = {
        "status": "ok",
        "service": "evalidator.eu",
        "version": "1.1",
        "timestamp": now.isoformat(),
        "endpoints": {
            "oib": "/api/v1/oib/",
            "batch": "/api/v1/batch/",
            "docs": "/docs/",
            "verify_seal": "/api/v1/verify/<token>/",
        },
    }
    api_key_obj = _resolve_api_key(request)
    if api_key_obj:
        payload["authenticated"] = True
        payload["plan"] = api_key_obj.plan
        payload["daily_limit"] = api_key_obj.daily_limit
        payload["daily_used"] = api_key_obj.daily_used
        payload["daily_remaining"] = max(0, api_key_obj.daily_limit - api_key_obj.daily_used)
    else:
        payload["authenticated"] = False
        payload["note"] = "Pass X-API-Key header for quota info"
    return JsonResponse(payload)


# ═══════════════════════════════════════════════════════
# DOCUMENT SEAL — Verifikacija pečata vjerodostojnosti
# ═══════════════════════════════════════════════════════


@require_GET
def verify_seal(request, seal_token: str):
    """
    GET /evalidator/verify/<seal_token>/

    Javna stranica verifikacije dokumenta.
    Prikazuje: status autentičnosti, metapodatke, QR (za re-scan), CTA.

    Zakonski okvir: eIDAS Art. 41 — electronic timestamp presumption of integrity.
    """
    from evalidator.models import DocumentSeal
    from evalidator.seal_service import record_verify, seal_to_qr_base64

    token = seal_token.upper().strip()
    seal = DocumentSeal.objects.filter(seal_token=token).first()

    ctx = {
        "token": token,
        "seal": None,
        "found": False,
        "valid": False,
        "qr_data_uri": "",
    }

    if seal:
        ctx["found"] = True
        ctx["valid"] = seal.is_valid
        ctx["seal"] = seal
        try:
            ctx["qr_data_uri"] = seal_to_qr_base64(seal)
        except Exception:
            pass
        record_verify(token, request)

    return render(request, "evalidator/verify_seal.html", ctx)


@require_GET
def api_verify_seal(request, seal_token: str):
    """
    GET /evalidator/api/v1/verify/<token>/

    JSON verifikacija pečata za strojno čitanje (DATEV BelegLink, ERP integracija).
    """
    from evalidator.models import DocumentSeal
    from evalidator.seal_service import record_verify

    token = seal_token.upper().strip()
    seal = DocumentSeal.objects.filter(seal_token=token).first()

    if not seal:
        return JsonResponse({"verified": False, "token": token, "error": "Pečat nije pronađen"}, status=404)

    record_verify(token, request)

    return JsonResponse(
        {
            "verified": True,
            "valid": seal.is_valid,
            "token": seal.seal_token,
            "sha256": seal.sha256_hash,
            "doc_number": seal.doc_number,
            "doc_date": seal.doc_date.isoformat() if seal.doc_date else None,
            "partner": seal.partner_name,
            "amount": float(seal.amount) if seal.amount else None,
            "currency": seal.currency,
            "issuer": seal.issuer_name,
            "issuer_country": seal.issuer_country,
            "sealed_at": seal.sealed_at.isoformat(),
            "expires_at": seal.expires_at.isoformat() if seal.expires_at else None,
            "verify_url": seal.verify_url,
            "legal_basis": "eIDAS Art. 41 — electronic timestamp",
        }
    )
