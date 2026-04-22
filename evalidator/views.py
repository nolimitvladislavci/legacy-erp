"""
evalidator/views.py — V2 sa novinama:
1. Batch OIB/IBAN validacija (CSV/textarea → JSON rezultati)
2. VIES live check — naziv firme + adresa iz EU VIES REST API
3. OIB → naziv firme (Sudski registar javni API)
4. Redis live counter (HyperLogLog unique IP + dnevni count)
5. eArhivator CTA
"""
import hashlib
import json
import time
import logging

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.oib_validator import validate_iban, validate_oib_hr, validate_vat_id

logger = logging.getLogger("fenix.evalidator")

# Redis prefix — fina-connect koristi db1, prefix ev:
_RP = "ev:"


def _redis():
    """Direktni Redis klijent za HyperLogLog i counters."""
    try:
        import redis as redis_lib
        return redis_lib.from_url("redis://127.0.0.1:6379/1")
    except Exception:
        return None


def _log(vtype, value, valid, api=False, ms=0, ip=None):
    """Bilježi validaciju u DB + Redis live counter."""
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
    # Redis live counter
    try:
        from datetime import date
        r = _redis()
        if r:
            today = date.today().isoformat()
            r.incr(_RP + "cnt:total")
            r.incr(_RP + "cnt:today:" + today)
            r.expire(_RP + "cnt:today:" + today, 86400 * 2)
            if ip:
                r.pfadd(_RP + "hll:ips:" + today, ip)
                r.expire(_RP + "hll:ips:" + today, 86400 * 2)
    except Exception:
        pass


def _live_stats():
    """Dohvati live stats iz Redisa (fallback na DB cache)."""
    try:
        from datetime import date
        r = _redis()
        if r:
            today = date.today().isoformat()
            total = int(r.get(_RP + "cnt:total") or 0)
            today_cnt = int(r.get(_RP + "cnt:today:" + today) or 0)
            unique_ips = r.pfcount(_RP + "hll:ips:" + today)
            if total > 0:
                return {"total": total, "today": today_cnt, "unique_ips": unique_ips}
    except Exception:
        pass
    # Fallback: DB cache
    stats = cache.get("ev_stats") or {}
    if not stats:
        from evalidator.models import ValidationLog
        from django.utils import timezone
        stats = {
            "total": ValidationLog.objects.count(),
            "today": ValidationLog.objects.filter(created_at__date=timezone.now().date()).count(),
            "unique_ips": 0,
        }
        cache.set("ev_stats", stats, 60)
    return stats


def _rate_ok(request):
    ip = request.META.get("REMOTE_ADDR", "x")
    key = "ev_rate:" + ip
    n = cache.get(key, 0)
    if n >= 30:
        return False
    cache.set(key, n + 1, 60)
    return True


def _vies_lookup(country_code: str, vat_number: str) -> dict:
    """
    VIES EU REST API lookup.
    Returns: {valid, name, address, vies_checked}
    Timeout 4s, fallback graceful.
    """
    try:
        import requests
        cc = country_code.upper().strip()
        vn = vat_number.upper().replace(cc, "").strip()
        url = f"https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{cc}/vat/{vn}"
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "vies_checked": True,
                "vies_valid": data.get("isValid", False),
                "vies_name": data.get("name") or "",
                "vies_address": data.get("address") or "",
            }
    except Exception as exc:
        logger.debug("VIES lookup failed: %s", exc)
    return {"vies_checked": False}


