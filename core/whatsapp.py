"""
Centralized WhatsApp service via WAHA gateway.
Mirrors core/email_tasks.py pattern for async messaging.
"""
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger('whatsapp')

# ── TEST MODE — WhatsApp Whitelist ─────────────────────────────────────────
# Dok je TEST_MODE aktivan, poruke idu SAMO na whitelist.
# Sve ostalo se logira ali NE šalje — ne plašimo klijente testnim podacima.
# Isključi na produkciji (15.4.2026): WHATSAPP_TEST_MODE = False u settings.
WHATSAPP_TEST_MODE = getattr(settings, 'WHATSAPP_TEST_MODE', True)
WHATSAPP_WHITELIST = getattr(settings, 'WHATSAPP_WHITELIST', [
    '4915771998747', # Ivan DE broj (ispravni)
    '385991908089',  # Ivan HR broj (0991908089)
    '385976715957',  # Petar Brtan (golubar tester)
    '4915771998747',  # Ivan Brtan (glavni)
    '491778716331',   # Antonio
])
# ──────────────────────────────────────────────────────────────────────────


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
        from datetime import date

        import redis
        r = redis.Redis.from_url(getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'))
        key = 'wa_global:%s' % date.today().isoformat()
        count = r.incr(key)
        r.expire(key, 86400)
        if count > daily_limit:
            logger.warning('WhatsApp daily limit reached: %d/%d', count, daily_limit)
            return False
        return True
    except ImportError:
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
    except ImportError as e:
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

    # TEST MODE — šalji samo na whitelist brojeve
    if WHATSAPP_TEST_MODE:
        _norm = normalize_phone(phone)
        if _norm not in WHATSAPP_WHITELIST:
            logger.info(f'TEST_MODE: poruka blokirana za {_norm} (nije na whitelistu)')
            return {'success': True, 'error': None, 'response': {'test_mode_blocked': True}}

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
    except requests.RequestException as e:
        logger.error('WhatsApp send error: %s', e)
        return {'success': False, 'error': str(e), 'response': None}



def send_document(phone, file_path, caption='', filename='', company_id=None):
    """Send a document (PDF, XLSX, etc.) via WAHA gateway.

    Args:
        phone: Phone number
        file_path: Absolute path to local file
        caption: Optional caption text
        filename: Display filename (default: basename of file_path)
        company_id: Optional for rate limiting

    Returns:
        dict: {success, error, response}
    """
    import base64
    import os

    if not getattr(settings, 'WAHA_ENABLED', False):
        return {'success': False, 'error': 'WhatsApp gateway disabled', 'response': None}

    # TEST MODE — šalji samo na whitelist brojeve
    if WHATSAPP_TEST_MODE:
        _norm = normalize_phone(phone)
        if _norm not in WHATSAPP_WHITELIST:
            logger.info(f'TEST_MODE: poruka blokirana za {_norm} (nije na whitelistu)')
            return {'success': True, 'error': None, 'response': {'test_mode_blocked': True}}

    if not os.path.exists(file_path):
        return {'success': False, 'error': f'File not found: {file_path}', 'response': None}

    normalized = normalize_phone(phone)
    if not normalized:
        return {'success': False, 'error': f'Invalid phone: {phone}', 'response': None}

    if not filename:
        filename = os.path.basename(file_path)

    chat_id = f"{normalized}@c.us"
    session_name = getattr(settings, 'WAHA_SESSION_NAME', 'default')

    # Read file and encode to base64
    with open(file_path, 'rb') as f:
        file_data = base64.b64encode(f.read()).decode()

    # Detect mimetype
    ext = os.path.splitext(file_path)[1].lower()
    mimetypes = {
        '.pdf': 'application/pdf',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel',
        '.csv': 'text/csv',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.zip': 'application/zip',
        '.xml': 'application/xml',
    }
    mimetype = mimetypes.get(ext, 'application/octet-stream')

    try:
        url = f"{settings.WAHA_API_URL}/api/sendFile"
        headers = {'Content-Type': 'application/json'}
        api_key = getattr(settings, 'WAHA_API_KEY', '')
        if api_key:
            headers['X-Api-Key'] = api_key

        # Try WAHA v2 format first (base64 in body)
        payload = {
            'chatId': chat_id,
            'session': session_name,
            'file': {
                'mimetype': mimetype,
                'filename': filename,
                'data': f'data:{mimetype};base64,{file_data}',
            },
        }
        if caption:
            payload['caption'] = caption

        resp = requests.post(url, json=payload, timeout=30, headers=headers)

        if resp.status_code in (200, 201):
            logger.info('WhatsApp document sent to %s: %s', normalized, filename)
            return {'success': True, 'error': None, 'response': resp.json()}

        # Fallback v1: data URL format
        payload['file']['data'] = file_data
        resp2 = requests.post(url, json=payload, timeout=30, headers=headers)
        if resp2.status_code in (200, 201):
            logger.info('WhatsApp document sent (v1) to %s: %s', normalized, filename)
            return {'success': True, 'error': None, 'response': resp2.json()}

        # Fallback: multipart upload
        return _send_document_multipart(chat_id, file_path, filename, caption, session_name, headers)

    except requests.RequestException as e:
        logger.error('WhatsApp send_document error: %s', e)
        return {'success': False, 'error': str(e), 'response': None}


def _send_document_multipart(chat_id, file_path, filename, caption, session_name, headers):
    """Fallback: multipart file upload for WAHA."""
    try:
        url = f"{settings.WAHA_API_URL}/api/sendFile"
        # Remove content-type for multipart
        h = {k: v for k, v in headers.items() if k.lower() != 'content-type'}

        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            data = {'chatId': chat_id, 'session': session_name, 'caption': caption}
            resp = requests.post(url, files=files, data=data, timeout=30, headers=h)

        if resp.status_code in (200, 201):
            logger.info('WhatsApp document (multipart) sent: %s', filename)
            return {'success': True, 'error': None, 'response': resp.json()}
        else:
            error = f'WAHA sendFile error {resp.status_code}: {resp.text[:200]}'
            logger.error(error)
            return {'success': False, 'error': error, 'response': None}

    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.error('WhatsApp multipart error: %s', e)
        return {'success': False, 'error': str(e), 'response': None}


def send_image(phone, image_path_or_b64, caption='', company_id=None):
    """Send an image via WAHA gateway.

    Args:
        phone: Phone number
        image_path_or_b64: File path OR base64 string
        caption: Optional caption

    Returns:
        dict: {success, error, response}
    """
    import base64
    import os

    if not getattr(settings, 'WAHA_ENABLED', False):
        return {'success': False, 'error': 'WhatsApp gateway disabled', 'response': None}

    # TEST MODE — šalji samo na whitelist brojeve
    if WHATSAPP_TEST_MODE:
        _norm = normalize_phone(phone)
        if _norm not in WHATSAPP_WHITELIST:
            logger.info(f'TEST_MODE: poruka blokirana za {_norm} (nije na whitelistu)')
            return {'success': True, 'error': None, 'response': {'test_mode_blocked': True}}

    normalized = normalize_phone(phone)
    if not normalized:
        return {'success': False, 'error': f'Invalid phone: {phone}', 'response': None}

    chat_id = f"{normalized}@c.us"
    session_name = getattr(settings, 'WAHA_SESSION_NAME', 'default')

    # Get base64 data
    if os.path.exists(str(image_path_or_b64)):
        with open(image_path_or_b64, 'rb') as f:
            b64_data = base64.b64encode(f.read()).decode()
        mimetype = 'image/jpeg' if image_path_or_b64.lower().endswith(('.jpg','.jpeg')) else 'image/png'
    else:
        b64_data = image_path_or_b64
        if b64_data.startswith('data:'):
            b64_data = b64_data.split(',')[1]
        mimetype = 'image/jpeg'

    try:
        url = f"{settings.WAHA_API_URL}/api/sendImage"
        headers = {'Content-Type': 'application/json'}
        api_key = getattr(settings, 'WAHA_API_KEY', '')
        if api_key:
            headers['X-Api-Key'] = api_key

        payload = {
            'chatId': chat_id,
            'session': session_name,
            'file': {
                'mimetype': mimetype,
                'data': b64_data,
            },
            'caption': caption,
        }

        resp = requests.post(url, json=payload, timeout=15, headers=headers)

        if resp.status_code in (200, 201):
            logger.info('WhatsApp image sent to %s', normalized)
            return {'success': True, 'error': None, 'response': resp.json()}
        else:
            error = f'WAHA sendImage error {resp.status_code}: {resp.text[:200]}'
            logger.error(error)
            return {'success': False, 'error': error, 'response': None}

    except requests.RequestException as e:
        logger.error('WhatsApp send_image error: %s', e)
        return {'success': False, 'error': str(e), 'response': None}


def send_document_link(phone, download_url, title='', caption='', company_id=None):
    """Fallback: salje tekst s linkom za preuzimanje."""
    parts = []
    if title:
        parts.append(title)
    if caption:
        parts.append(caption)
    parts.append('Preuzmi: ' + download_url)
    return send_text(phone, chr(10).join(parts), company_id=company_id)
