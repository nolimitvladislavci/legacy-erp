import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.managers import CompanyManager


class CompanyRegistration(models.Model):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    STATUS_CHOICES = [
        (PENDING, _('Pending')),
        (APPROVED, _('Approved')),
        (REJECTED, _('Rejected')),
    ]

    BUSINESS_TYPES = [
        ('doo', 'd.o.o.'),
        ('jdoo', 'j.d.o.o.'),
        ('obrt', 'Obrt'),
        ('dd', 'd.d.'),
        ('sp', 's.p.'),
        ('eu', 'EU company'),
        ('other', 'Other'),
    ]

    PLAN_CHOICES = [
        ('micro', 'Micro – €4/mj'),
        ('starter', 'Starter – €9/mj'),
        ('professional', 'Professional – €29/mj'),
        ('enterprise', 'Enterprise – €79/mj'),
        ('distributor', 'Distributor – €149/mj'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Company info
    name = models.CharField(max_length=200)
    oib = models.CharField(max_length=20, unique=True)
    country = models.CharField(max_length=100, default='Croatia')
    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPES, default='doo')
    address = models.TextField()

    # Contact
    contact_name = models.CharField(max_length=200)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=50)

    # Document
    document = models.FileField(upload_to='registrations/documents/', blank=True, null=True)

    # Plan selected during registration
    selected_plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='starter')

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='reviewed_registrations'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Company Registration'
        verbose_name_plural = 'Company Registrations'

    def __str__(self):
        return f"{self.name} [{self.status}]"

    @property
    def is_pending(self):
        return self.status == self.PENDING

    @property
    def is_approved(self):
        return self.status == self.APPROVED

    @property
    def is_rejected(self):
        return self.status == self.REJECTED



class PricingPlan(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    name_de = models.CharField(max_length=100, blank=True)
    name_en = models.CharField(max_length=100, blank=True)
    tagline = models.CharField(max_length=200, blank=True)
    tagline_de = models.CharField(max_length=200, blank=True)
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="EUR")
    max_users = models.PositiveIntegerField(default=3)
    max_locations = models.PositiveIntegerField(default=1)
    max_invoices_per_month = models.PositiveIntegerField(default=50)
    max_articles = models.PositiveIntegerField(default=100)
    storage_mb = models.PositiveIntegerField(default=500)
    included_modules = models.JSONField(default=list, help_text="List of module slugs included")
    has_fiscalization = models.BooleanField(default=False)
    has_whatsapp = models.BooleanField(default=False)
    has_api_access = models.BooleanField(default=False)
    has_premium_support = models.BooleanField(default=False)
    has_custom_branding = models.BooleanField(default=False)
    is_popular = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Pricing Plan"
        verbose_name_plural = "Pricing Plans"

    def __str__(self):
        return f"{self.name} ({self.price_monthly} {self.currency}/mo)"

