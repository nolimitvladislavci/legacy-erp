"""
VAPID Web Push helper.
Šalje push notifikaciju na jednu ili više pretplata.
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_vapid_claims():
    return {
        'sub': f'mailto:{settings.VAPID_CLAIMS_EMAIL}',
    }


def send_push(subscription_json: str, title: str, body: str,
              icon: str = '/static/images/icon-192.png',
              url: str = '/interventions/') -> bool:
    """
    Pošalji Web Push notifikaciju.
    subscription_json – JSON string iz browser.pushManager.subscribe()
    Vraća True ako uspješno, False ako pretplata više ne vrijedi (treba brisati).
    """
    if not subscription_json or not settings.VAPID_PUBLIC_KEY:
        return False
    try:
        sub = json.loads(subscription_json)
    except (json.JSONDecodeError, ValueError):
        return False

    payload = json.dumps({
        'title': title,
        'body':  body,
        'icon':  icon,
        'url':   url,
    })

    try:
        from pywebpush import WebPushException, webpush
        webpush(
            subscription_info=sub,
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims=_get_vapid_claims(),
        )
        return True
    except ImportError as exc:
        err_str = str(exc)
        if '410' in err_str or '404' in err_str:
            # Pretplata istekla – caller bi trebao obrisati
            logger.info(f'Push subscription expired (410/404): {exc}')
            return False
        logger.warning(f'Push send error: {exc}')
        return False


def send_push_to_user(user, title: str, body: str, url: str = '/interventions/') -> bool:
    """Pošalji push notifikaciju korisniku (via UserProfile.push_subscription)."""
    try:
        sub = user.profile.push_subscription
        if not sub:
            return False
        ok = send_push(sub, title, body, url=url)
        if not ok:
            # Očisti nevažeću pretplatu
            user.profile.push_subscription = ''
            user.profile.save(update_fields=['push_subscription'])
        return ok
    except AttributeError as exc:
        logger.warning(f'send_push_to_user error: {exc}')
        return False


def send_company_push(company_id, title, body, url="/einvoice/inbox/"):
    """Posalji push notifikaciju svim korisnicima koji pripadaju firmi."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    users = User.objects.filter(
        profile__company_id=company_id,
        profile__push_subscription__gt="",
        is_active=True,
    ).select_related("profile")
    sent = 0
    for user in users:
        if send_push_to_user(user, title, body, url=url):
            sent += 1
    logger.info(f"Company push ({company_id}): {sent}/{users.count()} delivered")
    return sent
