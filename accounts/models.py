from django.core.exceptions import ObjectDoesNotExist
from core.fields import FernetEncryptedCharField
from django.contrib.auth.models import User
from django.db import models, DatabaseError, IntegrityError
from django.utils.translation import gettext_lazy as _
from core.managers import CompanyManager


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('superadmin',  _('Super Administrator')),
        ('tenant_admin', _('Tenant Admin (krovna firma)')),
        ('company_admin', _('Admin tvrtke')),
        ('project_manager', _('Voditelj projekta')),
        ('worker',      _('Radnik')),
        ('investor',    _('Investitor')),
        ('partner',     _('Partner / Klijent')),
        # Vanjski suradnici (Delegation Pattern)
        ('veterinar',   _('Veterinar')),
        ('racunovodja', _('Racunovodja / Steuerberater')),
        ('inspektor',   _('Inspektor')),
        ('revizor',     _('Revizor')),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES,
                            default='worker', verbose_name=_('Uloga'))
    company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL,
                                null=True, blank=True, verbose_name=_('Tvrtka'))
    profile_image = models.ImageField(upload_to='profiles/', blank=True,
                                      verbose_name=_('Profilna slika'))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_('Telefon'))
    department = models.CharField(max_length=100, blank=True, verbose_name=_('Odjel'))
    totp_secret = FernetEncryptedCharField(blank=True, verbose_name='TOTP Secret')
    totp_enabled = models.BooleanField(default=False, verbose_name='2FA aktiviran')
    google_id = models.CharField(max_length=100, blank=True)
    microsoft_id = models.CharField(max_length=100, blank=True)
    preferred_language = models.CharField(
        max_length=5, default='hr',
        choices=[('hr', 'Hrvatski'), ('de', 'Deutsch'), ('en', 'English')],
        verbose_name=_('Jezik sučelja')
    )
    can_upload_photos = models.BooleanField(default=True, verbose_name=_('Može uploadati slike'))
    can_view_financials = models.BooleanField(default=False, verbose_name=_('Vidi financije'))
    can_approve_timesheets = models.BooleanField(default=False, verbose_name=_('Odobrava radne sate'))
    # Web Push subscription (VAPID)
    push_subscription   = models.TextField(blank=True, default='',
                                            verbose_name='Push subscription JSON')
    must_change_password = models.BooleanField(default=False, verbose_name=_("Mora promijeniti lozinku"))

    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = FernetEncryptedCharField(blank=True)
    branch       = models.ForeignKey(
        'companies.CompanyBranch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='users',
        verbose_name=_('Podružnica'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    objects = CompanyManager()

    # Dron #1: GPS lokacija radnika (ažurira se pri FSM tranziciji)
    last_lat           = models.FloatField(null=True, blank=True)
    last_lng           = models.FloatField(null=True, blank=True)
    last_gps_update    = models.DateTimeField(null=True, blank=True)

    # Dron #2: Eksplicitni certifikati za dispatch (hard filter)
    # Email verifikacija
    email_verified = models.BooleanField(default=False, verbose_name=_('Email verificiran'))
    email_verified_at = models.DateTimeField(null=True, blank=True)

    certified_categories = models.JSONField(default=list, blank=True,
        help_text='Lista: voda, struja, plin, kljucar')

    class Meta:
        db_table = 'core_userprofile'
        verbose_name = _('Korisnički profil')
        verbose_name_plural = _('Korisnički profili')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} [{self.get_role_display()}]"

    @property
    def is_superadmin(self):
        return self.role == 'superadmin' or self.user.is_superuser

    @property
    def is_tenant_admin(self):
        return self.role == 'tenant_admin'

    def get_visible_companies(self):
        """Vrati firme koje ovaj korisnik smije vidjeti.
        superadmin (is_superuser) = SVE
        tenant_admin = umbrella children + grandchildren (rekurzivno)
        ostali = samo vlastita firma
        """
        from companies.models import Company
        if self.user.is_superuser and self.role == 'superadmin':
            return Company.objects.all()
        if self.role == 'tenant_admin' and self.company:
            # Rekurzivno: vlastita + children + grandchildren (max 3 razine)
            ids = set()
            ids.add(self.company.pk)
            # Level 1: direct children
            level1 = set(Company.objects.filter(umbrella_parent=self.company).values_list('pk', flat=True))
            ids.update(level1)
            # Level 2: grandchildren
            if level1:
                level2 = set(Company.objects.filter(umbrella_parent__in=level1).values_list('pk', flat=True))
                ids.update(level2)
                # Level 3: great-grandchildren
                if level2:
                    level3 = set(Company.objects.filter(umbrella_parent__in=level2).values_list('pk', flat=True))
                    ids.update(level3)
            return Company.objects.filter(pk__in=ids)
        if self.company:
            return Company.objects.filter(pk=self.company.pk)
        return Company.objects.none()

    @property
    def is_company_admin(self):
        return self.role in ('superadmin', 'company_admin') or self.user.is_staff

    @property
    def is_manager(self):
        return self.role in ('superadmin', 'company_admin', 'project_manager')

    @property
    def dashboard_url(self):
        URLS = {
            'superadmin': '/superadmin/',
            'company_admin': '/dashboard/company/',
            'project_manager': '/dashboard/manager/',
            'worker': '/dashboard/worker/',
            'investor': '/dashboard/investor/',
            'partner': '/dashboard/partner/',
        }
        return URLS.get(self.role, '/')




class ImpersonationLog(models.Model):
    """Audit trail for every superadmin impersonation session."""
    superadmin  = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='impersonation_sessions',
        verbose_name='Superadmin'
    )
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='impersonation_logs', verbose_name='Tvrtka'
    )
    started_at    = models.DateTimeField(auto_now_add=True, verbose_name='Početak')
    ended_at      = models.DateTimeField(null=True, blank=True, verbose_name='Kraj')
    ip_address    = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP adresa')
    actions_count = models.IntegerField(default=0, verbose_name='Broj akcija')
    objects = CompanyManager()

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Log impersonacije'
        verbose_name_plural = 'Logovi impersonacija'

    def __str__(self):
        return f"{self.superadmin.username} → {self.company.name} @ {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def duration_display(self):
        from django.utils import timezone
        end = self.ended_at or timezone.now()
        secs = int((end - self.started_at).total_seconds())
        h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
        return f"{h:02d}:{m:02d}:{s:02d}"