class CompanySubscription(models.Model):
    PLAN_CHOICES = [
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('business', 'Business'),  # legacy
        ('enterprise', 'Enterprise'),
        ('micro', 'Micro'),
        ('distributor', 'Distributor'),
        ('archive_readonly', 'Arhiva (read-only)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES)
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    monthly_fee = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    pricing_plan = models.ForeignKey(
        PricingPlan, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="subscriptions",
        verbose_name="Pricing Plan",
    )
    trial_ends = models.DateField(null=True, blank=True, verbose_name="Trial End Date")
    billing_cycle = models.CharField(
        max_length=10,
        choices=[("monthly", "Monthly"), ("yearly", "Yearly")],
        default="monthly",
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    modules_override = models.JSONField(null=True, blank=True, help_text="Custom module list; overrides plan if set")
    promo_code = models.ForeignKey(
        'PromoCode', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Korišteni promo kod',
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        verbose_name='Otkaži na kraju perioda',
        help_text='Pretplata ostaje aktivna do valid_until, zatim auto-downgrade na archive_readonly',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Datum otkazivanja')

    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Company Subscription'
        verbose_name_plural = 'Company Subscriptions'

    def __str__(self):
        status = 'active' if self.is_active else 'inactive'
        return f"{self.company.name} – {self.plan} ({status})"

    @property
    def is_trial(self):
        from datetime import date
        return self.trial_ends is not None and self.trial_ends >= date.today()

    @property
    def allowed_modules(self):
        if self.modules_override is not None:
            return set(self.modules_override)
        if self.pricing_plan_id and self.pricing_plan:
            return set(self.pricing_plan.included_modules or [])
        from registration.constants import PLAN_MODULES
        return PLAN_MODULES.get(self.plan, set())

    def has_module(self, module_name):
        return module_name in self.allowed_modules

    def cancel(self):
        """Otkaži pretplatu na kraju perioda. Arhiva ostaje dostupna (ZOR 11g)."""
        from django.utils import timezone
        self.cancel_at_period_end = True
        self.cancelled_at = timezone.now()
        self.save(update_fields=['cancel_at_period_end', 'cancelled_at'])

    def reactivate(self):
        """Poništi otkazivanje."""
        self.cancel_at_period_end = False
        self.cancelled_at = None
        self.save(update_fields=['cancel_at_period_end', 'cancelled_at'])

    @property
    def is_cancelled(self):
        return self.cancel_at_period_end

class PromoCode(models.Model):
    """Promo / gutschein kod za popust ili besplatne module pri registraciji."""
    TYPE_CHOICES = [
        ('discount_percent', 'Popust (%)'),
        ('discount_fixed', 'Popust (fiksni EUR)'),
        ('free_months', 'Besplatni mjeseci'),
        ('plan_upgrade', 'Upgrade plana'),
        ('full_access', 'Puni pristup (svi moduli)'),
    ]

    code              = models.CharField(max_length=50, unique=True, verbose_name='Kod')
    name              = models.CharField(max_length=200, verbose_name='Naziv/Opis')
    promo_type        = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='Tip')
    discount_percent  = models.PositiveIntegerField(default=0, verbose_name='Popust %')
    discount_amount   = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='Popust iznos (EUR)')
    free_months       = models.PositiveIntegerField(default=0, verbose_name='Besplatni mjeseci')
    target_plan       = models.CharField(max_length=20, blank=True, verbose_name='Ciljani plan (za upgrade)')
    max_uses          = models.PositiveIntegerField(default=0, verbose_name='Max korištenja (0=neograničeno)')
    times_used        = models.PositiveIntegerField(default=0, verbose_name='Korišteno puta')
    valid_from        = models.DateTimeField(null=True, blank=True)
    valid_until       = models.DateTimeField(null=True, blank=True)
    is_active         = models.BooleanField(default=True)
    is_superadmin_code = models.BooleanField(default=False, verbose_name='Superadmin kod (puni pristup)')
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Promo kod'
        verbose_name_plural = 'Promo kodovi'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} ({self.get_promo_type_display()})"

    def is_valid(self):
        if not self.is_active:
            return False
        if self.max_uses > 0 and self.times_used >= self.max_uses:
            return False
        from django.utils import timezone
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True

    def apply_to_subscription(self, subscription):
        if not self.is_valid():
            return False, "Kod nije validan"
        if self.promo_type == 'discount_percent':
            original = subscription.monthly_fee
            from decimal import Decimal
            discount = original * Decimal(self.discount_percent) / Decimal('100')
            subscription.monthly_fee = max(Decimal('0'), original - discount)
            subscription.save(update_fields=['monthly_fee'])
        elif self.promo_type == 'discount_fixed':
            from decimal import Decimal
            subscription.monthly_fee = max(Decimal('0'), subscription.monthly_fee - self.discount_amount)
            subscription.save(update_fields=['monthly_fee'])
        elif self.promo_type == 'free_months':
            from datetime import timedelta

            from django.utils import timezone
            if subscription.trial_ends:
                subscription.trial_ends += timedelta(days=30 * self.free_months)
            else:
                subscription.trial_ends = timezone.now().date() + timedelta(days=30 * self.free_months)
            subscription.save(update_fields=['trial_ends'])
        elif self.promo_type == 'plan_upgrade' and self.target_plan:
            subscription.plan = self.target_plan
            try:
                new_plan = PricingPlan.objects.get(slug=self.target_plan)
                subscription.pricing_plan = new_plan
            except PricingPlan.DoesNotExist:
                pass
            subscription.save(update_fields=['plan', 'pricing_plan'])
        elif self.promo_type == 'full_access' or self.is_superadmin_code:
            subscription.plan = 'enterprise'
            try:
                ent_plan = PricingPlan.objects.get(slug='enterprise')
                subscription.pricing_plan = ent_plan
            except PricingPlan.DoesNotExist:
                pass
            from decimal import Decimal
            subscription.monthly_fee = Decimal('0')
            subscription.save(update_fields=['plan', 'pricing_plan', 'monthly_fee'])
        self.times_used += 1
        self.save(update_fields=['times_used'])
        return True, "Kod primijenjen"



class PropterTenant(models.Model):
    """SaaS tenant for Propter e-invoicing gateway."""
    TIER_CHOICES = [
        ('client', 'Direktni klijent (30-80 EUR/mj)'),
        ('bookkeeper', 'Knjigovodstveni servis (150-200 EUR/mj)'),
    ]
    CERT_STATUS_CHOICES = [
        ('none', 'Nema certifikata'),
        ('pending', 'Zahtjev poslan'),
        ('active', 'Aktivan'),
        ('expiring', 'Istice uskoro'),
        ('expired', 'Istekao'),
    ]

    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='propter_tenant'
    )
    operator_name = models.CharField(
        max_length=200, blank=True,
        verbose_name='Operator / knjigovodstveni servis',
        help_text='Npr. KS Limit d.o.o.'
    )
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='client', verbose_name='Tip pretplate')
    max_companies = models.PositiveIntegerField(
        default=1, verbose_name='Max tvrtki',
        help_text='Za bookkeepere: koliko klijenata mogu voditi'
    )
    fina_cert_status = models.CharField(
        max_length=15, choices=CERT_STATUS_CHOICES,
        default='none', verbose_name='Status FINA certifikata'
    )
    modules_enabled = models.JSONField(default=list, verbose_name='Omoguceni moduli')
    monthly_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='Mjesecna naknada (EUR)')
    billing_day = models.PositiveIntegerField(default=1, verbose_name='Dan fakturiranja')
    next_billing = models.DateField(null=True, blank=True, verbose_name='Sljedece fakturiranje')
    eracuni_sent_total = models.PositiveIntegerField(default=0, verbose_name='Ukupno poslanih e-racuna')
    eracuni_sent_month = models.PositiveIntegerField(default=0, verbose_name='e-Racuna ovaj mjesec')
    is_active = models.BooleanField(default=True, verbose_name='Aktivan')
    notes = models.TextField(blank=True, verbose_name='Napomene')

    # Self-referential: bookkeeper manages client tenants
    managed_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_tenants',
        verbose_name='Upravljano od',
        help_text='Knjigovodstveni servis koji upravlja ovom tvrtkom'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Propter korisnik'
        verbose_name_plural = 'Propter korisnici'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.company.name} ({self.get_tier_display()})'


