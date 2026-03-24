"""
FenixSignal views — AJAX endpoint za "Prijavi grešku" gumb.

Rate-limited: max 10 signala po korisniku/IP u 5 minuta.
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.cache import cache

from limit_connect_ai.models_signal import FenixSignal

logger = logging.getLogger("borg.signal")


def _check_rate_limit(identifier, limit=10, window=300):
    """Max 10 signala po identifikatoru u 5 min."""
    key = f"fenix_signal_rl:{identifier}"
    count = cache.get(key, 0)
    if count >= limit:
        return False
    cache.set(key, count + 1, window)
    return True


def _get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")


@csrf_exempt
@require_POST
def submit_signal(request):
    """
    POST /api/borg/signal/

    Body (JSON):
    {
        "type": "bug|confusion|suggestion|ai_bad|urgent",
        "message": "Opis problema...",
        "page_url": "/pos/terminal/1/",
        "context": {"terminal_id": 1}  // optional
    }

    Autentificirani korisnici: user + company automatski.
    Neautentificirani: anonimni signal (za POS kiosk, guest pages).
    """
    ip = _get_ip(request)
    identifier = str(request.user.id) if request.user.is_authenticated else ip

    if not _check_rate_limit(identifier):
        return JsonResponse(
            {"ok": False, "error": "Previše signala. Pričekaj 5 minuta."},
            status=429,
        )

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    message = data.get("message", "").strip()
    if not message:
        return JsonResponse({"ok": False, "error": "Poruka je obavezna"}, status=400)

    if len(message) > 2000:
        message = message[:2000]

    signal_type = data.get("type", "bug")
    if signal_type not in dict(FenixSignal.SignalType.choices):
        signal_type = "bug"

    # Get company from user
    company = None
    user = None
    if request.user.is_authenticated:
        user = request.user
        try:
            from core.company_utils import get_user_company
            company = get_user_company(request)
        except Exception:
            pass

    signal = FenixSignal.objects.create(
        user=user,
        company=company,
        signal_type=signal_type,
        source=FenixSignal.Source.IN_APP,
        message=message,
        page_url=data.get("page_url", "")[:500],
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        screen_width=data.get("screen_width"),
        context=data.get("context", {}),
        ip_address=ip,
    )

    logger.info(
        "FenixSignal %s: [%s] %s — %s",
        signal.id, signal_type, message[:80],
        user or ip,
    )

    # FAZA 2: Haiku AI triage — async, ne blokira response
    try:
        from limit_connect_ai.tasks_signal import triage_new_signal
        triage_new_signal.delay(str(signal.id))
    except Exception:
        pass  # Triage failure ne smije blokirati signal

    return JsonResponse({
        "ok": True,
        "signal_id": str(signal.id),
        "message": "Hvala! Signal primljen. BORG analizira...",
    })
