"""
accounts/email_verification.py — Email Verification Service

Moderan pristup (GitHub/Slack stil):
- Korisnik se može prijaviti odmah nakon registracije
- Verifikacijski email se šalje u pozadini (Celery)
- Banner na dashboardu dok ne verificira
- Nije blokirajuće, ali je trajno vidljivo

Flow:
  1. quick_register() → send_verification_email(user)
  2. Korisnik klikne link → /auth/verify-email/<token>/
  3. email_verified = True, email_verified_at = now()
  4. Banner nestaje

Token: MagicToken(token_type='verify', hours=72)
"""

import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("accounts.verification")


def send_verification_email(user):
    """
    Šalje verifikacijski email korisniku.
    Poziva se async iz quick_register (Celery).
    """
    from accounts.auth_models import MagicToken
    from core.email_tasks import send_email_task

    # Kreiraj verify token (72h valjanost)
    token = MagicToken.create_for_user(user, token_type="verify", hours=72)

    # Generiraj link
    base_url = getattr(settings, "SITE_URL", "https://limit-connect.com")
    verify_url = f"{base_url}/auth/verify-email/{token.token}/"

    subject = "LIMIT Connect — Potvrdite email adresu"
    body = f"""Poštovani {user.get_full_name() or user.username},

Dobrodošli u LIMIT Connect!

Kliknite na sljedeći link kako biste potvrdili svoju email adresu:

{verify_url}

Link vrijedi 72 sata.

Ako niste vi kreirali ovaj račun, ignorirajte ovaj email.

—
LIMIT Connect
limit-connect.com
"""

    html_body = f'''<div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:2rem;background:#0a0a0f;color:#e2e8f0">
<h2 style="color:#c9a84c;margin-bottom:1rem">LIMIT Connect</h2>
<p>Poštovani {user.get_full_name() or user.username},</p>
<p>Dobrodošli! Potvrdite svoju email adresu klikom na gumb:</p>
<p style="margin:2rem 0;text-align:center">
<a href="{verify_url}" style="display:inline-block;padding:14px 32px;background:#c9a84c;color:#000;text-decoration:none;border-radius:8px;font-weight:700;font-size:1rem">Potvrdi email ✓</a>
</p>
<p style="color:#64748b;font-size:.85rem">Link vrijedi 72 sata.</p>
<p style="color:#64748b;font-size:.75rem">Ili kopirajte: {verify_url}</p>
<hr style="border:none;border-top:1px solid #333;margin:1.5rem 0">
<p style="color:#475569;font-size:.75rem">Ako niste vi kreirali račun, ignorirajte ovaj email.</p>
</div>'''

    try:
        send_email_task.delay(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_body,
        )
        logger.info("Verification email sent to %s (token=%s)", user.email, token.token[:8])
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", user.email, e)


def verify_email_token(token_str, request=None):
    """
    Verificira email token i ažurira profil.

    Returns: (success: bool, user: User|None, message: str)
    """
    from accounts.auth_models import MagicToken

    try:
        token = MagicToken.objects.get(token=token_str, token_type="verify")
    except MagicToken.DoesNotExist:
        return False, None, "Nevažeći verifikacijski link."

    if token.used_at:
        return False, token.user, "Email je već verificiran."

    if not token.is_valid:
        return False, token.user, "Link je istekao. Zatražite novi."

    # Označi token kao korišten
    ip = None
    if request:
        ip = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR")
    token.mark_used(ip=ip)

    # Ažuriraj profil
    try:
        profile = token.user.profile
        profile.email_verified = True
        profile.email_verified_at = timezone.now()
        profile.save(update_fields=["email_verified", "email_verified_at"])
        logger.info("Email verified for %s", token.user.email)
    except AttributeError as e:
        logger.error("Profile update failed for %s: %s", token.user.email, e)
        return False, token.user, "Greška pri ažuriranju profila."

    return True, token.user, "Email uspješno verificiran!"


def resend_verification_email(user):
    """
    Ponovo šalje verifikacijski email.
    Rate limit: max 3 emaila po korisniku.
    """
    from accounts.auth_models import MagicToken

    # Rate limit: max 3 verify tokena u zadnja 24h
    recent_count = MagicToken.objects.filter(
        user=user,
        token_type="verify",
        created_at__gte=timezone.now() - timezone.timedelta(hours=24),
    ).count()

    if recent_count >= 3:
        return False, "Previše zahtjeva. Pokušajte ponovo za 24 sata."

    send_verification_email(user)
    return True, "Verifikacijski email poslan."
