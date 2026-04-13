import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models, DatabaseError, IntegrityError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist


class MagicToken(models.Model):
    """Magic link token za passwordless login"""
    TOKEN_TYPE = [
        ('investor',  _('Investitor - projekti')),
        ('partner',   _('Partner - fakture')),
        ('worker',    _('Radnik - upload slika')),
        ('reset',     _('Reset lozinke')),
        ('verify',    _('Verifikacija emaila')),
    ]
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='magic_tokens')
    token      = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    token_type = models.CharField(max_length=20, choices=TOKEN_TYPE, default='partner')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at    = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    # Opcionalni kontekst - za koji projekt, fakturu itd.
    context    = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _('Magic token')
        verbose_name_plural = _('Magic tokeni')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} – {self.token_type} – {'iskorišten' if self.used_at else 'aktivan'}"

    @classmethod
    def create_for_user(cls, user, token_type='partner', hours=24, context=None):
        # Pobrisi stare neiskorištene tokene istog tipa
        cls.objects.filter(user=user, token_type=token_type, used_at__isnull=True).delete()
        return cls.objects.create(
            user=user,
            token_type=token_type,
            expires_at=timezone.now() + timedelta(hours=hours),
            context=context or {},
        )

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()

    def mark_used(self, ip=None):
        self.used_at = timezone.now()
        self.ip_address = ip
        self.save(update_fields=['used_at', 'ip_address'])


class LoginAttempt(models.Model):
    """Log pokušaja prijave za sigurnost"""
    email      = models.EmailField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    success    = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)
    user_agent = models.CharField(max_length=255, blank=True)
    method     = models.CharField(max_length=20, default='password',
                                   help_text='password/magic/google/microsoft/2fa')

    class Meta:
        verbose_name = _('Pokušaj prijave')
        verbose_name_plural = _('Pokušaji prijave')
        ordering = ['-attempted_at']

    @classmethod
    def is_blocked(cls, ip, email, max_attempts=5, minutes=15):
        """Blokira IP/email nakon previše neuspješnih pokušaja"""
        since = timezone.now() - timedelta(minutes=minutes)
        count = cls.objects.filter(
            ip_address=ip, success=False, attempted_at__gte=since
        ).count()
        return count >= max_attempts