class CompanyMembership(models.Model):
    """Links a user to a company with a specific role.
    Enables one user to belong to multiple companies."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_memberships')
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, related_name='memberships'
    )
    role = models.CharField(max_length=30, choices=UserProfile.ROLE_CHOICES, default='worker')
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        unique_together = ('user', 'company')
        db_table = 'accounts_companymembership'
        verbose_name = 'Membership'
        verbose_name_plural = 'Memberships'

    def __str__(self):
        return f"{self.user.username} @ {self.company.name} [{self.get_role_display()}]"


# ═══════════════════════════════════════════════════════════════
# DeviceToken — Mobilni barcode login (mobitel = čip kartica)
# ═══════════════════════════════════════════════════════════════

import uuid as _uuid
import hashlib as _hashlib
import urllib.parse as _urllib_parse


class DeviceToken(models.Model):
    """
    Token za login bez lozinke — korisnik sprema barcode u mobitel,
    skenira ga na POS terminalu kamerom → instant prijava.
    Ako POS radi na istom mobitelu → auto-login bez skeniranja.
    """
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='device_tokens', verbose_name=_('Korisnik'),
    )
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='device_tokens', verbose_name=_('Tvrtka'),
    )
    token = models.UUIDField(default=_uuid.uuid4, unique=True, editable=False)
    # Barcode data: LC-DEV-{short_hash} — kratko za skeniranje
    barcode_data = models.CharField(
        max_length=30, unique=True, editable=False,
        verbose_name=_('Barcode podatak'),
    )
    device_name = models.CharField(
        max_length=100, blank=True, verbose_name=_('Naziv uređaja'),
        help_text=_('npr. "Moj iPhone", "Samsung tablet blagajna"'),
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivan'))
    # Auto POS login: ako je True, browser s ovim tokenom u localStorage
    # automatski se logira bez skeniranja
    auto_pos_login = models.BooleanField(
        default=True, verbose_name=_('Auto POS login'),
        help_text=_('Automatski prijavi na POS bez skeniranja barkoda'),
    )
    # Opcionalno: cashier ID za direktan cashier-switch nakon logina
    cashier = models.ForeignKey(
        'pos.POSCashier', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('POS blagajnik'),
        help_text=_('Ako je postavljeno, odmah aktivira ovog blagajnika'),
    )
    # B-20: Token expiry za volontere (null = ne istječe)
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Istječe'),
        help_text=_('Automatski se deaktivira nakon ovog datuma. Prazno = trajno.'),
    )
    # B-21: Label za printani QR
    label = models.CharField(
        max_length=100, blank=True, verbose_name=_('Natpis na QR-u'),
        help_text=_('Ime + firma + datum — za printane QR kartice volontera'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Device token')
        verbose_name_plural = _('Device tokeni')
        ordering = ['-created_at']

    def __str__(self):
        return '%s — %s (%s)' % (
            self.user.get_full_name() or self.user.username,
            self.device_name or 'Uređaj',
            'aktivan' if self.is_active else 'deaktiviran',
        )

    @property
    def is_expired(self):
        """True ako je token istekao (B-20 volonter expiry)."""
        if not self.expires_at:
            return False
        from django.utils import timezone as _tz
        return _tz.now() > self.expires_at

    @property
    def is_usable(self):
        """True samo ako je aktivan I nije istekao."""
        return self.is_active and not self.is_expired

    @property
    def whatsapp_link(self):
        """B-19: WhatsApp deep link za slanje tokena — jedan klik."""
        url = 'https://limit-connect.com/hr/auth/device-login/?token=%s' % self.token
        text = 'Tvoj LIMIT Connect pristup: %s\nOtvori link za prijavu na POS.' % url
        return 'https://wa.me/?text=%s' % _urllib_parse.quote(text)

    @property
    def auto_login_url(self):
        """Direktni URL za auto-login (za QR kod, bookmark, WhatsApp)."""
        return 'https://limit-connect.com/hr/auth/device-login/?token=%s' % self.token

    def save(self, *args, **kwargs):
        if not self.barcode_data:
            # Generiraj kratki barcode: LC-DEV-XXXXXXXX
            short = _hashlib.sha256(self.token.bytes).hexdigest()[:8].upper()
            self.barcode_data = 'LC-DEV-%s' % short
        # Auto-generate label if empty
        if not self.label and self.user_id:
            name = self.user.get_full_name() or self.user.username
            company = self.company.name if self.company_id else ''
            self.label = '%s — %s' % (name, company)
        super().save(*args, **kwargs)


# ════════════════════════════════════════════════════════════════
# TriKey — 3 ključa za 1 bravu
# ════════════════════════════════════════════════════════════════
from accounts.trikey import TriKeyProfile  # noqa: E402
