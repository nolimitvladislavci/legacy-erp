"""
core/qr_verify_views.py — Javna QR verifikacijska stranica

/qr/<token>/    — puni token (32-hex)
/qr/s/<short>/  — shortlink (8-char)

Bez logina. Radi za sve objekte iz QR Registry.
Bilježi sken (honeypot), prikazuje VC, viral CTA.
"""

import logging

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger("fenix.qr_registry")

VIRAL_REGISTER_URL = "https://fina-connect.online/hr/accounts/register/?ref={viral_code}&utm_source=qr&utm_medium=scan"


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()[:45]
    return request.META.get("REMOTE_ADDR", "")[:45]


def _record_scan_async(qr_token, request) -> None:
    """Bilježi sken asinkrono (da ne usporava response)."""
    try:
        from core.qr_registry_models import QRScanLog

        ip = _client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")[:300]
        ref = request.META.get("HTTP_REFERER", "")[:500]

        QRScanLog.objects.create(
            qr_token=qr_token,
            ip_address=ip if ip else None,
            user_agent=ua,
            referrer=ref,
        )
        qr_token.record_scan(ip=ip, ua=ua)
    except Exception as e:
        logger.warning("QR scan log failed: %s", e)


@require_GET
@never_cache
def qr_verify(request, token: str):
    """
    Javna verifikacijska stranica za QR token (puni 32-hex).
    """
    from core.qr_registry_models import QRToken

    qr = get_object_or_404(QRToken, token=token, is_active=True)

    if qr.is_expired:
        return render(request, "core/qr_expired.html", {"qr": qr}, status=410)

    _record_scan_async(qr, request)

    # Dohvati detalje objekta ako postoji view dispatcher
    object_detail = _fetch_object_detail(qr)

    viral_url = ""
    if qr.viral_code:
        viral_url = VIRAL_REGISTER_URL.format(viral_code=qr.viral_code)

    return render(
        request,
        "core/qr_verify.html",
        {
            "qr": qr,
            "object_detail": object_detail,
            "viral_url": viral_url,
            "vc_payload": qr.vc_payload,
        },
    )


@require_GET
@never_cache
def qr_verify_short(request, short: str):
    """Shortlink redirect → puni verify URL."""
    from core.qr_registry_models import QRToken

    try:
        qr = QRToken.objects.only("token", "is_active").get(short=short, is_active=True)
    except QRToken.DoesNotExist:
        raise Http404
    return redirect(f"/qr/{qr.token}/", permanent=False)


@require_GET
def qr_api_status(request, token: str):
    """
    JSON API — za mobilne skenerske appove i offline VC verifikaciju.
    Vraća VC payload + status bez HTML-a.
    """
    from core.qr_registry_models import QRToken

    try:
        qr = QRToken.objects.get(token=token, is_active=True)
    except QRToken.DoesNotExist:
        return JsonResponse({"valid": False, "error": "not_found"}, status=404)

    return JsonResponse(
        {
            "valid": True,
            "expired": qr.is_expired,
            "token": qr.token,
            "short": qr.short,
            "object_type": qr.object_type,
            "label": qr.label,
            "company": qr.company_name,
            "created_at": qr.created_at.isoformat(),
            "scan_count": qr.scan_count,
            "tamper": qr.tamper_flag,
            "vc": qr.vc_payload,
        }
    )


def _fetch_object_detail(qr) -> dict:
    """
    Pokušaj dohvatiti detalje objekta za prikaz na verify stranici.
    Svaki dispatcher vraća dict s ključevima: type, title, date, amount, url.
    Failsafe: ako ne uspije, vrati prazan dict.
    """
    try:
        dispatcher = _DISPATCHERS.get(qr.object_type)
        if dispatcher:
            return dispatcher(qr.object_ref)
    except Exception as e:
        logger.debug("object detail fetch failed for %s:%s — %s", qr.object_type, qr.object_ref, e)
    return {}


def _detail_arhiva(ref: str) -> dict:
    from documents.models import ArhivaEntry

    e = ArhivaEntry.objects.select_related("company").get(id=ref)
    return {
        "type": "Arhiva dokument",
        "title": e.title,
        "date": str(e.document_date or ""),
        "company": getattr(e.company, "name", ""),
        "hash": e.layer1_sha256 or "",
    }


def _detail_invoice(ref: str) -> dict:
    from invoicing.models import Invoice

    inv = Invoice.objects.select_related("company").get(pk=ref)
    return {
        "type": "Račun",
        "title": getattr(inv, "invoice_number", f"#{ref}"),
        "date": str(getattr(inv, "issue_date", "") or ""),
        "amount": str(getattr(inv, "total_amount", "") or ""),
        "company": getattr(inv.company, "name", ""),
    }


def _detail_pos_receipt(ref: str) -> dict:
    from pos.models import Receipt

    r = Receipt.objects.get(pk=ref)
    return {
        "type": "POS blagajnički isječak",
        "title": f"POS #{r.pk}",
        "date": str(getattr(r, "created_at", "")[:10] if hasattr(r, "created_at") else ""),
        "amount": str(getattr(r, "total", "") or ""),
    }


_DISPATCHERS = {
    "arhiva.entry": _detail_arhiva,
    "invoicing.invoice": _detail_invoice,
    "pos.receipt": _detail_pos_receipt,
}
