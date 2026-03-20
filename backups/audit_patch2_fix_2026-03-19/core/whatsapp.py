"""
Centralized WhatsApp service via WAHA gateway.
Mirrors core/email_tasks.py pattern for async messaging.
"""
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger('whatsapp')


def normalize_phone(phone):
    """Normalize phone number to international format for WhatsApp.

    Handles:
    - German mobiles: +49 / 0049 / 049 prefix
    - Croatian mobiles: +385 / 00385 / 091-099 local
    - Already-international numbers
    Returns '' for empty/invalid input.
    """
    if not phone:
        return ''

    # Strip all non-digit characters except leading +
    cleaned = phone.strip()
    has_plus = cleaned.startswith('+')
    digits = re.sub(r'\D', '', cleaned)

    if not digits:
        return ''

    # If had a + prefix, it's already international
    if has_plus:
        # Validate length (country code + number = 10-15 digits)
        if 10 <= len(digits) <= 15:
            return digits
        return ''

    # 00-prefix international (e.g. 004917..., 00385...)
    if digits.startswith('00') and len(digits) >= 12:
        intl = digits[2:]
        if 10 <= len(intl) <= 15:
            return intl
        return ''

    # Croatian local (091..., 092..., 095..., 097..., 098..., 099...)
    # Must come before German local check since 09x also starts with 0
    if digits.startswith('09') and 9 <= len(digits) <= 10:
        intl = '385' + digits[1:]
        if 10 <= len(intl) <= 15:
            return intl
        return ''

    # German local (0171..., 0151..., 030...) → prepend 49
    if digits.startswith('0') and 10 <= len(digits) <= 12:
        intl = '49' + digits[1:]
        if 10 <= len(intl) <= 15:
            return intl
        return ''

    # Already international without prefix (e.g. 491711234567)
    if 10 <= len(digits) <= 15:
        return digits

    return ''


def is_gateway_healthy():
    """Check if WAHA gateway is running and session is active.

    Returns True if session status is WORKING, False otherwise.
    """
    if not getattr(settings, 'WAHA_ENABLED', False):
        return False

    try:
        url = f"{settings.WAHA_API_URL}/api/sessions"
        headers = {}
        api_key = getattr(settings, 'WAHA_API_KEY', '')
        if api_key:
            headers['X-Api-Key'] = api_key
        resp = requests.get(url, timeout=5, headers=headers)
        if resp.status_code != 200:
            return False
        sessions = resp.json()
        session_name = getattr(settings, 'WAHA_SESSION_NAME', 'default')
        for s in sessions:
            if s.get('name') == session_name and s.get('status') == 'WORKING':
                return True
        return False
    except (requests.ConnectionError, requests.Timeout, Exception) as e:
        logger.warning('WAHA health check failed: %s', e)
        return False


