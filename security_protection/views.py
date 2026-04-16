import json, logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger("fenix.security")

@require_POST
@csrf_exempt
def security_log(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False}, status=400)

    event   = str(data.get("event", "unknown"))[:50]
    user    = str(data.get("user", "anonymous"))[:100]
    company = str(data.get("company", ""))[:100]
    url     = str(data.get("url", ""))[:200]
    ip      = (request.META.get("HTTP_X_FORWARDED_FOR","").split(",")[0].strip()
               or request.META.get("REMOTE_ADDR",""))

    logger.warning("SECURITY | %-25s | user=%-30s | company=%-20s | ip=%s | url=%s",
                   event, user, company, ip, url)

    CRITICAL = {"copy_blocked","print_blocked","screenshot_suspected","printscreen_key"}
    if event in CRITICAL:
        logger.error("SECURITY_CRITICAL | %s | user=%s | company=%s | ip=%s",
                     event, user, company, ip)

    return JsonResponse({"ok": True})
