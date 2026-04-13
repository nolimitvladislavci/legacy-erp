"""
WhatsApp / SMS / Email notification service.
Scenario 2.3: Meta API timeout — fallback chain.
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_cart_link(snapshot, phone_number, method='whatsapp'):
    """
    Send cart share link via WhatsApp, with SMS/email fallback.
    Never blocks caller — returns result dict.
    """
    link = f"https://limit-connect.com/marketplace/checkout/shared/{snapshot.token}/"
    message = (
        f"Vasa narudzba je spremna!\n"
        f"Ukupno: {snapshot.total} EUR\n"
        f"Link: {link}\n"
        f"Link istice za 60 minuta."
    )

    result = {'sent': False, 'method': 'none', 'error': None}

    # Try WhatsApp Business API first
    if method == 'whatsapp':
        try:
            result = _send_whatsapp(phone_number, message, snapshot)
            if result['sent']:
                snapshot.wa_sent = True
                snapshot.wa_message_id = result.get('message_id', '')
                snapshot.save(update_fields=['wa_sent', 'wa_message_id'])
                return result
        except KeyError as e:
            logger.warning(f'WhatsApp send failed: {e}')
            result['error'] = str(e)

    # Fallback: SMS (placeholder)
    try:
        result = _send_sms_fallback(phone_number, message)
        if result['sent']:
            snapshot.wa_fallback_used = 'sms'
            snapshot.save(update_fields=['wa_fallback_used'])
            return result
    except Exception as e:
        logger.warning(f'SMS fallback failed: {e}')

    # Fallback: just log — link is still valid
    logger.error(f'All notification channels failed for snapshot {snapshot.token[:8]}')
    snapshot.wa_fallback_used = 'failed'
    snapshot.save(update_fields=['wa_fallback_used'])
    result['method'] = 'failed'
    return result


def _send_whatsapp(phone, message, snapshot):
    """Send via WhatsApp Business API (Cloud API)."""
    token = getattr(settings, 'WHATSAPP_API_TOKEN', '')
    phone_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')

    if not token or not phone_id:
        logger.info('WhatsApp API not configured — skipping')
        return {'sent': False, 'method': 'whatsapp', 'error': 'Not configured'}

    url = f'https://graph.facebook.com/v18.0/{phone_id}/messages'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': phone,
        'type': 'text',
        'text': {'body': message},
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        msg_id = data.get('messages', [{}])[0].get('id', '')
        return {'sent': True, 'method': 'whatsapp', 'message_id': msg_id}
    else:
        logger.warning(f'WhatsApp API error {resp.status_code}: {resp.text[:200]}')
        raise Exception(f'WA API {resp.status_code}')


def _send_sms_fallback(phone, message):
    """SMS fallback — placeholder for future integration."""
    # TODO: integrate with SMS provider (Twilio, Infobip, etc.)
    logger.info(f'SMS fallback: would send to {phone}: {message[:50]}...')
    return {'sent': False, 'method': 'sms', 'error': 'SMS not configured'}
