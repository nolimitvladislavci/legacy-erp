"""core/tasks.py — Centralni Celery taskovi."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  ERROR NOTIFICATION — WhatsApp + Email za trojku
# ═══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, soft_time_limit=30)
def notify_error_to_team(self, user, path, method, exc_class,
                         exc_message, category, traceback, ip):
    """
    Šalje WhatsApp + email notifikaciju trojci kad se dogodi 500.

    Trojka:
      - Nikša (dev) — dobije traceback
      - Marija (ops) — dobije user-friendly poruku
      - Dev kanal — dobije puni log
    """
    import logging
    from django.conf import settings
    from datetime import datetime

    logger = logging.getLogger(__name__)

    timestamp = datetime.now().strftime('%H:%M:%S')
    date_str = datetime.now().strftime('%d.%m.%Y')

    # ── Poruka za dev (puni traceback) ──
    dev_message = (
        f'🔴 *500 ERROR* — {date_str} {timestamp}\n\n'
        f'*User:* {user}\n'
        f'*Path:* {method} {path}\n'
        f'*Exception:* {exc_class}\n'
        f'*Message:* {exc_message[:300]}\n'
        f'*Category:* {category}\n'
        f'*IP:* {ip}\n\n'
        f'```\n{traceback[-1500:]}\n```'
    )

    # ── Poruka za ops (user-friendly) ──
    ops_message = (
        f'⚠️ Greška u sustavu — {timestamp}\n\n'
        f'Korisnik *{user}* je naišao na grešku na stranici {path}.\n'
        f'Tip: {category}\n'
        f'Tim je automatski obaviješten.'
    )

    # ── WhatsApp ──
    try:
        from core.whatsapp import send_text
        # Dev telefoni — iz environment varijabli
        dev_phones = getattr(settings, 'ERROR_NOTIFY_PHONES', [])
        ops_phones = getattr(settings, 'ERROR_NOTIFY_OPS_PHONES', [])

        for phone in dev_phones:
            try:
                send_text(phone, dev_message)
                logger.info('Error WhatsApp sent to dev: %s', phone)
            except Exception as e:
                logger.warning('WhatsApp dev notify failed for %s: %s', phone, e)

        for phone in ops_phones:
            try:
                send_text(phone, ops_message)
                logger.info('Error WhatsApp sent to ops: %s', phone)
            except Exception as e:
                logger.warning('WhatsApp ops notify failed for %s: %s', phone, e)

    except ImportError:
        logger.warning('WhatsApp module not available for error notification')

    # ── Email fallback ──
    try:
        from django.core.mail import mail_admins
        mail_admins(
            subject=f'[500] {exc_class} at {path}',
            message=f'User: {user}\nPath: {method} {path}\n'
                    f'Exception: {exc_class}: {exc_message}\n'
                    f'Category: {category}\nIP: {ip}\n\n'
                    f'Traceback:\n{traceback}',
            fail_silently=True,
        )
    except Exception as e:
        logger.warning('Email error notification failed: %s', e)

