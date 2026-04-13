"""
core/notify.py — Koordinatorske notifikacije na WhatsApp

Sve važne poruke prema Ivanu idu kroz ovu funkciju.
Kategorije:
  INFO    — za znanje, ne treba akcija
  ACTION  — treba tvoj odgovor/potvrdu
  ALERT   — nešto je puklo, gledaj odmah

Korištenje:
  from core.notify import notify
  notify("INFO", "Bulk invite završen — 8 korisnika pozvano")
  notify("ACTION", "Šeki otvorio prvu smjenu — potvrdi fiskalizaciju?")
  notify("ALERT", "Gunicorn restartao — health monitor detektirao 502")
"""
import logging
from django.conf import settings

logger = logging.getLogger('notify')

ICONS = {
    'INFO':   'ℹ️',
    'ACTION': '👆',
    'ALERT':  '🚨',
    'DEPLOY': '🚀',
    'USER':   '👤',
    'POS':    '🧾',
    'MONEY':  '💶',
}

ADMIN_PHONE = getattr(settings, 'SUPERADMIN_WHATSAPP', '+4915771998747')


def notify(category: str, message: str, urgent: bool = False):
    """
    Pošalji WhatsApp notifikaciju Ivanu.

    category: INFO | ACTION | ALERT | DEPLOY | USER | POS | MONEY
    message:  tekst poruke
    urgent:   True = sync slanje, False = async (Celery)
    """
    icon = ICONS.get(category, '📌')
    full_msg = f"{icon} *LIMIT Connect*\n\n{message}"

    try:
        if urgent:
            from core.whatsapp import send_text
            return send_text(ADMIN_PHONE, full_msg)
        else:
            from core.whatsapp_tasks import send_whatsapp_text_task
            send_whatsapp_text_task.delay(ADMIN_PHONE, full_msg)
            return {'success': True, 'async': True}
    except ImportError as e:
        logger.error('notify() failed: %s', e)
        return {'success': False, 'error': str(e)}