def _sudreg_lookup(oib: str) -> dict:
    """
    Sudski registar — javni API za naziv firme po OIB-u.
    Returns: {found, name, mbs, status, address}
    """
    cache_key = "ev:sudreg:" + oib
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        import requests
        url = "https://sudreg-api.pravosudje.hr/javni/subjekt_detalji"
        resp = requests.get(
            url,
            params={"tipSubjekta": "d", "oib": oib},
            headers={"Accept": "application/json"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            result = {
                "found": True,
                "name": data.get("naziv") or data.get("ime") or "",
                "mbs": str(data.get("mbs") or ""),
                "status": data.get("stanje_subjekta", {}).get("naziv") or "",
                "address": data.get("sjediste", {}).get("ulica_kbr") or "",
            }
            cache.set(cache_key, result, 86400)
            return result
    except Exception as exc:
        logger.debug("Sudreg lookup failed for OIB %s: %s", oib, exc)
    result = {"found": False}
    cache.set(cache_key, result, 300)
    return result


@require_GET
def landing(request):
    stats = _live_stats()
    return render(request, "evalidator/landing.html", {"stats": stats})


@csrf_exempt
@require_POST
def validate_oib(request):
    t0 = time.monotonic()
    ip = request.META.get("REMOTE_ADDR", "")
    oib = request.POST.get("oib", "").strip().replace(" ", "")
    r = {"oib": oib, "valid": False, "message": "", "suggestion": "", "company": None}
    if len(oib) == 11 and oib.isdigit():
        if validate_oib_hr(oib):
            r.update(valid=True, message="OIB je ispravan ✓")
            # Company lookup (async-style — non-blocking, cached)
            company = _sudreg_lookup(oib)
            if company.get("found"):
                r["company"] = company
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
        _log("oib_hr", oib, r["valid"], ms=int((time.monotonic() - t0) * 1000), ip=ip)
    return render(request, "evalidator/partials/result.html", r)


@csrf_exempt
@require_POST
def validate_iban_view(request):
    t0 = time.monotonic()
    ip = request.META.get("REMOTE_ADDR", "")
    iban = request.POST.get("iban", "").strip().replace(" ", "").upper()
    r = {"iban": iban, "valid": False, "message": ""}
    if iban:
        if validate_iban(iban):
            r.update(valid=True, message=f"IBAN je ispravan ({iban[:2]}) ✓")
        else:
            r["message"] = "IBAN nije ispravan (MOD 97 provjera)"
    if iban:
        _log("iban", iban, r["valid"], ms=int((time.monotonic() - t0) * 1000), ip=ip)
    return render(request, "evalidator/partials/result.html", r)


@csrf_exempt
@require_POST
def validate_vat_view(request):
    t0 = time.monotonic()
    ip = request.META.get("REMOTE_ADDR", "")
    vat = request.POST.get("vat", "").strip().upper()
    country = (request.POST.get("country", "") or vat[:2]).upper()
    r = {"vat": vat, "valid": False, "message": "", "country": country, "vies": None}
    if vat:
        local_valid = validate_vat_id(vat, country)
        if local_valid:
            r.update(valid=True, message=f"VAT ID ispravan ({country}) ✓")
            # VIES live check
            vies = _vies_lookup(country, vat)
            if vies.get("vies_checked"):
                r["vies"] = vies
                if vies.get("vies_name"):
                    r["message"] = f"VAT ID ispravan · {vies['vies_name']} ✓"
        else:
            r["message"] = f"VAT ID nije ispravan za {country}"
    if vat:
        _log("vat_eu", vat, r["valid"], ms=int((time.monotonic() - t0) * 1000), ip=ip)
    return render(request, "evalidator/partials/result.html", r)


@csrf_exempt
@require_POST
def validate_company(request):
    """
    POST validate/company/
    OIB → naziv firme, MBS, status (Sudski registar).
    """
    oib = request.POST.get("oib", "").strip().replace(" ", "")
    r = {"oib": oib, "valid": False, "message": "", "company": None}
    if len(oib) == 11 and oib.isdigit():
        if validate_oib_hr(oib):
            r["valid"] = True
            company = _sudreg_lookup(oib)
            r["company"] = company
            if company.get("found"):
                r["message"] = f"Firma pronađena: {company['name']} ✓"
            else:
                r["message"] = "OIB ispravan, firma nije u Sudskom registru (fizička osoba ili obrt)"
        else:
            r["message"] = "OIB nije ispravan (ISO 7064 MOD 11,10)"
    elif oib:
        r["message"] = f"OIB mora imati 11 znamenki (uneseno: {len(oib)})"
    return render(request, "evalidator/partials/result_company.html", r)


@csrf_exempt
def api_batch(request):
    """
    POST /api/v1/batch/
    Body: {"items": [{"type": "oib", "value": "12345678901"}, ...]}
    Max 100 stavki po zahtjevu.
    """
    if not _rate_ok(request):
        return JsonResponse({"error": "Rate limit exceeded"}, status=429)

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    items = body.get("items") or []
    if not isinstance(items, list):
        return JsonResponse({"error": "items must be array"}, status=400)
    if len(items) > 100:
        return JsonResponse({"error": "Max 100 items per request", "upgrade": "/pricing/"}, status=400)

    results = []
    for item in items:
        val_type = str(item.get("type", "oib")).lower()
        value = str(item.get("value", "")).strip().replace(" ", "")
        result = {"type": val_type, "value": value, "valid": False, "message": ""}

        if val_type == "oib":
            if len(value) == 11 and value.isdigit():
                valid = validate_oib_hr(value)
                result["valid"] = valid
                result["message"] = "valid" if valid else "invalid checksum"
            else:
                result["message"] = f"must be 11 digits (got {len(value)})"

        elif val_type == "iban":
            value_upper = value.upper()
            valid = validate_iban(value_upper) if value_upper else False
            result["valid"] = valid
            result["value"] = value_upper
            result["message"] = "valid" if valid else "invalid (MOD 97)"

        elif val_type == "vat":
            country = str(item.get("country", value[:2])).upper()
            valid = validate_vat_id(value.upper(), country)
            result["valid"] = valid
            result["country"] = country
            result["message"] = "valid" if valid else f"invalid for {country}"

        else:
            result["message"] = f"unknown type: {val_type}"

        results.append(result)

    valid_count = sum(1 for r in results if r["valid"])
    _log("batch", str(len(items)), True, api=True, ip=request.META.get("REMOTE_ADDR", ""))

    return JsonResponse({
        "count": len(results),
        "valid": valid_count,
        "invalid": len(results) - valid_count,
        "results": results,
    })


@csrf_exempt
def api_oib(request):
    if not _rate_ok(request):
        return JsonResponse({"error": "Rate limit", "upgrade": "https://evalidator.eu/pricing/"}, status=429)
    oib = (
        request.GET.get("oib")
        or (json.loads(request.body or b"{}").get("oib", "") if request.method == "POST" else "")
    ).strip()
    if not oib:
        return JsonResponse({"error": "Missing oib"}, status=400)
    valid = validate_oib_hr(oib)
    _log("oib_hr", oib, valid, api=True, ip=request.META.get("REMOTE_ADDR", ""))
    resp = {"oib": oib, "valid": valid, "algorithm": "ISO 7064 MOD 11,10", "country": "HR"}
    if valid and request.GET.get("company") == "1":
        company = _sudreg_lookup(oib)
        if company.get("found"):
            resp["company"] = {"name": company["name"], "mbs": company["mbs"], "status": company["status"]}
    return JsonResponse(resp)


@require_GET
def api_docs(request):
    return render(request, "evalidator/docs.html")


@require_GET
def pricing(request):
    return render(request, "evalidator/pricing.html")


def _resolve_api_key(request):
    raw = (request.META.get("HTTP_X_API_KEY") or request.GET.get("api_key") or "").strip()
    if not raw:
        return None
    from evalidator.models import APIKey
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return APIKey.objects.filter(key_hash=key_hash, is_active=True).first()


@csrf_exempt
@require_GET
def api_status(request):
    from django.utils import timezone
    now = timezone.now()
    stats = _live_stats()
    payload = {
        "status": "ok",
        "service": "evalidator.eu",
        "version": "2.0",
        "timestamp": now.isoformat(),
        "stats": {"total_validations": stats.get("total", 0), "today": stats.get("today", 0)},
        "endpoints": {
            "oib": "/api/v1/oib/?oib=",
            "oib_with_company": "/api/v1/oib/?oib=&company=1",
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


@require_GET
def verify_seal(request, seal_token: str):
    from evalidator.models import DocumentSeal
    from evalidator.seal_service import record_verify, seal_to_qr_base64

    token = seal_token.upper().strip()
    seal = DocumentSeal.objects.filter(seal_token=token).first()
    ctx = {"token": token, "seal": None, "found": False, "valid": False, "qr_data_uri": ""}
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
    from evalidator.models import DocumentSeal
    from evalidator.seal_service import record_verify

    token = seal_token.upper().strip()
    seal = DocumentSeal.objects.filter(seal_token=token).first()
    if not seal:
        return JsonResponse({"verified": False, "token": token, "error": "Pečat nije pronađen"}, status=404)
    record_verify(token, request)
    return JsonResponse({
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
    })
