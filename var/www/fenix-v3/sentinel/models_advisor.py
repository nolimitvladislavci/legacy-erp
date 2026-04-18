"""
FENIX SENTINEL — Advisor Models (PLAN_078–081)
EUFundProfile, EUFund, EUMatch
ObrascTip, ObrascInstance, ObrascKalendar, KalendarObveza
"""

from django.db import models
from core.base_model import TenantModel, BaseModel


# ─── EU NAVIGATOR (PLAN_078) ──────────────────────────────────────────────────


class EUFund(BaseModel):
    """Katalog EU natječaja — puni Gemini/AI, ažurira se tjedno"""

    STATUS = [
        ("open", "Otvoren"),
        ("closing", "Zatvara se"),
        ("closed", "Zatvoren"),
        ("announced", "Najavljen"),
    ]

    fund_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=500)
    title_hr = models.CharField(max_length=500, blank=True)
    program = models.CharField(max_length=200)  # Horizon EU, ESF+, ERDF...
    total_budget_eur = models.BigIntegerField(null=True, blank=True)
    max_grant_eur = models.IntegerField(null=True, blank=True)
    min_grant_eur = models.IntegerField(null=True, blank=True)
    cofinancing_rate = models.IntegerField(default=85)  # % EU pokriva
    deadline = models.DateField(null=True, blank=True)
    open_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="open")

    # Eligibility matrix
    eligible_nkd = models.JSONField(default=list)
    eligible_regions = models.JSONField(default=list)
    min_employees = models.IntegerField(default=0)
    max_employees = models.IntegerField(null=True, blank=True)
    min_age_years = models.IntegerField(default=0)

    # Scoring weights
    innovation_weight = models.IntegerField(default=25)
    digital_weight = models.IntegerField(default=25)
    green_weight = models.IntegerField(default=25)
    social_weight = models.IntegerField(default=25)

    # Meta
    source_url = models.URLField(blank=True)
    summary_hr = models.TextField(blank=True)
    gemini_analysis = models.JSONField(default=dict)

    class Meta(BaseModel.Meta):
        db_table = "sentinel_eu_fund"
        verbose_name = "EU Fund"
        ordering = ["deadline"]

    def __str__(self):
        return f"{self.program}: {self.title_hr or self.title}"


class EUFundProfile(TenantModel):
    """Profil firme za EU fondove — automatski izračunat tjedno"""

    nkd_code = models.CharField(max_length=10, blank=True)
    employee_count = models.IntegerField(default=0)
    annual_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    company_age_years = models.IntegerField(default=0)
    region = models.CharField(max_length=100, blank=True)

    # AI score komponente
    innovation_score = models.IntegerField(default=0)
    digital_score = models.IntegerField(default=0)
    green_score = models.IntegerField(default=0)
    social_score = models.IntegerField(default=0)

    last_profiled = models.DateTimeField(null=True, blank=True)
    profile_version = models.CharField(max_length=20, default="1.0")

    class Meta(TenantModel.Meta):
        db_table = "sentinel_eu_fund_profile"
        verbose_name = "EU Fund Profile"

    def __str__(self):
        return f"EU Profil: {self.company}"


class EUMatch(TenantModel):
    """Personalizirani match: firma × natječaj"""

    RECOMMENDED = "recommended"
    APPLIED = "applied"
    REJECTED = "rejected"
    WON = "won"
    STATUS = [
        (RECOMMENDED, "Preporučeno"),
        (APPLIED, "Aplikacija u tijeku"),
        (REJECTED, "Odbijeno"),
        (WON, "Odobreno"),
    ]

    fund = models.ForeignKey(EUFund, on_delete=models.CASCADE, related_name="matches")
    match_score = models.IntegerField(default=0)
    eligibility_score = models.IntegerField(default=0)
    potential_eur = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS, default=RECOMMENDED)
    ai_reasoning = models.TextField(blank=True)
    action_plan = models.JSONField(default=list)
    notified = models.BooleanField(default=False)

    class Meta(TenantModel.Meta):
        db_table = "sentinel_eu_match"
        unique_together = ["company", "fund"]
        ordering = ["-match_score"]

    def __str__(self):
        return f"{self.company} ↔ {self.fund} [{self.match_score}/100]"


