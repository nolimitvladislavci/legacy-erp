"""
BORG FENIX — Regulatory Knowledge Graph
Automatska asimilacija zakona, olakšica i prilagodba sustava u stvarnom vremenu.

Modeli:
- RegulatorySource: Službeni izvori (NN, FINA, Porezna, EUR-Lex)
- RegulatoryUpdate: Sirovi podatak o promjeni zakona/propisa
- ImpactDomain: Na koga se odnosi (NKD, veličina, PDV status)
- AdaptationRule: Automatska akcija sustava (promjena stope, XML validacije...)
- LegalOpportunity: Olakšica/poticaj — generator ROI-ja
- ClientOpportunityMatch: Spoj firma ↔ olakšica — WhatsApp "pronašli smo 4 prilike"
"""
import uuid
from django.db import models
from django.utils import timezone


class RegulatorySource(models.Model):
    """Službeni izvori podataka (Narodne novine, FINA, Porezna uprava, EUR-Lex)."""

    SOURCE_TYPES = [
        ('nn', 'Narodne novine'),
        ('fina', 'FINA'),
        ('porezna', 'Porezna uprava'),
        ('eurlex', 'EUR-Lex'),
        ('hzz', 'Hrvatski zavod za zapošljavanje'),
        ('mingor', 'Ministarstvo gospodarstva'),
        ('custom', 'Prilagođeni izvor'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name='Naziv izvora')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES, default='nn')
    url_endpoint = models.URLField(verbose_name='API ili RSS Endpoint', blank=True)
    scrape_config = models.JSONField(
        default=dict, blank=True,
        help_text='CSS selektori, API ključevi, parametri scrapera',
    )
    is_active = models.BooleanField(default=True)
    last_scraped = models.DateTimeField(null=True, blank=True)
    scrape_interval_hours = models.IntegerField(default=6, help_text='Svakih N sati')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Regulatorni izvor'
        verbose_name_plural = 'Regulatorni izvori'

    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"


