"""Webhook endpoint for posrednik status callbacks."""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from einvoice.services.webhook_receiver import verify_webhook_signature, process_webhook_payload

logger = logging.getLogger("propter.einvoice.webhook")


# CSRF exempt: external webhook — no browser session
@csrf_exempt
@require_POST
def posrednik_webhook(request):
    """
    POST /api/einvoice/webhook/posrednik/

    Receives status updates from FINA posrednik.
    Secured with HMAC-SHA256 signature verification.
    """
    # Step 1: Verify signature
    signature = request.headers.get("X-Webhook-Signature", "")
    if not verify_webhook_signature(request.body, signature):
        logger.warning(f"Webhook signature verification failed from {request.META.get('REMOTE_ADDR')}")
        return JsonResponse({"error": "Invalid signature"}, status=401)

    # Step 2: Parse payload
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Step 3: Process
    result = process_webhook_payload(payload)

    status_code = 200 if result.get("processed") else 202
    return JsonResponse(result, status=status_code)