# ─── OBRASCI ENGINE (PLAN_079) ────────────────────────────────────────────────


class ObrascTip(BaseModel):
    """Katalog obrazaca — PDV, JOPPD, URA, IRA, GDPR..."""

    PERIODI = [
        ("monthly", "Mjesečno"),
        ("quarterly", "Kvartalno"),
        ("yearly", "Godišnje"),
        ("on_demand", "Na zahtjev"),
    ]

    kod = models.CharField(max_length=50, unique=True)
    naziv = models.CharField(max_length=200)
    opis = models.TextField(blank=True)
    period = models.CharField(max_length=20, choices=PERIODI)
    rok_dana = models.IntegerField(default=20)
    institucija = models.CharField(max_length=100)
    template_path = models.CharField(max_length=200, blank=True)
    field_mapping = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        db_table = "sentinel_obrazac_tip"
        verbose_name = "Obrazac Tip"
        ordering = ["kod"]

    def __str__(self):
        return f"{self.kod} — {self.naziv}"


class ObrascInstance(TenantModel):
    """Instanca obrasca — popunjen, čeka podnošenje ili je podnesen"""

    STATUS = [
        ("draft", "Nacrt"),
        ("ready", "Spreman"),
        ("submitted", "Podnesen"),
        ("accepted", "Prihvaćen"),
        ("rejected", "Odbijen"),
    ]

    tip = models.ForeignKey(ObrascTip, on_delete=models.CASCADE, related_name="instances")
    period_od = models.DateField()
    period_do = models.DateField()
    rok_podnosenja = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS, default="draft", db_index=True)

    izracunata_vrijednost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    polja = models.JSONField(default=dict)
    ai_napomene = models.JSONField(default=list)

    xml_sadrzaj = models.TextField(blank=True)
    pdf_sadrzaj = models.BinaryField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_ref = models.CharField(max_length=100, blank=True)

    class Meta(TenantModel.Meta):
        db_table = "sentinel_obrazac_instance"
        unique_together = ["company", "tip", "period_od"]
        ordering = ["rok_podnosenja"]
        indexes = [
            models.Index(fields=["company", "rok_podnosenja", "status"]),
        ]

    def __str__(self):
        return f"{self.tip.kod} {self.period_od.strftime('%m/%Y')} [{self.status}]"


class KalendarObveza(TenantModel):
    """Master kalendar svih računovodstvenih obveza za firmu"""

    KATEGORIJA = [
        ("porezna", "Porezna uprava"),
        ("mirovinsko", "HZMO"),
        ("zdravstveno", "HZZO"),
        ("sud", "Sudski registar"),
        ("eu", "EU/HAMAG"),
        ("banka", "Banka"),
        ("ostalo", "Ostalo"),
    ]

    kategorija = models.CharField(max_length=20, choices=KATEGORIJA)
    naziv = models.CharField(max_length=200)
    opis = models.TextField(blank=True)
    rok = models.DateField(db_index=True)
    procijenjeni_iznos = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    zakonska_osnova = models.CharField(max_length=200, blank=True)
    penali_kasnjenja = models.TextField(blank=True)

    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    auto_generated = models.BooleanField(default=True)
    obrazac = models.ForeignKey(ObrascInstance, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta(TenantModel.Meta):
        db_table = "sentinel_kalendar_obveza"
        verbose_name = "Kalendar Obveza"
        ordering = ["rok"]
        indexes = [
            models.Index(fields=["company", "rok"]),
            models.Index(fields=["company", "is_completed"]),
        ]

    def __str__(self):
        return f"{self.naziv} — rok: {self.rok}"
