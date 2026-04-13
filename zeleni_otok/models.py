import uuid

from django.db import models

from core.managers import CompanyManager


class CompetitorProfile(models.Model):
    """Profil konkurenta za usporednu analizu."""
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    vendor = models.CharField(max_length=200, blank=True)
    website = models.URLField(blank=True)
    country = models.CharField(max_length=5, default='HR')
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)

    # Pricing snapshot
    price_entry = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='Najniža cijena (EUR/mj)')
    price_top = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='Najviša cijena (EUR/mj)')

    # Feature flags (what competitor HAS)
    has_fiscalization = models.BooleanField(default=False)
    has_einvoice = models.BooleanField(default=False)
    has_payroll = models.BooleanField(default=False)
    has_inventory = models.BooleanField(default=False)
    has_pos = models.BooleanField(default=False)
    has_manufacturing = models.BooleanField(default=False)
    has_api = models.BooleanField(default=False)
    has_mobile_app = models.BooleanField(default=False)
    has_ai_features = models.BooleanField(default=False)
    has_multi_org = models.BooleanField(default=False)
    has_verticals = models.BooleanField(default=False)
    has_unlimited_invoices = models.BooleanField(default=False)
    has_unlimited_payroll = models.BooleanField(default=False)
    has_free_migration = models.BooleanField(default=False)
    data_retention_years = models.PositiveIntegerField(default=5)

    # Weaknesses (for comparison page)
    weaknesses = models.JSONField(default=list, blank=True, help_text='Lista slabosti za prikaz')

    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Competitor Profile'
        verbose_name_plural = 'Competitor Profiles'
        ordering = ['name']

    def __str__(self):
        return self.name


class ComparisonFeature(models.Model):
    """Pojedinačna feature za usporednu tablicu."""
    CATEGORY_CHOICES = [
        ('invoicing', 'Fakturiranje'),
        ('accounting', 'Knjigovodstvo'),
        ('payroll', 'Plaće'),
        ('inventory', 'Zalihe'),
        ('pos', 'POS / Blagajna'),
        ('ai', 'AI funkcije'),
        ('compliance', 'Usklađenost'),
        ('support', 'Podrška'),
        ('pricing', 'Cijene'),
        ('data', 'Podaci i sigurnost'),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    name = models.CharField(max_length=200)
    name_de = models.CharField(max_length=200, blank=True)
    name_en = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Font Awesome class')
    sort_order = models.PositiveIntegerField(default=0)

    # LC status
    lc_available = models.BooleanField(default=True)
    lc_note = models.CharField(max_length=200, blank=True, help_text='Npr. "AI-powered" ili "Neograničeno"')

    is_highlight = models.BooleanField(default=False, help_text='Istaknuti kao prednost LC-a')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Comparison Feature'
        verbose_name_plural = 'Comparison Features'
        ordering = ['category', 'sort_order']

    def __str__(self):
        return f'{self.get_category_display()}: {self.name}'


class CompetitorFeatureStatus(models.Model):
    """Status specifičnog featurea kod konkurenta."""
    STATUS_CHOICES = [
        ('yes', 'Da'),
        ('no', 'Ne'),
        ('partial', 'Djelomično'),
        ('paid', 'Uz doplatu'),
        ('limited', 'Ograničeno'),
    ]

    competitor = models.ForeignKey(CompetitorProfile, on_delete=models.CASCADE, related_name='feature_statuses')
    feature = models.ForeignKey(ComparisonFeature, on_delete=models.CASCADE, related_name='competitor_statuses')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='no')
    note = models.CharField(max_length=200, blank=True, help_text='Npr. "Max 500/mj"')

    class Meta:
        verbose_name = 'Competitor Feature Status'
        verbose_name_plural = 'Competitor Feature Statuses'
        unique_together = ['competitor', 'feature']

    def __str__(self):
        return f'{self.competitor.name} — {self.feature.name}: {self.get_status_display()}'


class MigrationRequest(models.Model):
    """Zahtjev za migraciju iz drugog sustava u LC."""
    STATUS_CHOICES = [
        ('submitted', 'Zaprimljeno'),
        ('analyzing', 'Analiza u tijeku'),
        ('mapping', 'Mapiranje podataka'),
        ('importing', 'Import u tijeku'),
        ('verifying', 'Verifikacija'),
        ('completed', 'Završeno'),
        ('failed', 'Neuspjelo'),
    ]

    SOURCE_CHOICES = [
        ('minimax', 'Minimax (Seyfor)'),
        ('luceed', 'Luceed'),
        ('pantheon', 'Datalab Pantheon'),
        ('synesis', 'Synesis'),
        ('excel', 'Excel / CSV'),
        ('other', 'Drugi sustav'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Tko migrira
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='migration_requests'
    )
    contact_name = models.CharField(max_length=200)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=50, blank=True)
    company_name = models.CharField(max_length=200, help_text='Naziv tvrtke koja migrira')
    oib = models.CharField(max_length=20, blank=True)

    # Odakle
    source_system = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='minimax')
    source_version = models.CharField(max_length=50, blank=True)
    source_plan = models.CharField(max_length=100, blank=True, help_text='Npr. "Maksi računovodstvo"')

    # Što migrirati
    migrate_partners = models.BooleanField(default=True, verbose_name='Partneri')
    migrate_articles = models.BooleanField(default=True, verbose_name='Artikli')
    migrate_chart_of_accounts = models.BooleanField(default=True, verbose_name='Kontni plan')
    migrate_opening_balances = models.BooleanField(default=True, verbose_name='Početna salda')
    migrate_invoices = models.BooleanField(default=False, verbose_name='Povijesni računi')
    migrate_fixed_assets = models.BooleanField(default=False, verbose_name='Osnovna sredstva')
    migrate_employees = models.BooleanField(default=False, verbose_name='Zaposlenici')

    # Upload
    upload_file = models.FileField(upload_to='migrations/uploads/', blank=True, null=True)
    upload_format = models.CharField(max_length=20, blank=True, help_text='xml, csv, json, mdb')

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    status_message = models.TextField(blank=True)

    # Rezultati
    records_found = models.JSONField(default=dict, blank=True, help_text='{"partners": 150, "articles": 500, ...}')
    records_imported = models.JSONField(default=dict, blank=True)
    records_skipped = models.JSONField(default=dict, blank=True)
    mapping_log = models.JSONField(default=list, blank=True, help_text='Log mapiranja i transformacija')
    validation_errors = models.JSONField(default=list, blank=True)

    # Verifikacija
    verification_report = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verified_migrations'
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    # Referral
    referral_code = models.CharField(max_length=50, blank=True)

    # Meta
    assigned_to = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_migrations'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Migration Request'
        verbose_name_plural = 'Migration Requests'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.company_name} ({self.get_source_system_display()}) [{self.get_status_display()}]'

    @property
    def progress_percent(self):
        status_progress = {
            'submitted': 10,
            'analyzing': 25,
            'mapping': 50,
            'importing': 75,
            'verifying': 90,
            'completed': 100,
            'failed': 0,
        }
        return status_progress.get(self.status, 0)


