import secrets
import string

from django.db import models


def _gen_seal_token():
    """8-char alphanumeric token, URL-safe, uppercase."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


class ValidationLog(models.Model):
    TYPES = [("oib_hr", "OIB HR"), ("vat_eu", "VAT EU"), ("iban", "IBAN"), ("mbs", "MBS"), ("cross", "Cross")]
    validation_type = models.CharField(max_length=20, choices=TYPES)
    input_hash = models.CharField(max_length=64)
    is_valid = models.BooleanField()
    is_api_call = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    response_ms = models.IntegerField(default=0)

    class Meta:
        db_table = "evalidator_log"
        indexes = [models.Index(fields=["validation_type", "created_at"])]


class DocumentSeal(models.Model):
    """
    Digitalni pečat vjerodostojnosti dokumenta.

    Generira se pri slanju ili eksplicitnom pečaćenju dokumenta.
    Token je 8-char URL-safe kod koji se ugrađuje u QR i PDF footer.

    Zakonski okvir:
    - eIDAS Art. 41: electronic timestamp = pravna presumpcija integriteta
    - GoBD §14b: neopoziv, vremenski označen, dostupan na zahtjev
    - Croatian ZED (NN 150/05): digitalni dokument s timestampom = original

    Verifikacija: https://evalidator.eu/verify/<seal_token>/
    """

    # Identifikacija dokumenta
    seal_token = models.CharField(
        max_length=8,
        unique=True,
        default=_gen_seal_token,
        db_index=True,
        help_text="8-char kod (URL-safe). Embed u QR i PDF footer.",
    )
    sha256_hash = models.CharField(
        max_length=64, db_index=True, help_text="SHA-256 hex digest sadržaja datoteke pri pečaćenju."
    )

    # Veza na arhivski entry (optional — može biti i standalone)
    arhiva_entry_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    arhiva_company_id = models.PositiveIntegerField(null=True, blank=True)

    # Metapodaci dokumenta (denormalizirani za prikaz na verify stranici)
    doc_number = models.CharField(max_length=255, blank=True)
    doc_date = models.DateField(null=True, blank=True)
    partner_name = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, default="EUR")
    issuer_name = models.CharField(max_length=200, blank=True, help_text="Naziv firme koja je pečatila")
    issuer_country = models.CharField(max_length=2, blank=True, default="HR")

    # Timestamp i validnost
    sealed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sealed_by_user_id = models.PositiveIntegerField(null=True, blank=True)
    sealed_by_username = models.CharField(max_length=150, blank=True)
    expires_at = models.DateTimeField(
        null=True, blank=True, help_text="Null = trajno. Inače: datum isteka (npr. 10 godina GoBD)."
    )

    # Slanje
    send_channel = models.CharField(max_length=50, blank=True, help_text="email, whatsapp, portal, datev")
    viral_code = models.CharField(
        max_length=12, blank=True, db_index=True, help_text="Viralni kod za onboarding landing page"
    )

    # Audit
    verify_count = models.PositiveIntegerField(default=0, help_text="Koliko puta je verifikacijska stranica otvorena")
    last_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "evalidator_document_seal"
        ordering = ["-sealed_at"]
        indexes = [
            models.Index(fields=["sha256_hash"]),
            models.Index(fields=["viral_code"]),
            models.Index(fields=["arhiva_entry_id"]),
        ]

    def __str__(self):
        return f"Pečat {self.seal_token} — {self.doc_number or 'bez broja'} ({self.sealed_at.date()})"

    @property
    def is_valid(self):
        from django.utils import timezone

        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    @property
    def verify_url(self):
        return f"https://evalidator.eu/verify/{self.seal_token}/"



class PartnerPortal(models.Model):
    """
    Portal koji integrira evalidator.eu API (B2B partner).

    Primjeri:
    - Fenix V3 (interni, besplatan)
    - Synesis (bookkeeping SW)
    - RRIF (računovodstveni softver)
    - DATEV Connector (DE/AT)
    - Custom white-label reseller
    """
    PORTAL_TYPES = [
        ("internal",    "Interni (Fenix V3)"),
        ("reseller",    "Reseller / White-label"),
        ("integration", "Direktna integracija (API)"),
        ("affiliate",   "Affiliate (referral)"),
    ]

    name           = models.CharField(max_length=200, unique=True)
    portal_type    = models.CharField(max_length=20, choices=PORTAL_TYPES, default="integration")
    contact_email  = models.EmailField(blank=True)
    website        = models.URLField(blank=True)

    # API access
    master_api_key = models.CharField(max_length=64, unique=True, blank=True,
                                      help_text="SHA-256 hashed master key za portal-razinu")
    allowed_origins = models.TextField(blank=True,
                                       help_text="Newline-separated lista CORS origin-a (npr. https://synesis.hr)")

    # Kvote za portal (agregat svih njegovih korisnika)
    monthly_validation_limit = models.IntegerField(default=10_000)
    monthly_invoice_limit    = models.IntegerField(default=500)
    monthly_ocr_limit        = models.IntegerField(default=200)

    # Billing
    revenue_share_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                            help_text="% provizije za reseller model")
    stripe_customer_id = models.CharField(max_length=50, blank=True)

    # Branding (white-label)
    logo_url       = models.URLField(blank=True)
    primary_color  = models.CharField(max_length=7, blank=True, default="#C9A84C",
                                      help_text="Hex boja za branded landing stranicu")
    custom_domain  = models.CharField(max_length=200, blank=True,
                                      help_text="npr. validator.synesis.hr → CNAME na evalidator.eu")

    is_active      = models.BooleanField(default=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    notes          = models.TextField(blank=True)

    class Meta:
        db_table = "evalidator_partner_portal"
        verbose_name = "Partner Portal"

    def __str__(self):
        return f"{self.name} ({self.get_portal_type_display()})"


class SubscriptionPlan(models.Model):
    """
    Subscription tier za API korisnike evalidator.eu.
    Mapira na Stripe Product/Price ID za buduću naplatu.
    """
    PLAN_CODES = [
        ("free",       "Free"),
        ("starter",    "Starter (€9/mo)"),
        ("pro",        "Pro (€29/mo)"),
        ("enterprise", "Enterprise"),
    ]

    code          = models.CharField(max_length=20, choices=PLAN_CODES, unique=True)
    display_name  = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    price_annual  = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                        help_text="Godišnja cijena (≈ 20% popust = 10 mj)")

    # Kvote
    daily_validation_limit  = models.IntegerField(default=100,
                                                   help_text="Validacija/dan. -1 = unlimited")
    monthly_invoice_limit   = models.IntegerField(default=5,
                                                   help_text="E-računa/mj. -1 = unlimited")
    monthly_ocr_limit       = models.IntegerField(default=0,
                                                   help_text="OCR import/mj. -1 = unlimited")
    batch_max_items         = models.IntegerField(default=10,
                                                   help_text="Max stavki u batch validaciji")

    # Features (boolean flags)
    has_api_key       = models.BooleanField(default=False)
    has_eidas_seal    = models.BooleanField(default=False)
    has_peppol        = models.BooleanField(default=False)
    has_datev_export  = models.BooleanField(default=False)
    has_white_label   = models.BooleanField(default=False)
    has_sla_99_9      = models.BooleanField(default=False)
    pdf_watermark     = models.BooleanField(default=True,
                                            help_text="True = 'Demo' watermark na PDF-u")

    # Stripe
    stripe_price_id_monthly = models.CharField(max_length=50, blank=True)
    stripe_price_id_annual  = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = "evalidator_subscription_plan"
        ordering = ["price_monthly"]

    def __str__(self):
        return f"{self.display_name} ({self.price_monthly} €/mo)"




class APIKey(models.Model):
    """
    API ključ za evalidator.eu — per-user ili per-application.

    Korisnici mogu biti:
    1. Direktni korisnici evalidator.eu (registrirani na stranici)
    2. Korisnici partner portala (Synesis, RRIF, vlastiti SW)
    3. Interni Fenix V3 korisnici (portal=FenixV3PartnerPortal)
    """
    BILLING_CYCLE = [("monthly", "Mjesečno"), ("annual", "Godišnje")]

    # Identifikacija
    name       = models.CharField(max_length=200)
    email      = models.EmailField(db_index=True)
    key_hash   = models.CharField(max_length=64, unique=True,
                                  help_text="SHA-256 hash API ključa. Plain key prikazan samo jednom.")
    key_prefix = models.CharField(max_length=8, blank=True,
                                  help_text="Prvih 8 znakova za prikaz (ev_abc123X)")

    # Plan + portal
    plan       = models.ForeignKey("SubscriptionPlan", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="api_keys")
    portal     = models.ForeignKey("PartnerPortal", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="api_keys",
                                   help_text="Ako dolazi kroz partner portal, inače null")

    # Billing
    billing_cycle      = models.CharField(max_length=10, choices=BILLING_CYCLE, default="monthly")
    trial_ends_at      = models.DateTimeField(null=True, blank=True,
                                              help_text="14-day trial expiry. Null = trial nije aktivan.")
    subscription_start = models.DateField(null=True, blank=True)
    subscription_end   = models.DateField(null=True, blank=True,
                                          help_text="Null = active indefinitely (enterprise)")
    stripe_customer_id     = models.CharField(max_length=50, blank=True)
    stripe_subscription_id = models.CharField(max_length=50, blank=True)

    # Usage counters (soft denormalization — brže od JOIN-a)
    daily_used          = models.IntegerField(default=0)
    last_daily_reset    = models.DateField(auto_now_add=True)
    monthly_invoices    = models.IntegerField(default=0)
    monthly_ocr         = models.IntegerField(default=0)
    last_monthly_reset  = models.DateField(auto_now_add=True)
    total_validations   = models.BigIntegerField(default=0,
                                                  help_text="Životni broj validacija (za analytics)")
    total_invoices      = models.BigIntegerField(default=0)

    # Status
    is_active     = models.BooleanField(default=True)
    is_suspended  = models.BooleanField(default=False,
                                        help_text="Suspendiran zbog neplaćanja/zlouporabe")
    suspend_reason = models.CharField(max_length=200, blank=True)

    # Metapodaci
    company_name    = models.CharField(max_length=200, blank=True)
    company_country = models.CharField(max_length=2, blank=True, default="HR")
    oib             = models.CharField(max_length=11, blank=True)
    vat_id          = models.CharField(max_length=20, blank=True)
    webhook_url     = models.URLField(blank=True,
                                      help_text="POST na ovaj URL pri svakom generiranju računa")

    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "evalidator_apikey"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["trial_ends_at"]),
            models.Index(fields=["subscription_end"]),
        ]

    def __str__(self):
        plan_name = self.plan.code if self.plan else "free"
        return f"{self.email} [{plan_name}] (ev_{self.key_prefix}...)"

    @property
    def is_on_trial(self):
        from django.utils import timezone
        return self.trial_ends_at is not None and self.trial_ends_at > timezone.now()

    @property
    def effective_plan_code(self):
        """Free tier ako trial istekao i nema plaćenog plana."""
        if self.is_suspended:
            return "suspended"
        if self.plan:
            return self.plan.code
        return "free"

    def can_validate(self):
        """Provjeri dnevni limit validacija."""
        from django.utils import timezone
        today = timezone.now().date()
        if self.last_daily_reset < today:
            self.daily_used = 0
            self.last_daily_reset = today
            self.save(update_fields=["daily_used", "last_daily_reset"])
        if not self.is_active or self.is_suspended:
            return False
        limit = self.plan.daily_validation_limit if self.plan else 100
        if limit == -1:
            return True
        return self.daily_used < limit

    def can_generate_invoice(self):
        """Provjeri mjesečni limit e-računa."""
        from django.utils import timezone
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        if self.last_monthly_reset < first_of_month:
            self.monthly_invoices = 0
            self.monthly_ocr = 0
            self.last_monthly_reset = first_of_month
            self.save(update_fields=["monthly_invoices", "monthly_ocr", "last_monthly_reset"])
        if not self.is_active or self.is_suspended:
            return False
        limit = self.plan.monthly_invoice_limit if self.plan else 5
        if limit == -1:
            return True
        return self.monthly_invoices < limit

    def can_ocr(self):
        """Provjeri mjesečni OCR limit."""
        if not self.is_active or self.is_suspended:
            return False
        limit = self.plan.monthly_ocr_limit if self.plan else 0
        if limit == 0:
            return False
        if limit == -1:
            return True
        return self.monthly_ocr < limit

    def record_validation(self):
        APIKey.objects.filter(pk=self.pk).update(
            daily_used=models.F("daily_used") + 1,
            total_validations=models.F("total_validations") + 1,
        )

    def record_invoice(self):
        APIKey.objects.filter(pk=self.pk).update(
            monthly_invoices=models.F("monthly_invoices") + 1,
            total_invoices=models.F("total_invoices") + 1,
        )

    def record_ocr(self):
        APIKey.objects.filter(pk=self.pk).update(
            monthly_ocr=models.F("monthly_ocr") + 1,
        )


class APIUsageLog(models.Model):
    """
    Granularni log API poziva — za analytics, billing dispute resolution,
    i anomaly detection.

    Čuva se 90 dana, zatim arhivira u S3 / komprimira.
    """
    ENDPOINTS = [
        ("validate_oib",   "Validate OIB"),
        ("validate_vat",   "Validate VAT ID"),
        ("validate_iban",  "Validate IBAN"),
        ("validate_batch", "Batch Validation"),
        ("company_lookup", "Company Lookup"),
        ("invoice_gen",    "Invoice Generate"),
        ("invoice_ocr",    "Invoice OCR Import"),
        ("seal_create",    "Document Seal Create"),
        ("seal_verify",    "Seal Verify"),
    ]

    api_key   = models.ForeignKey(APIKey, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="usage_logs")
    portal    = models.ForeignKey(PartnerPortal, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="usage_logs")
    endpoint  = models.CharField(max_length=30, choices=ENDPOINTS)
    ip_hash   = models.CharField(max_length=16, blank=True,
                                 help_text="FNV hash IP-a (privacy-safe, ne čuva raw IP)")
    country   = models.CharField(max_length=2, blank=True)
    response_ms = models.SmallIntegerField(default=0)
    status_code = models.SmallIntegerField(default=200)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "evalidator_usage_log"
        indexes = [
            models.Index(fields=["api_key", "created_at"]),
            models.Index(fields=["endpoint", "created_at"]),
            models.Index(fields=["created_at"]),
        ]
        # Auto-delete after 90 days handled by Celery Beat task
        verbose_name = "Usage Log"