class RegulatoryUpdate(models.Model):
    """Sirovi podatak o promjeni zakona/propisa — povučen s izvora."""

    CATEGORY_CHOICES = [
        ('TAX', 'Porezi i davanja'),
        ('VAT', 'PDV'),
        ('LABOUR', 'Radno pravo i plaće'),
        ('FISCAL', 'Fiskalizacija'),
        ('ERACUN', 'e-Račun / PEPPOL'),
        ('CORP', 'Korporativno pravo'),
        ('TRADE', 'Trgovina i carine'),
        ('GDPR', 'Zaštita podataka'),
        ('AML', 'Sprječavanje pranja novca'),
        ('NONPROFIT', 'Udruge i neprofitni sektor'),
        ('EU_FUND', 'EU fondovi i poticaji'),
        ('OTHER', 'Ostalo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        RegulatorySource, on_delete=models.CASCADE,
        related_name='updates', null=True, blank=True,
    )
    title = models.CharField(max_length=500, verbose_name='Naslov dokumenta/zakona')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='Kategorija')
    nn_number = models.CharField(
        max_length=50, blank=True,
        verbose_name='NN broj', help_text='Npr. NN 123/2026',
    )
    publication_date = models.DateField(verbose_name='Datum objave')
    effective_date = models.DateField(
        verbose_name='Datum stupanja na snagu', null=True, blank=True,
    )
    raw_text = models.TextField(verbose_name='Puni tekst ili sažetak', blank=True)
    ai_summary = models.TextField(
        verbose_name='AI sažetak', blank=True,
        help_text='Claude/Gemini generiran sažetak utjecaja',
    )
    impact_score = models.IntegerField(
        default=0,
        help_text='1-10: koliko je kritično za naše klijente',
    )
    affected_modules = models.JSONField(
        default=list, blank=True,
        help_text='Lista modula: ["pos", "invoicing", "payroll"]',
    )
    is_processed = models.BooleanField(default=False, help_text='AI je parsirao?')
    is_breaking = models.BooleanField(
        default=False,
        help_text='Zahtijeva hitnu prilagodbu sustava?',
    )
    url = models.URLField(blank=True, verbose_name='Link na izvor')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Regulatorna promjena'
        verbose_name_plural = 'Regulatorne promjene'
        ordering = ['-publication_date']
        indexes = [
            models.Index(fields=['publication_date', 'category']),
            models.Index(fields=['is_processed', 'is_breaking']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"


class ImpactDomain(models.Model):
    """Na koga se promjena odnosi — filter po NKD, veličini, PDV statusu."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    regulatory_update = models.ForeignKey(
        RegulatoryUpdate, on_delete=models.CASCADE,
        related_name='impact_domains',
    )
    nkd_codes = models.JSONField(
        verbose_name='NKD kodovi', blank=True, default=list,
        help_text='["1071", "4711", "5610"] — prazno = svi',
    )
    business_types = models.JSONField(
        verbose_name='Tipovi poslovanja', blank=True, default=list,
        help_text='["doo", "obrt", "udruga"] — prazno = svi',
    )
    min_employees = models.IntegerField(default=0)
    max_employees = models.IntegerField(null=True, blank=True)
    requires_vat = models.BooleanField(
        default=False, verbose_name='Samo PDV obveznici',
    )
    country = models.CharField(
        max_length=5, default='HR',
        help_text='HR, DE, ili * za sve',
    )

    class Meta:
        verbose_name = 'Domena utjecaja'
        verbose_name_plural = 'Domene utjecaja'

    def __str__(self):
        return f"NKD:{self.nkd_codes} | {self.country}"

    def matches_company(self, company):
        """Provjeri odgovara li firma ovoj domeni."""
        if self.country != '*' and getattr(company, 'country', 'HR') != self.country:
            return False
        # nkd_code je FK na NKDCode — treba .code atribut; None = nema NKD = propusti
        if self.nkd_codes:
            nkd_fk = getattr(company, 'nkd_code', None)
            company_nkd = nkd_fk.code if nkd_fk else None
            if company_nkd is None:
                pass  # Firma nema NKD — ne isključuj jer ne možemo potvrditi
            elif company_nkd not in self.nkd_codes:
                return False
        if self.business_types and getattr(company, 'business_type', '') not in self.business_types:
            return False
        if self.requires_vat and not getattr(company, 'is_vat_registered', True):
            return False
        return True


class AdaptationRule(models.Model):
    """Automatska akcija sustava — npr. 'PDV stopa 13→25 za kategoriju X'."""

    RULE_TYPES = [
        ('tax_rate', 'Promjena porezne stope'),
        ('xml_schema', 'Promjena XML sheme (e-Račun, FINA)'),
        ('form_update', 'Ažuriranje obrasca (JOPPD, PDV-S)'),
        ('config_change', 'Promjena konfiguracije'),
        ('notification', 'Samo obavijest (ručna akcija)'),
        ('code_change', 'Zahtijeva code change (dev ticket)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    regulatory_update = models.ForeignKey(
        RegulatoryUpdate, on_delete=models.CASCADE,
        related_name='adaptation_rules',
    )
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    target_module = models.CharField(
        max_length=100,
        help_text='Django app: pos, invoicing, payroll, eracun...',
    )
    action_description = models.TextField(
        verbose_name='Opis akcije',
        help_text='Što točno treba napraviti',
    )
    action_payload = models.JSONField(
        help_text='Strukturirani podaci za auto-primjenu',
        default=dict, blank=True,
    )
    can_auto_apply = models.BooleanField(
        default=False,
        help_text='Može li sustav sam primijeniti bez ljudske intervencije?',
    )
    is_executed = models.BooleanField(default=False)
    executed_at = models.DateTimeField(null=True, blank=True)
    executed_by = models.CharField(
        max_length=50, blank=True,
        help_text='auto / username koji je primijenio',
    )
    error_log = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Pravilo adaptacije'
        verbose_name_plural = 'Pravila adaptacije'

    def __str__(self):
        return f"{self.get_rule_type_display()} → {self.target_module}"

    def execute(self):
        """Pokušaj automatsku primjenu pravila."""
        if not self.can_auto_apply:
            return False
        if self.is_executed:
            return True
        try:
            from limit_connect_ai.services.adaptation_engine import apply_rule
            apply_rule(self)
            self.is_executed = True
            self.executed_at = timezone.now()
            self.executed_by = 'auto'
            self.save(update_fields=['is_executed', 'executed_at', 'executed_by'])
            return True
        except Exception as e:
            self.error_log = str(e)[:500]
            self.save(update_fields=['error_log'])
            return False


class LegalOpportunity(models.Model):
    """Olakšica, poticaj, ili legalna optimizacija — generator ROI-ja."""

    OPPORTUNITY_TYPES = [
        ('tax_relief', 'Porezna olakšica'),
        ('employment_subsidy', 'Poticaj za zapošljavanje'),
        ('eu_fund', 'EU fond'),
        ('depreciation', 'Ubrzana amortizacija'),
        ('vat_exemption', 'PDV izuzeće'),
        ('regional_aid', 'Regionalna pomoć'),
        ('green_incentive', 'Zeleni poticaj'),
        ('digital_voucher', 'Digitalni bon/vaučer'),
        ('other', 'Ostalo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    regulatory_update = models.ForeignKey(
        RegulatoryUpdate, on_delete=models.CASCADE,
        related_name='opportunities', null=True, blank=True,
    )
    impact_domain = models.ForeignKey(
        ImpactDomain, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    opportunity_type = models.CharField(max_length=25, choices=OPPORTUNITY_TYPES)
    name = models.CharField(max_length=255, verbose_name='Naziv olakšice')
    description = models.TextField(verbose_name='Opis i uvjeti')
    eligibility_criteria = models.JSONField(
        default=dict, blank=True,
        help_text='{"max_employee_age": 30, "min_duration_months": 12}',
    )
    savings_formula = models.CharField(
        max_length=500, blank=True,
        help_text='Python izraz: bruto_placa * 0.165 * 12',
    )
    typical_savings_eur = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Tipična ušteda (EUR)',
    )
    deadline = models.DateField(null=True, blank=True, verbose_name='Rok za prijavu')
    is_active = models.BooleanField(default=True)
    url = models.URLField(blank=True, verbose_name='Link na natječaj/zakon')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pravna prilika (Olakšica)'
        verbose_name_plural = 'Pravne prilike (Olakšice)'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_opportunity_type_display()})"

    @property
    def is_expired(self):
        if not self.deadline:
            return False
        return self.deadline < timezone.now().date()


class ClientOpportunityMatch(models.Model):
    """
    Spoj firma ↔ olakšica.
    Ovo je srž monetizacije: "Pronašli smo 4 prilike za uštedu od 12.340 EUR"
    """

    STATUS_CHOICES = [
        ('identified', 'Identificirano'),
        ('notified', 'Klijent obaviješten'),
        ('interested', 'Klijent zainteresiran'),
        ('applied', 'Aplicirano'),
        ('utilized', 'Iskorišteno'),
        ('rejected', 'Klijent odbio'),
        ('expired', 'Istekao rok'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='opportunity_matches',
    )
    opportunity = models.ForeignKey(
        LegalOpportunity, on_delete=models.CASCADE,
        related_name='client_matches',
    )
    calculated_savings = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Izračunata ušteda (EUR)',
    )
    calculation_details = models.JSONField(
        default=dict, blank=True,
        help_text='Detaljni izračun: {"base": 5000, "rate": 0.165, "months": 12}',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='identified')
    notified_at = models.DateTimeField(null=True, blank=True)
    notified_via = models.CharField(max_length=20, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    matched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pronađena prilika za klijenta'
        verbose_name_plural = 'Pronađene prilike za klijente'
        unique_together = ('company', 'opportunity')
        ordering = ['-calculated_savings']

    def __str__(self):
        return f"{self.company.name} → {self.opportunity.name} ({self.calculated_savings} EUR)"


class SupplierRiskAlert(models.Model):
    """
    Sustav ranog upozoravanja na temelju FINA API podataka (GFI, boniteti, blokade).

    ARHITEKTONSKA NOTA (Gemini, 2026-03-24):
    Strogo odvojeno od LegalOpportunity modela.
    LegalOpportunity = generiranje novca (olakšice, poticaji).
    SupplierRiskAlert = zaštita novca (rizici, blokade, stečaj).
    Nikad ne miješati ova dva koncepta.
    """

    RISK_LEVEL_CHOICES = [
        ('LOW', 'Nizak rizik'),
        ('MEDIUM', 'Srednji rizik (povećan dug / pad prihoda)'),
        ('HIGH', 'Visok rizik (predstečaj / upozorenje)'),
        ('CRITICAL', 'Kritičan rizik (blokada / stečaj / brisanje)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='supplier_risk_alerts',
        verbose_name='Naš klijent koji je ugrožen',
    )
    supplier_oib = models.CharField(
        max_length=11, verbose_name='OIB dobavljača',
        db_index=True,
    )
    supplier_name = models.CharField(max_length=255, verbose_name='Naziv dobavljača')
    risk_level = models.CharField(
        max_length=20, choices=RISK_LEVEL_CHOICES,
        verbose_name='Razina rizika', db_index=True,
    )
    risk_description = models.TextField(
        verbose_name='Detalji',
        help_text='Npr. "Blokiran račun duže od 30 dana"',
    )
    source_data = models.JSONField(
        verbose_name='Sirovi FINA podaci (audit trail)',
        blank=True, null=True,
    )
    detected_at = models.DateTimeField(auto_now_add=True)
    is_acknowledged = models.BooleanField(
        default=False,
        verbose_name='Klijent potvrdio',
        help_text='Je li klijent vidio i potvrdio upozorenje?',
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    notified_via = models.CharField(
        max_length=20, blank=True,
        help_text='whatsapp / email / sms',
    )
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Upozorenje o riziku dobavljača'
        verbose_name_plural = 'Upozorenja o rizicima dobavljača'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['company', 'supplier_oib']),
            models.Index(fields=['risk_level', 'is_acknowledged']),
        ]

    def __str__(self):
        return f'[{self.risk_level}] {self.supplier_name} → {self.company.name}'

    @property
    def is_critical(self):
        return self.risk_level == 'CRITICAL'

    @property
    def needs_immediate_action(self):
        return self.risk_level in ('HIGH', 'CRITICAL') and not self.is_acknowledged



class TenantRegulatoryImpact(models.Model):
    """Per-tenant relevantnost regulatorne promjene."""

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='regulatory_impacts',
    )
    regulatory_update = models.ForeignKey(
        RegulatoryUpdate, on_delete=models.CASCADE,
        related_name='tenant_impacts',
    )
    is_relevant = models.BooleanField(default=False)
    severity = models.CharField(max_length=20, default='info',
        help_text='info, warning, action_required')
    impact_summary = models.TextField(blank=True)
    affected_modules = models.JSONField(default=list, blank=True)
    reviewed_by_user = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'regulatory_update']
        verbose_name = 'Tenant Regulatory Impact'
        verbose_name_plural = 'Tenant Regulatory Impacts'

    def __str__(self):
        return f'{self.company.name} <- {self.regulatory_update.title[:50]} ({self.severity})'