def _wa_rate_ok(daily_limit=500):
    """Redis daily rate limit za WhatsApp poruke (globalni)."""
    try:
        import redis
        from datetime import date
        r = redis.Redis.from_url(getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'))
        key = 'wa_global:%s' % date.today().isoformat()
        count = r.incr(key)
        r.expire(key, 86400)
        if count > daily_limit:
            logger.warning('WhatsApp daily limit reached: %d/%d', count, daily_limit)
            return False
        return True
    except Exception:
        return True


# ── Per-company & per-phone rate limits ──────────────────
WHATSAPP_DAILY_LIMIT_PER_COMPANY = 200
WHATSAPP_HOURLY_LIMIT_PER_PHONE = 5

def _whatsapp_rate_check(company_id=None, phone=None):
    """Check per-company/per-phone WhatsApp rate limits via Redis."""
    try:
        from django.core.cache import cache
        from django.utils import timezone
        today = timezone.now().strftime('%Y-%m-%d')
        hour = timezone.now().strftime('%Y-%m-%d-%H')
        if company_id:
            key = f'wha_co:{company_id}:{today}'
            count = cache.get(key, 0)
            if count >= WHATSAPP_DAILY_LIMIT_PER_COMPANY:
                logger.warning('WhatsApp daily limit for company %s: %d', company_id, count)
                return False, f'Dnevni limit ({WHATSAPP_DAILY_LIMIT_PER_COMPANY}) za firmu dosegnut'
        if phone:
            key = f'wha_ph:{phone}:{hour}'
            count = cache.get(key, 0)
            if count >= WHATSAPP_HOURLY_LIMIT_PER_PHONE:
                logger.warning('WhatsApp hourly limit for phone %s***', phone[:6])
                return False, f'Satni limit ({WHATSAPP_HOURLY_LIMIT_PER_PHONE}) za broj dosegnut'
        return True, ''
    except Exception as e:
        logger.warning('WhatsApp rate check error (allowing): %s', e)
        return True, ''

def _whatsapp_rate_increment(company_id=None, phone=None):
    """Increment rate counters after successful send."""
    try:
        from django.core.cache import cache
        from django.utils import timezone
        today = timezone.now().strftime('%Y-%m-%d')
        hour = timezone.now().strftime('%Y-%m-%d-%H')
        if company_id:
            key = f'wha_co:{company_id}:{today}'
            try: cache.incr(key)
            except ValueError: cache.set(key, 1, timeout=86400)
        if phone:
            key = f'wha_ph:{phone}:{hour}'
            try: cache.incr(key)
            except ValueError: cache.set(key, 1, timeout=3600)
    except Exception as e:
        logger.warning('WhatsApp rate increment error: %s', e)


def send_text(phone, message, company_id=None):
    """Send a WhatsApp text message via WAHA gateway.

    Args:
        phone: Phone number (will be normalized)
        message: Text message body
        company_id: Optional company ID for per-company rate limiting

    Returns:
        dict with keys: success (bool), error (str or None), response (dict or None)
    """
    if not getattr(settings, 'WAHA_ENABLED', False):
        return {'success': False, 'error': 'WhatsApp gateway disabled', 'response': None}

    if not _wa_rate_ok():
        return {'success': False, 'error': 'WhatsApp daily limit reached (500/day)', 'response': None}

    normalized = normalize_phone(phone)
    if not normalized:
        return {'success': False, 'error': f'Invalid phone number: {phone}', 'response': None}

    # Per-company + per-phone rate check
    allowed, reason = _whatsapp_rate_check(company_id=company_id, phone=normalized)
    if not allowed:
        return {'success': False, 'error': reason, 'response': None}

    chat_id = f"{normalized}@c.us"
    session_name = getattr(settings, 'WAHA_SESSION_NAME', 'default')

    try:
        url = f"{settings.WAHA_API_URL}/api/sendText"
        headers = {'Content-Type': 'application/json'}
        api_key = getattr(settings, 'WAHA_API_KEY', '')
        if api_key:
            headers['X-Api-Key'] = api_key
        payload = {
            'chatId': chat_id,
            'text': message,
            'session': session_name,
        }
        resp = requests.post(url, json=payload, timeout=10, headers=headers)

        if resp.status_code in (200, 201):
            logger.info('WhatsApp sent to %s (session=%s)', normalized, session_name)
            _whatsapp_rate_increment(company_id=company_id, phone=normalized)
            return {'success': True, 'error': None, 'response': resp.json()}
        else:
            error_msg = f'WAHA API error {resp.status_code}: {resp.text[:200]}'
            logger.error(error_msg)
            return {'success': False, 'error': error_msg, 'response': None}

    except requests.ConnectionError as e:
        logger.error('WAHA gateway unreachable: %s', e)
        return {'success': False, 'error': 'Gateway unreachable', 'response': None}
    except requests.Timeout as e:
        logger.error('WAHA gateway timeout: %s', e)
        return {'success': False, 'error': 'Gateway timeout', 'response': None}
    except Exception as e:
        logger.error('WhatsApp send error: %s', e)
        return {'success': False, 'error': str(e), 'response': None}
