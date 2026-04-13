from django.db import models

from core.managers import CompanyManager


class SystemAuditLog(models.Model):
    """Immutable audit trail for all financial data changes."""
    ACTION_CHOICES = [
        ('create', 'Kreiranje'),
        ('update', 'Ažuriranje'),
        ('delete', 'Brisanje'),
        ('read', 'Pristup'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=50)
    object_repr = models.CharField(max_length=300, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['company', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
        verbose_name = 'Revizijski zapis'
        verbose_name_plural = 'Revizijski zapisi'

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} | {self.action} | {self.model_name} | {self.object_repr[:50]}"


class InspectionToken(models.Model):
    """
    Inspekcijski pristupni token — generira se iz Panic Buttona.
    Inspektor skenira QR → pristupa read-only dashboardu bez logina.
    """
    SCOPE_CHOICES = [
        ('porezna',  'Porezna inspekcija'),
        ('pos',      'POS / Fiskalizacija'),
        ('radna',    'Radna inspekcija'),
        ('sanitarna', 'Sanitarna inspekcija'),
        ('hapih',    'HAPIH — Knjiga lijekova'),
        ('jrdz',     'JRDZ — Registar životinja'),
        ('vetis',    'VetIS — Vet knjiga'),
        ('prigovori', 'Knjiga prigovora i utisaka'),
        ('all',      'Potpuni pristup (sve)'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='inspection_tokens')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='all')
    label = models.CharField(max_length=200, blank=True,
                             verbose_name='Naziv (npr. "Porezna inspekcija 22.03.2026")')

    # Period koji inspektor može vidjeti
    date_from = models.DateField(null=True, blank=True, verbose_name='Od datuma')
    date_to = models.DateField(null=True, blank=True, verbose_name='Do datuma')

    # Sigurnost
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(verbose_name='Istječe')
    max_views = models.IntegerField(default=100, verbose_name='Max pregleda')
    view_count = models.IntegerField(default=0)

    # Audit
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(null=True, blank=True)
    access_ip = models.GenericIPAddressField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Inspekcijski token'
        verbose_name_plural = 'Inspekcijski tokeni'

    def __str__(self):
        return f'{self.label or self.scope} — {self.company.name}'

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.view_count >= self.max_views:
            return False
        return True

    def record_access(self, ip=None):
        from django.utils import timezone
        self.view_count += 1
        self.last_accessed = timezone.now()
        if ip:
            self.access_ip = ip
        self.save(update_fields=['view_count', 'last_accessed', 'access_ip'])


class InspectionProtocol(models.Model):
    """
    Zapisnik o inspekcijskom pristupu — inspektor potpisuje PRIJE pristupa podacima.
    Pravna osnova: GDPR čl. 30, Zakon o inspekcijama (NN 115/18) čl. 24.
    """
    token = models.OneToOneField(InspectionToken, on_delete=models.CASCADE,
                                  related_name='protocol')
    # Inspektor
    inspector_first_name = models.CharField(max_length=100, verbose_name='Ime inspektora')
    inspector_last_name = models.CharField(max_length=100, verbose_name='Prezime inspektora')
    inspector_badge = models.CharField(max_length=50, blank=True, verbose_name='Broj znacke / ID')
    inspector_institution = models.CharField(max_length=200, blank=True,
        verbose_name='Institucija (npr. Porezna uprava, DORH, MUP)')
    inspector_phone = models.CharField(max_length=30, blank=True, verbose_name='Kontakt telefon')
    inspector_email = models.EmailField(blank=True, verbose_name='Email inspektora')

    # Pravni temelj
    legal_basis = models.CharField(max_length=300, blank=True,
        verbose_name='Pravni temelj inspekcije',
        help_text='Npr. Nalog br. UP/II-471-01/26-01/123')

    # Izjava i potpis
    terms_accepted = models.BooleanField(default=False,
        verbose_name='Inspektor prihvatio uvjete pristupa')
    signature = models.TextField(blank=True, verbose_name='Digitalni potpis (base64)')
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_ip = models.GenericIPAddressField(null=True, blank=True)

    # Upload — slika znacke/naloga
    badge_photo = models.ImageField(upload_to='inspection/badges/', null=True, blank=True,
        verbose_name='Fotografija znacke')
    warrant_photo = models.ImageField(upload_to='inspection/warrants/', null=True, blank=True,
        verbose_name='Fotografija naloga/rjesenja')

    # Geolokacija (opciono, ako browser dozvoli)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Inspekcijski zapisnik'
        verbose_name_plural = 'Inspekcijski zapisnici'

    def __str__(self):
        return f'{self.inspector_first_name} {self.inspector_last_name} — {self.token.label}'

    @property
    def inspector_full_name(self):
        return f'{self.inspector_first_name} {self.inspector_last_name}'.strip()


class MemioPetWaitlist(models.Model):
    """Waiting lista za memio.pet — javna prijava s landing pagea."""
    PET_TYPE_CHOICES = [
        ('pas', 'Pas'), ('macka', 'Mačka'), ('konj', 'Konj'), ('ostalo', 'Ostalo'),
    ]
    USER_TYPE_CHOICES = [
        ('vlasnik', 'Vlasnik ljubimca'), ('uzgajivac', 'Uzgajivač / Kennel'),
    ]
    name       = models.CharField(max_length=120)
    email      = models.EmailField(unique=True)
    pet_type   = models.CharField(max_length=20, choices=PET_TYPE_CHOICES, blank=True)
    user_type  = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, blank=True)
    source     = models.CharField(max_length=50, default='memio.pet')
    ip         = models.GenericIPAddressField(null=True, blank=True)
    # ── CroValidator / OIB verifikacija (samo za pravne osobe) ──
    oib             = models.CharField(max_length=11, blank=True, default='')
    is_cro_validated = models.BooleanField(default=False)
    validated_name  = models.CharField(max_length=200, blank=True, default='')
    validated_city  = models.CharField(max_length=100, blank=True, default='')
    validated_at    = models.DateTimeField(null=True, blank=True)
    notified   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Memio.pet waiting lista'

    def __str__(self):
        return f"{self.name} <{self.email}>"


# ═══════════════════════════════════════════════════════════════════════════
# BookingSignature — Globalni audit trail s integritetnim hashom
# ═══════════════════════════════════════════════════════════════════════════

class BookingSignature(models.Model):
    """
    Append-only audit trail za SVE financijske akcije na portalu.

    Zakonska osnova:
    - Zakon o računovodstvu (NN 78/15) čl. 8, 12, 13
    - GDPR (EU 2016/679) — pravo na uvid
    - Zakon o fiskalizaciji — identitet operatera

    Arhitekturna pravila:
    1. NIKAD se ne briše (save blokira update, delete zabranjen)
    2. integrity_hash = SHA256(user + action + target + timestamp + SECRET)
    3. Sinkroni upis u istoj transakciji s akcijom
    4. changes sadrži SAMO promijenjene fieldove (diff, ne dump)
    5. Retention: 11 godina (Zakon o računovodstvu)
    """

    class Action(models.TextChoices):
        BOOK        = 'book',       'Knjiženje'
        UNBOOK      = 'unbook',     'Odknjižavanje'
        DELETE      = 'delete',     'Brisanje'
        STORNO      = 'storno',     'Storno'
        EXPORT      = 'export',     'Izvoz podataka'
        SWITCH      = 'switch',     'Promjena konteksta'
        LOGIN       = 'login',      'Prijava'
        LOGOUT      = 'logout',     'Odjava'
        CREATE      = 'create',     'Kreiranje'
        UPDATE      = 'update',     'Ažuriranje'
        FISCAL      = 'fiscal',     'Fiskalizacija'
        PRINT       = 'print',      'Ispis'
        SEND        = 'send',       'Slanje (email/WhatsApp)'
        APPROVE     = 'approve',    'Odobravanje'
        VIEW_SENSITIVE = 'view_sensitive', 'Pristup osjetljivim podacima'

    # ── Tko ───────────────────────────────────────────────────
    user = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True,
        related_name='booking_signatures',
    )

    # ── Za koga ───────────────────────────────────────────────
    company = models.ForeignKey(
        'companies.Company', on_delete=models.SET_NULL, null=True,
        related_name='booking_signatures',
    )
    workspace = models.ForeignKey(
        'companies.Workspace', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='booking_signatures',
    )

    # ── Što ────────────────────────────────────────────────────
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    target_model = models.CharField(max_length=100, db_index=True)
    target_id = models.CharField(max_length=100, blank=True)
    target_repr = models.CharField(max_length=300, blank=True,
        help_text='Čovjeku čitljiv opis objekta (npr. "Račun R-2026-0042")')

    # ── Promjene (samo diff) ──────────────────────────────────
    changes = models.JSONField(default=dict, blank=True,
        help_text='Samo promijenjeni fieldovi: {"amount": {"old": 100, "new": 150}}')

    # ── Odakle ────────────────────────────────────────────────
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    session_key = models.CharField(max_length=100, blank=True)

    # ── Potvrda ───────────────────────────────────────────────
    pin_verified = models.BooleanField(default=False,
        help_text='True ako je korisnik potvrdio PIN za ovu akciju')

    # ── Integritet ────────────────────────────────────────────
    integrity_hash = models.CharField(max_length=64, db_index=True,
        help_text='SHA256(user+action+target+timestamp+SECRET_SALT)')

    # ── Kad ────────────────────────────────────────────────────
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['company', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['target_model', 'target_id']),
        ]
        verbose_name = 'Audit potpis'
        verbose_name_plural = 'Audit potpisi'

    def __str__(self):
        return f"{self.action} {self.target_model}:{self.target_id} by {self.user_id} @ {self.timestamp}"

    def save(self, *args, **kwargs):
        # Append-only: blokira update postojećeg zapisa
        if self.pk:
            raise ValueError("BookingSignature entries cannot be modified.")
        # First save to get auto_now_add timestamp
        super().save(*args, **kwargs)
        # Now compute hash with real timestamp and update
        self._compute_hash()
        type(self).objects.filter(pk=self.pk).update(integrity_hash=self.integrity_hash)

    def delete(self, *args, **kwargs):
        raise ValueError("BookingSignature entries cannot be deleted.")

    def _compute_hash(self):
        import hashlib

        from django.conf import settings
        salt = getattr(settings, 'BOOKING_SIGNATURE_SALT', settings.SECRET_KEY[:32])
        raw = f"{self.user_id}|{self.action}|{self.target_model}|{self.target_id}|{self.timestamp}|{salt}"
        self.integrity_hash = hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def verify_integrity(self):
        """Provjeri da zapis nije mijenjan."""
        import hashlib

        from django.conf import settings
        salt = getattr(settings, 'BOOKING_SIGNATURE_SALT', settings.SECRET_KEY[:32])
        raw = f"{self.user_id}|{self.action}|{self.target_model}|{self.target_id}|{self.timestamp}|{salt}"
        expected = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        return self.integrity_hash == expected

    @classmethod
    def log(cls, request, action, target_obj=None, target_model=None, target_id=None,
            changes=None, pin_verified=False, target_repr=None):
        """
        Glavni API za logiranje akcija.

        Primjer:
            BookingSignature.log(request, 'book', target_obj=arhiva_entry,
                changes={'is_booked': {'old': False, 'new': True}})
        """
        from companies.models import Workspace

        user = request.user if request.user.is_authenticated else None
        company = getattr(request, 'company', None)

        # Workspace iz sesije
        ws_id = request.session.get('active_workspace_id')
        workspace = None
        if ws_id:
            try:
                workspace = Workspace.objects.get(pk=ws_id)
            except Workspace.DoesNotExist:
                pass

        # Target info
        if target_obj:
            target_model = target_obj.__class__.__name__
            target_id = str(target_obj.pk)
            if not target_repr:
                target_repr = str(target_obj)[:300]

        # IP
        ip = (request.META.get('HTTP_X_REAL_IP')
              or request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
              or request.META.get('REMOTE_ADDR', ''))

        return cls.objects.create(
            user=user,
            company=company,
            workspace=workspace,
            action=action,
            target_model=target_model or '',
            target_id=target_id or '',
            target_repr=target_repr or '',
            changes=changes or {},
            ip_address=ip or None,
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
            session_key=request.session.session_key or '',
            pin_verified=pin_verified,
        )


# ═══════════════════════════════════════════════════════════════════════════
# @audit_action decorator — za view-ove koji zahtijevaju audit trail
# ═══════════════════════════════════════════════════════════════════════════

def audit_action(action_name, target_param='pk', target_model_name=None):
    """
    Dekorator za view-ove koji trebaju BookingSignature zapis.

    @audit_action('book')
    def proknjizi(request, pk):
        ...

    @audit_action('delete', target_param='entry_id')
    def obrisi(request, entry_id):
        ...
    """
    import functools

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Extract target ID from kwargs
            target_id = kwargs.get(target_param, args[0] if args else '')

            # Execute view
            response = view_func(request, *args, **kwargs)

            # Log after successful execution (status < 400)
            if hasattr(response, 'status_code') and response.status_code < 400:
                try:
                    BookingSignature.log(
                        request=request,
                        action=action_name,
                        target_model=target_model_name or view_func.__module__.split('.')[0],
                        target_id=str(target_id),
                    )
                except (ValueError, TypeError):
                    pass  # Never let audit failure break the action

            return response
        return wrapper
    return decorator
