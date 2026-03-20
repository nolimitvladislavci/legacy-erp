"""
Propter models -- Faza A + B

Faza A: BillingPeriod, Otpremnica, OtpremnicaItem
Faza B: PropterTenant, PropterOperator
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone


# =============================================================================
# FAZA A -- BillingPeriod + Otpremnica
# =============================================================================

class BillingPeriod(models.Model):
    """Obracunski period (mjesec) per firma.
    Skuplja otpremnice kroz cijeli mjesec.
    Na kraju perioda aggregate_to_eracun() kreira jedan zbirni e-Racun.
    """

    class Status(models.TextChoices):
        OPEN      = "open",     "Otvoren"
        CLOSING   = "closing",  "Zatvara se"
        CLOSED    = "closed",   "Zatvoren"
        INVOICED  = "invoiced", "Fakturiran"

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="billing_periods"
    )
    year  = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()  # 1-12

    status      = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    opened_at   = models.DateTimeField(auto_now_add=True)
    closed_at   = models.DateTimeField(null=True, blank=True)
    invoiced_at = models.DateTimeField(null=True, blank=True)

    # Zbirni e-Racun kreiran na kraju perioda (FK na eracun.ERacun)
    zbirni_eracun_id     = models.CharField(max_length=64, blank=True, db_index=True)
    zbirni_invoice_number = models.CharField(max_length=100, blank=True)

    # Snapshot iznosa pri zatvaranju
    total_net        = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_tax        = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_with_tax   = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    otpremnica_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("company", "year", "month")
        ordering = ["-year", "-month"]
        verbose_name = "Obracunski period"
        verbose_name_plural = "Obracunski periodi"

    def __str__(self):
        return "{} {}/{:02d} ({})".format(
            self.company.name, self.year, self.month, self.get_status_display()
        )

    @classmethod
    def get_or_create_current(cls, company):
        now = timezone.now()
        period, _ = cls.objects.get_or_create(
            company=company, year=now.year, month=now.month,
            defaults={"status": cls.Status.OPEN}
        )
        return period


class Otpremnica(models.Model):
    """Otpremnica (delivery note).
    Izvor: POS zatvaranje smjene, rucni unos, Synesis sync, API.
    Agregira se na kraju perioda u jedan zbirni e-Racun.
    """

    class Status(models.TextChoices):
        DRAFT      = "draft",      "Nacrt"
        ISSUED     = "issued",     "Izdana"
        AGGREGATED = "aggregated", "Ukljucena u zbirni racun"
        CANCELLED  = "cancelled",  "Stornirana"

    class Source(models.TextChoices):
        POS     = "pos",     "POS blagajna"
        MANUAL  = "manual",  "Rucni unos"
        SYNESIS = "synesis", "Synesis"
        API     = "api",     "API"
        INVOICE = "invoice", "Faktura"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="otpremnice"
    )
    billing_period = models.ForeignKey(
        BillingPeriod, on_delete=models.PROTECT,
        related_name="otpremnice", null=True, blank=True
    )

    # Veze na izvorne dokumente (opcionalno -- loose coupling)
    pos_receipt_id = models.CharField(max_length=64, blank=True, db_index=True)
    invoice_id     = models.CharField(max_length=64, blank=True, db_index=True)

    number        = models.CharField(max_length=50, verbose_name="Broj otpremnice")
    issue_date    = models.DateField()
    delivery_date = models.DateField(null=True, blank=True)

    recipient_name    = models.CharField(max_length=200)
    recipient_oib     = models.CharField(max_length=20, blank=True)
    recipient_address = models.CharField(max_length=300, blank=True)

    subtotal   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total      = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    note   = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-issue_date", "-created_at"]
        verbose_name = "Otpremnica"
        verbose_name_plural = "Otpremnice"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "billing_period"]),
            models.Index(fields=["issue_date"]),
        ]

    def __str__(self):
        return "OTP-{} -> {} ({} EUR)".format(self.number, self.recipient_name, self.total)

    def save(self, **kwargs):
        if not self.billing_period_id and self.company_id:
            self.billing_period = BillingPeriod.get_or_create_current(self.company)
        if not self.number:
            now = timezone.now()
            count = Otpremnica.objects.filter(
                company=self.company,
                issue_date__year=now.year
            ).count() + 1
            self.number = "{}-{:04d}".format(now.year, count)
        super().save(**kwargs)


class OtpremnicaItem(models.Model):
    """Stavka otpremnice (EN 16931 kompatibilna)."""

    UNIT_CHOICES = [
        ("EA", "Komad"), ("HUR", "Sat"), ("KGM", "Kilogram"),
        ("MTR", "Metar"), ("LTR", "Litra"), ("MTK", "m2"),
        ("DAY", "Dan"), ("MON", "Mjesec"), ("SET", "Set"),
    ]

    otpremnica  = models.ForeignKey(Otpremnica, on_delete=models.CASCADE, related_name="items")
    line_number = models.PositiveIntegerField(default=1)
    description = models.CharField(max_length=300)
    quantity    = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    unit        = models.CharField(max_length=5, choices=UNIT_CHOICES, default="EA")
    unit_price  = models.DecimalField(max_digits=12, decimal_places=4)
    tax_rate    = models.DecimalField(max_digits=5, decimal_places=2, default=25)
    line_total  = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["line_number"]
        verbose_name = "Stavka otpremnice"

    def __str__(self):
        return "#{}: {} x{} = {}".format(
            self.line_number, self.description, self.quantity, self.line_total
        )


# =============================================================================
# FAZA B -- PropterTenant (SaaS multi-tenant)
# =============================================================================

class PropterConfig(models.Model):
    """SaaS tenant za Propter modul.

    Tier bookkeeper: vodi N klijenata, max pretplata.
    Tier client: vlastita firma, manja pretplata.

    Arhitektura certifikata (zakonski):
        - Svaki klijent ima vlastiti FINA certifikat
        - KS Limit/operator nije registrirana pristupna tocka
        - Kad zakon dopusti -- operator moze biti pristupna tocka
    """

    class Tier(models.TextChoices):
        CLIENT      = "client",      "Komitent (direktni)"
        BOOKKEEPER  = "bookkeeper",  "Knjigovodstveni servis"
        OPERATOR    = "operator",    "Operator/Hub (buducnost)"

    class CertStatus(models.TextChoices):
        NONE    = "none",    "Nema certifikata"
        PENDING = "pending", "Ceka certifikat"
        ACTIVE  = "active",  "Aktivan"
        EXPIRED = "expired", "Istekao"

    company = models.OneToOneField(
        "companies.Company", on_delete=models.CASCADE,
        related_name="propter_config"
    )

    tier            = models.CharField(max_length=15, choices=Tier.choices, default=Tier.CLIENT)
    operator_name   = models.CharField(max_length=200, blank=True,
                                       help_text="Npr. KS Limit d.o.o.")
    max_clients     = models.PositiveIntegerField(default=1,
                                                  help_text="Za bookkeepere: max klijenata")

    # FINA certifikat status
    cert_status      = models.CharField(max_length=10, choices=CertStatus.choices,
                                        default=CertStatus.NONE)
    cert_valid_until = models.DateField(null=True, blank=True)

    # Moduli ukljuceni u pretplatu
    modules_enabled = models.JSONField(default=list,
                                       help_text="Slugovi modula: eracun, payroll, pos, ...")

    # Pretplata
    monthly_fee  = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    billing_day  = models.PositiveSmallIntegerField(default=1)  # dan u mj. naplate
    is_active    = models.BooleanField(default=True)
    trial_until  = models.DateField(null=True, blank=True)

    # Eco/marketing
    eco_badge_enabled = models.BooleanField(default=False)
    public_eco_page   = models.BooleanField(default=False,
                                            help_text="Javna eko stranica za klijenta")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Propter tenant"
        verbose_name_plural = "Propter tenanti"

    def __str__(self):
        return "{} [{}] {}/mj".format(
            self.company.name, self.get_tier_display(), self.monthly_fee
        )

    @property
    def is_trial(self):
        return self.trial_until and self.trial_until >= timezone.now().date()

    @property
    def cert_is_valid(self):
        if self.cert_status != self.CertStatus.ACTIVE:
            return False
        if self.cert_valid_until and self.cert_valid_until < timezone.now().date():
            return False
        return True


# =============================================================================
# FAZA C -- EkoStats (marketing differentiator)
# =============================================================================

class EkoStats(models.Model):
    """Eko statistika po firmi i mjesecu.
    Automatski se izracunava pri zatvaranju BillingPeriod-a.

    Marketing: 'bez papira', CO2 usteda, ESG reporting.
    Badge razine: bronze 50+, silver 200+, gold 500+, platinum 1000+ e-racuna/mj
    """

    class Badge(models.TextChoices):
        NONE     = "",          "Bez bedza"
        BRONZE   = "bronze",   "Bronze (50+)"
        SILVER   = "silver",   "Silver (200+)"
        GOLD     = "gold",     "Gold (500+)"
        PLATINUM = "platinum", "Platinum (1000+)"

    company        = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="eko_stats"
    )
    billing_period = models.OneToOneField(
        BillingPeriod, on_delete=models.CASCADE,
        related_name="eko_stats", null=True, blank=True
    )
    year  = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()

    # Brojaci
    eracuni_sent     = models.PositiveIntegerField(default=0)
    otpremnice_count = models.PositiveIntegerField(default=0)

    # Eko izracun (IPCC standard: 5g CO2 po listu A4)
    paper_saved_sheets  = models.PositiveIntegerField(default=0)
    co2_saved_grams     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trees_equivalent    = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    # Kumulativ za godinu
    paper_saved_ytd  = models.PositiveIntegerField(default=0)
    co2_saved_ytd    = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    badge_level = models.CharField(max_length=10, choices=Badge.choices, blank=True, default="")

    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("company", "year", "month")
        ordering = ["-year", "-month"]
        verbose_name = "Eko statistika"
        verbose_name_plural = "Eko statistike"

    def __str__(self):
        return "{} {}/{:02d} -- {}g CO2 usteda [{}]".format(
            self.company.name, self.year, self.month,
            self.co2_saved_grams, self.badge_level or "bez bedza"
        )

    @classmethod
    def calculate(cls, billing_period):
        """Izracunaj i spremi eko statistiku za period."""
        from decimal import Decimal

        count = billing_period.otpremnica_count or 0

        # CO2: 5g po listu, prosjecno 2 lista po dokumentu (original + kopija)
        sheets = count * 2
        co2 = Decimal(str(sheets * 5))  # grama
        # 1 stablo apsorbira ~21700g CO2/god
        trees = co2 / Decimal("21700") if co2 > 0 else Decimal("0")

        # Badge logika
        if count >= 1000:
            badge = cls.Badge.PLATINUM
        elif count >= 500:
            badge = cls.Badge.GOLD
        elif count >= 200:
            badge = cls.Badge.SILVER
        elif count >= 50:
            badge = cls.Badge.BRONZE
        else:
            badge = ""

        # YTD -- zbroj prethodnih mjeseci iste godine
        ytd_qs = cls.objects.filter(
            company=billing_period.company,
            year=billing_period.year,
            month__lt=billing_period.month
        )
        ytd_sheets = sum(e.paper_saved_sheets for e in ytd_qs) + sheets
        ytd_co2 = sum(e.co2_saved_grams for e in ytd_qs) + co2

        eko, _ = cls.objects.update_or_create(
            company=billing_period.company,
            year=billing_period.year,
            month=billing_period.month,
            defaults={
                "billing_period": billing_period,
                "eracuni_sent": count,
                "otpremnice_count": count,
                "paper_saved_sheets": sheets,
                "co2_saved_grams": co2,
                "trees_equivalent": trees.quantize(Decimal("0.0001")),
                "paper_saved_ytd": ytd_sheets,
                "co2_saved_ytd": ytd_co2,
                "badge_level": badge,
            }
        )
        return eko