class ReferralProgram(models.Model):
    """Referral program — postojeći korisnik preporuči novog."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Tko preporuča
    referrer_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='referral_codes_given'
    )
    referrer_user = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True
    )

    # Kod
    code = models.CharField(max_length=30, unique=True)

    # Nagrada
    REWARD_CHOICES = [
        ('free_month', '1 mjesec gratis'),
        ('free_months_3', '3 mjeseca gratis'),
        ('discount_20', '20% popust trajno'),
        ('credit', 'Kredit na račun'),
    ]
    reward_type = models.CharField(max_length=20, choices=REWARD_CHOICES, default='free_month')
    reward_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text='Za credit tip')

    # Statistika
    times_shared = models.PositiveIntegerField(default=0)
    times_used = models.PositiveIntegerField(default=0)
    total_revenue_generated = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Limiti
    max_uses = models.PositiveIntegerField(default=0, help_text='0 = neograničeno')
    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = 'Referral Code'
        verbose_name_plural = 'Referral Codes'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} ({self.referrer_company.name})'

    @staticmethod
    def generate_code(company_name=''):
        import random
        import string
        prefix = ''.join(c for c in company_name[:4].upper() if c.isalpha()) or 'LC'
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f'{prefix}-{suffix}'

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


class ReferralRedemption(models.Model):
    """Evidencija korištenja referral koda."""
    referral = models.ForeignKey(ReferralProgram, on_delete=models.CASCADE, related_name='redemptions')
    new_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='referral_used'
    )
    reward_applied = models.BooleanField(default=False)
    reward_description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Referral Redemption'
        verbose_name_plural = 'Referral Redemptions'
        unique_together = ['referral', 'new_company']

    def __str__(self):
        return f'{self.new_company.name} via {self.referral.code}'


class FreeToolUsage(models.Model):
    """Praćenje korištenja besplatnih alata (lead gen)."""
    TOOL_CHOICES = [
        ('pdv_calc', 'PDV Kalkulator'),
        ('oib_lookup', 'OIB Provjera'),
        ('r1_validator', 'R-1 Validator'),
        ('eracun_tester', 'E-Račun Tester'),
        ('roi_calculator', 'ROI Kalkulator'),
        ('tax_calendar', 'Porezni Kalendar'),
        ('compare_pricing', 'Usporedi Cjenike'),
    ]

    tool = models.CharField(max_length=30, choices=TOOL_CHOICES)
    session_id = models.CharField(max_length=64, blank=True, help_text='Anonymous session tracking')
    ip_hash = models.CharField(max_length=64, blank=True, help_text='SHA256 of IP for analytics')

    # Optional lead capture
    email = models.EmailField(blank=True)
    company_name = models.CharField(max_length=200, blank=True)

    # Usage data
    input_data = models.JSONField(default=dict, blank=True, help_text='Što je korisnik unio (anonimno)')
    result_summary = models.CharField(max_length=500, blank=True)

    # Conversion
    converted_to_signup = models.BooleanField(default=False)
    converted_at = models.DateTimeField(null=True, blank=True)

    # UTM
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Free Tool Usage'
        verbose_name_plural = 'Free Tool Usage'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tool', 'created_at']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f'{self.get_tool_display()} — {self.created_at:%Y-%m-%d %H:%M}'


class SwitchWeekCampaign(models.Model):
    """'Switch Week' kampanja — periodična akcija za migraciju."""
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=50, unique=True)

    start_date = models.DateField()
    end_date = models.DateField()

    free_migration = models.BooleanField(default=True)
    free_months = models.PositiveIntegerField(default=3)
    bonus_description = models.TextField(blank=True)

    # Landing page content
    hero_title = models.CharField(max_length=200, blank=True)
    hero_subtitle = models.TextField(blank=True)
    cta_text = models.CharField(max_length=100, default='Prebaci se besplatno')

    # Stats
    signups = models.PositiveIntegerField(default=0)
    migrations_started = models.PositiveIntegerField(default=0)
    migrations_completed = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Switch Week Campaign'
        verbose_name_plural = 'Switch Week Campaigns'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.name} ({self.start_date} — {self.end_date})'

    @property
    def is_running(self):
        from datetime import date
        return self.is_active and self.start_date <= date.today() <= self.end_date
