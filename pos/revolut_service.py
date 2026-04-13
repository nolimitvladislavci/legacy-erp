"""
Revolut Business Payment Integration za POS.

Flow:
1. POS kreira payment link (Revolut API)
2. Gost otvori link na mobitelu → plati karticom/Apple Pay/Google Pay
3. Revolut šalje webhook → naš server zatvara bon
4. Novac sjeda na Revolut Business račun

Alternativno:
- Revolut Reader (NFC) — fizički čitač
- Revolut Tap to Pay — mobitel kao terminal

Konfiguracija u .env:
  REVOLUT_API_KEY=sk_xxxxx (sandbox: sandbox_xxxxx)
  REVOLUT_MERCHANT_ID=merchant_xxxxx
  REVOLUT_WEBHOOK_SECRET=whsec_xxxxx
  REVOLUT_MODE=sandbox  (ili: production)
"""

import hashlib
import hmac
import logging
import os

import requests

logger = logging.getLogger("pos.revolut")

REVOLUT_API_KEY = os.environ.get("REVOLUT_API_KEY", "")
REVOLUT_MERCHANT_ID = os.environ.get("REVOLUT_MERCHANT_ID", "")
REVOLUT_WEBHOOK_SECRET = os.environ.get("REVOLUT_WEBHOOK_SECRET", "")
REVOLUT_MODE = os.environ.get("REVOLUT_MODE", "sandbox")

BASE_URL = (
    "https://merchant.revolut.com/api/1.0"
    if REVOLUT_MODE == "production"
    else "https://sandbox-merchant.revolut.com/api/1.0"
)


def is_configured():
    """Provjeri je li Revolut konfiguriran."""
    return bool(REVOLUT_API_KEY)


def create_payment_link(receipt, company, callback_url=""):
    """
    Kreira Revolut payment link za POS račun.

    Args:
        receipt: POSReceipt objekt
        company: Company objekt (za naziv i IBAN)
        callback_url: URL na koji se gost vraća nakon plaćanja

    Returns:
        dict: {ok, payment_id, checkout_url, qr_data} ili {ok: False, error}
    """
    if not REVOLUT_API_KEY:
        return {"ok": False, "error": "Revolut API ključ nije konfiguriran"}

    amount_cents = int(receipt.total * 100)  # Revolut radi u centima
    description = "Račun #%s — %s" % (receipt.receipt_number, company.name)

    try:
        resp = requests.post(
            "%s/orders" % BASE_URL,
            headers={
                "Authorization": "Bearer %s" % REVOLUT_API_KEY,
                "Content-Type": "application/json",
                "Revolut-Api-Version": "2024-09-01",
            },
            json={
                "amount": amount_cents,
                "currency": "EUR",
                "description": description[:140],
                "merchant_order_ext_ref": "POS-%d" % receipt.pk,
                "customer_email": "",  # Opcionalno
            },
            timeout=(3, 10),
        )

        if resp.status_code in (200, 201):
            data = resp.json()
            order_id = data.get("id", "")
            # Checkout URL — gost otvori ovaj link
            checkout_url = data.get("checkout_url", "")
            if not checkout_url:
                checkout_url = "https://checkout.revolut.com/pay/%s" % order_id

            return {
                "ok": True,
                "payment_id": order_id,
                "checkout_url": checkout_url,
                "qr_data": checkout_url,  # QR kodira ovaj URL
                "amount": str(receipt.total),
                "currency": "EUR",
            }
        else:
            error = resp.text[:200]
            logger.error("Revolut create order failed: %s %s", resp.status_code, error)
            return {"ok": False, "error": "Revolut greška: %s" % error}

    except requests.Timeout:
        return {"ok": False, "error": "Revolut timeout — pokušajte ponovo"}
    except requests.RequestException as e:
        logger.error("Revolut exception: %s", e)
        return {"ok": False, "error": str(e)}


def check_payment_status(payment_id):
    """
    Provjeri status Revolut plaćanja.

    Returns:
        dict: {status: 'pending'|'completed'|'failed', ...}
    """
    if not REVOLUT_API_KEY:
        return {"status": "error", "error": "Not configured"}

    try:
        resp = requests.get(
            "%s/orders/%s" % (BASE_URL, payment_id),
            headers={
                "Authorization": "Bearer %s" % REVOLUT_API_KEY,
                "Revolut-Api-Version": "2024-09-01",
            },
            timeout=(3, 10),
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "status": data.get("state", "pending").lower(),
                "payment_id": payment_id,
                "amount": data.get("amount", 0) / 100,
                "currency": data.get("currency", "EUR"),
            }
        return {"status": "error", "error": resp.text[:100]}
    except requests.RequestException as e:
        return {"status": "error", "error": str(e)}


def verify_webhook_signature(payload_body, signature_header):
    """Verificiraj Revolut webhook potpis."""
    if not REVOLUT_WEBHOOK_SECRET:
        logger.warning("REVOLUT_WEBHOOK_SECRET not configured — rejecting webhook")
        return False  # Reject unverified webhooks
    expected = hmac.new(
        REVOLUT_WEBHOOK_SECRET.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")
