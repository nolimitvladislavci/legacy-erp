"""
Password reset notification — šalje WhatsApp i/ili email kad admin promijeni lozinku.

Usage:
    from accounts.password_notify import notify_password_change
    notify_password_change(user, new_password, changed_by=request.user)
"""
import logging
from django.conf import settings
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger('accounts')


def notify_password_change(user, new_password, changed_by=None):
    """
    Šalje notifikaciju korisniku o promjeni lozinke.
    Pokušava WhatsApp prvo, fallback na email.

    Args:
        user: User čija je lozinka promijenjena
        new_password: nova lozinka (plaintext za poruku)
        changed_by: User koji je promijenio (za audit)
    """
    phone = _get_phone(user)
    full_name = user.get_full_name() or user.username

    message = (
        'Pozdrav %s!\n\n'
        'Vaša nova lozinka za LIMIT Connect:\n'
        'Korisničko ime: %s\n'
        'Lozinka: %s\n\n'
        'Prijavite se na: https://limit-connect.com/hr/\n\n'
        '— LIMIT Connect tim'
    ) % (full_name, user.username, new_password)

    sent_via = []

    # 1. WhatsApp (ako ima broj i WAHA je aktivan)
    if phone and getattr(settings, 'WAHA_ENABLED', False):
        try:
            from core.whatsapp_tasks import send_whatsapp_text_task
            send_whatsapp_text_task.delay(phone, message)
            sent_via.append('whatsapp:%s' % phone)
        except ImportError as e:
            logger.warning('WhatsApp password notify failed for %s: %s', user.username, e)

    # 2. Email fallback
    if user.email:
        try:
            from django.core.mail import send_mail
            send_mail(
                subject='LIMIT Connect — Nova lozinka',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            sent_via.append('email:%s' % user.email)
        except Exception as e:
            logger.warning('Email password notify failed for %s: %s', user.username, e)

    # 3. In-app notifikacija
    try:
        from notifications.services import notify
        notify(
            recipient=user,
            notification_type='system',
            title='Lozinka promijenjena',
            message='Vaša lozinka je promijenjena%s.' % (
                ' od strane %s' % changed_by.get_full_name() if changed_by else ''
            ),
            url='/worktime/profile/',
        )
        sent_via.append('in_app')
    except ImportError:
        pass

    if sent_via:
        logger.info('Password change notified: user=%s via=%s', user.username, ','.join(sent_via))
    else:
        logger.warning('Password change NOT notified: user=%s (no phone, no email)', user.username)

    return sent_via


def _get_phone(user):
    """Izvuci telefon iz UserProfile ili EmployeeProfile."""
    from core.whatsapp import normalize_phone

    # UserProfile
    profile = getattr(user, 'profile', None)
    if profile and profile.phone:
        normalized = normalize_phone(profile.phone)
        if normalized:
            return normalized

    # EmployeeProfile
    ep = getattr(user, 'employeeprofile', None)
    if ep and ep.phone:
        normalized = normalize_phone(ep.phone)
        if normalized:
            return normalized

    return ''