# AUTO-SYNC: registration.PropterTenant --> propter.PropterConfig
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=PropterTenant, dispatch_uid='propter_config_sync')
def sync_propter_config(sender, instance, created, **kwargs):
    try:
        from propter.models import PropterConfig
        tier_map = {
            'client': 'client',
            'bookkeeper': 'bookkeeper',
            'operator': 'operator',
        }
        cert_map = {
            'none': 'none',
            'pending': 'pending',
            'active': 'active',
            'expired': 'expired',
        }
        PropterConfig.objects.update_or_create(
            company=instance.company,
            defaults={
                'tier': tier_map.get(instance.tier, 'client'),
                'cert_status': cert_map.get(instance.fina_cert_status, 'none'),
                'monthly_fee': instance.monthly_fee,
                'max_clients': instance.max_companies,
                'is_active': True,
            }
        )
    except Exception as e:
        import logging
        logging.getLogger('propter').warning('PropterConfig sync greska: %s', e)


class UmbrellaInviteCode(models.Model):
    """Invite code generated by umbrella company for child registration."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    umbrella_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='invite_codes',
        verbose_name='Umbrella tvrtka',
    )
    code = models.CharField(max_length=20, unique=True, verbose_name='Pozivni kod')
    plan_slug = models.CharField(max_length=20, default='starter', verbose_name='Plan za novu firmu')
    relation_type = models.CharField(
        max_length=20, default='client',
        choices=[
            ('subsidiary', 'Podružnica'),
            ('client', 'Klijent (knjigovodstvo)'),
            ('franchise', 'Franšiza'),
        ],
        verbose_name='Tip veze',
    )
    max_uses = models.PositiveIntegerField(default=1, verbose_name='Max korištenja')
    times_used = models.PositiveIntegerField(default=0, verbose_name='Korišteno puta')
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Kreirao',
    )
    modules_override = models.JSONField(
        null=True, blank=True,
        verbose_name='Custom moduli (override plana)',
    )
    free_months = models.PositiveIntegerField(default=1, verbose_name='Besplatnih mjeseci')
    note = models.CharField(max_length=200, blank=True, verbose_name='Napomena')
    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = 'Umbrella pozivni kod'
        verbose_name_plural = 'Umbrella pozivni kodovi'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} ({self.umbrella_company.name})'

    def is_valid(self):
        if not self.is_active:
            return False
        if self.max_uses > 0 and self.times_used >= self.max_uses:
            return False
        if self.valid_until:
            from django.utils import timezone
            if timezone.now() > self.valid_until:
                return False
        return True

    @staticmethod
    def generate_code():
        import random, string
        return 'UC-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))



class SalesLead(models.Model):
    """Sales wizard — kompletni onboarding flow za novog klijenta."""
    STATUS_CHOICES = [
        ('draft', 'U pripremi'),
        ('signed', 'Potpisan'),
        ('active', 'Aktivan'),
        ('rejected', 'Odbijen'),
    ]

    # Basic info
    company_name = models.CharField(max_length=200)
    oib = models.CharField(max_length=20, blank=True)
    contact_name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=5, default='HR')

    # Business
    business_type = models.CharField(max_length=30, default='obrt')
    plan = models.CharField(max_length=30, default='professional')
    modules = models.JSONField(default=list, blank=True)

    # Signature
    signature_b64 = models.TextField(blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.CharField(max_length=200, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    agent = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_leads')
    notes = models.TextField(blank=True)
    ref_code = models.CharField(max_length=50, blank=True, verbose_name='Referral kod')
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=15, verbose_name='Provizija %')
    is_disability_ambassador = models.BooleanField(default=False, verbose_name='NO LIMIT Ambasador')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sales Lead'
        verbose_name_plural = 'Sales Leads'

    def __str__(self):
        return f'{self.company_name} ({self.status})'


@receiver(post_save, sender=SalesLead, dispatch_uid='ambassador_onboarding_email')
def _on_ambassador_flag_set(sender, instance, created, **kwargs):
    """Kad se is_disability_ambassador uključi → šalji onboarding mail."""
    if not instance.is_disability_ambassador or not instance.contact_email:
        return
    # Šalji samo kad se flag upravo uključio (novi lead ili update)
    update_fields = kwargs.get('update_fields')
    if not created and update_fields and 'is_disability_ambassador' not in update_fields:
        return
    from registration.tasks import send_ambassador_onboarding_email
    send_ambassador_onboarding_email.apply_async(args=[instance.pk], countdown=5)


# ════════════════════════════════════════════════════════════════════
# Claim Your Business — 71 ghost firma dobiva pristup
# ════════════════════════════════════════════════════════════════════

import secrets as _secrets


class CompanyClaimRequest(models.Model):
    """
    Zahtjev za pristup firmi koja već postoji u sustavu (importirana iz Synesisa).

    Tri ulaza:
      A) Vlasnik sam traži: /firma/preuzmi/<id>/ → pending → Marija odobri
      B) Marija šalje invite link: /firma/aktiviraj/<token>/ → vlasnik postavi lozinku
      C) Bulk invite: management command → CSV s linkovima za WhatsApp
    """
    STATUS_CHOICES = [
        ('pending',  'Čeka odobrenje'),
        ('approved', 'Odobreno'),
        ('rejected', 'Odbijeno'),
        ('expired',  'Isteklo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='claim_requests',
    )

    # Podaci vlasnika
    email = models.EmailField()
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    # Verifikacija
    oib_confirmed = models.BooleanField(default=False)
    role_claimed = models.CharField(max_length=50, default='company_admin')

    # Token za invite link
    verify_token = models.CharField(
        max_length=64, unique=True,
        default='',
    )
    token_expires = models.DateTimeField()

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_claims',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.CharField(max_length=300, blank=True)

    # Rezultat
    created_user = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_from_claim',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.verify_token:
            self.verify_token = _secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'company_claim_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['email', 'status']),
        ]

    def __str__(self):
        return f'{self.email} → {self.company.name} [{self.status}]'

    @property
    def is_token_valid(self):
        from django.utils import timezone
        return self.status == 'pending' and timezone.now() < self.token_expires

    def approve(self, reviewed_by):
        """
        Odobri zahtjev: kreira User + UserProfile + CompanyMembership.
        Vraća (user, temp_password).
        """
        from django.contrib.auth.models import User
        from django.db import transaction
        from django.utils import timezone
        from accounts.models import UserProfile, CompanyMembership

        with transaction.atomic():
            # Username iz emaila
            base_un = self.email.split('@')[0].lower().replace('.', '_')[:25]
            username = base_un
            i = 1
            while User.objects.filter(username=username).exists():
                username = f'{base_un}{i}'
                i += 1

            temp_password = _secrets.token_urlsafe(12)
            user = User.objects.create_user(
                username=username,
                email=self.email,
                password=temp_password,
                first_name=self.first_name,
                last_name=self.last_name,
            )

            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'company': self.company,
                    'role': self.role_claimed,
                    'email_verified': True,
                    'must_change_password': True,
                },
            )

            CompanyMembership.objects.get_or_create(
                user=user, company=self.company,
                defaults={'role': self.role_claimed, 'is_active': True, 'is_default': True},
            )

            # RBAC
            try:
                from permissions.models import Role, UserRole
                role = Role.objects.filter(role_type=self.role_claimed).first()
                if role:
                    UserRole.objects.get_or_create(
                        user=user, role=role, company=self.company,
                        defaults={'is_primary': True},
                    )
            except Exception:
                pass

            self.status = 'approved'
            self.reviewed_by = reviewed_by
            self.reviewed_at = timezone.now()
            self.created_user = user
            self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'created_user'])

        return user, temp_password


class DistributorApplication(models.Model):
    """Prijava za distributer/reseller partnera — /postani-distributer/."""
    STATUS_CHOICES = [
        ('pending', 'Na čekanju'),
        ('approved', 'Odobreno'),
        ('rejected', 'Odbijeno'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_name = models.CharField(max_length=200, verbose_name='Naziv tvrtke')
    oib = models.CharField(max_length=20, blank=True, verbose_name='OIB')
    contact_name = models.CharField(max_length=200, verbose_name='Kontakt osoba')
    email = models.EmailField(verbose_name='Email')
    phone = models.CharField(max_length=50, verbose_name='Telefon')
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=5, default='HR')

    # Poslovni detalji
    existing_clients = models.PositiveIntegerField(default=0,
        verbose_name='Koliko klijenata trenutno imate?')
    target_segment = models.CharField(max_length=200, blank=True,
        verbose_name='Ciljni segment (obrti, ugostiteljstvo, udruge...)')
    motivation = models.TextField(blank=True,
        verbose_name='Zašto želite postati distributer?')
    website = models.URLField(blank=True)

    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Auto WL setup after approval
    whitelabel_subdomain = models.CharField(max_length=50, blank=True,
        verbose_name='WhiteLabel subdomena (automatski)')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Distributer prijava'
        verbose_name_plural = 'Distributer prijave'

    def __str__(self):
        return f"{self.company_name} ({self.status})"
