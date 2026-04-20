"""Fenix v3 — Accounts Signals | Blok D + profile auto-create"""

from datetime import timedelta
from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatski kreira UserProfile za svakog novog korisnika."""
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """
    Blok D — Concurrent Session Detection.
    Kreira LoginAttempt zapis i provjerava istovremene sesije s razlicitih IP.
    Ako postoji aktivna sesija s druge IP (<30 min) → alert email + WhatsApp.
    """
    from .auth_models import LoginAttempt

    ip = request.META.get("REMOTE_ADDR", "")
    ua = request.META.get("HTTP_USER_AGENT", "")[:500]
    session_key = getattr(request.session, "session_key", "") or ""

    LoginAttempt.objects.create(
        user=user,
        email=user.email,
        ip_address=ip,
        user_agent=ua,
        method="password",
        success=True,
        session_key=session_key,
    )

    # Provjeri postoje li aktivne sesije s RAZLICITIH IP-ova u zadnjih 30 min
    cutoff = timezone.now() - timedelta(minutes=30)
    other_sessions = (
        LoginAttempt.objects.filter(
            user=user,
            success=True,
            attempted_at__gte=cutoff,
        )
        .exclude(ip_address=ip)
        .exists()
    )

    if other_sessions:
        try:
            from core.tasks import alert_concurrent_session

            alert_concurrent_session.delay(user.pk, ip, ua)
        except Exception:
            pass  # Ne zaustavljaj login ako task failuje
