"""
tax_wizard/models.py — Porezni Savjetnik

JSON-driven wizard engine za porezne prijave.
Obrasci se renderiraju iz TaxFormTemplate (baza), NE iz hardkodiranog HTML-a.
Marija može dodati/izmijeniti polja direktno iz Admin panela.

Pravni štit: AI SIMULIRA scenarije, NE SAVJETUJE.
  ✗ "Preporučujem manju plaću"
  ✓ "Simulacija pokazuje da bi X rezultiralo s Y eura manjim obvezama"

B2B2C: referred_by na TaxWizardSession omogućava računovođi
da vidi draft svog klijenta prije podnošenja.
"""
import hashlib
import json
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager

# ═══════════════════════════════════════════════════════════════════
#  1. JSON FORM ENGINE — Srce sustava
# ═══════════════════════════════════════════════════════════════════

class TaxFormTemplate(models.Model):
    """
    JSON shema koja definira porezni obrazac.
    Svaki obrazac (PO-SD, DOH, PD...) ima svoju shemu s koracima,
    poljima, validacijama i AI hintovima.

    Admin panel → Marija editira polja → korisnik vidi promjene
    bez novog deploya.

    schema format:
    {
      "steps": [
        {
          "id": "primitci",
          "title": "Primitci po kvartalima",
          "title_en": "Quarterly income",
          "fields": [
            {
              "name": "q1_primitak",
              "type": "decimal",       // text|decimal|integer|boolean|date|select|oib|iban
              "label": "Q1 primitak (EUR)",
              "label_en": "Q1 income (EUR)",
              "required": true,
              "default": 0,
              "min": 0,
              "max": 1000000,
              "help_text": "Ukupni primitci za I. kvartal",
              "help_text_en": "Total income for Q1",
              "ai_hint": "Ako korisnik ima naše fakture, auto-fill iz invoicing",
              "source": "invoicing.Invoice",  // auto-fill izvor
              "source_filter": {"quarter": 1}
            },
            ...
          ],
          "ai_message": "Provjeravam vaše fakture za automatski unos...",
          "ai_message_en": "Checking your invoices for auto-fill...",
          "validation_rules": [
            {"rule": "sum_q1_q4_lt_60000", "message": "Ukupni primitci prelaze 60.000 EUR — morate prijeći na redovni obrt!"}
          ]
        },
        ...
      ],
      "output_xml_template": "posd_2026_v1",
      "legal_references": ["Zakon o porezu na dohodak čl. 82.", "Pravilnik čl. 37."]
    }
    """

    class FormType(models.TextChoices):
        PO_SD   = 'PO-SD',   _('PO-SD — Paušalni obrt')
        DOH     = 'DOH',     _('DOH — Godišnja prijava poreza na dohodak')
        ZPP_DOH = 'ZPP-DOH', _('ZPP-DOH — Zahtjev za priznavanje prava')
        PD      = 'PD',      _('PD — Prijava poreza na dobit')
        PD_IPO  = 'PD-IPO',  _('PD-IPO — Transferne cijene')
        PDV     = 'PDV',     _('PDV — Prijava PDV-a')
        PDV_K   = 'PDV-K',   _('PDV-K — Konačni obračun PDV-a')
        GFI_POD = 'GFI-POD', _('GFI-POD — Godišnji financijski izvještaj')
        INO_DOH = 'INO-DOH', _('INO-DOH — Inozemni dohodak')
        JOPPD   = 'JOPPD',   _('JOPPD — Izvješće o primicima i doprinosima')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form_type = models.CharField(max_length=20, choices=FormType.choices, db_index=True)
    version = models.CharField(max_length=20, help_text='Npr. 2026-v1, 2026-v2')
    name = models.CharField(max_length=200, verbose_name='Naziv')
    name_en = models.CharField(max_length=200, blank=True, verbose_name='Name (EN)')

    # JSON shema — srce engine-a
    schema = models.JSONField(
        verbose_name='JSON shema obrasca',
        help_text='Definira korake, polja, validacije i AI hintove',
    )

    # Tko može koristiti ovaj obrazac
    applicable_business_types = models.JSONField(
        default=list, blank=True,
        help_text='["obrt", "doo", "jdoo"] — prazno = svi',
    )
    applicable_countries = models.JSONField(
        default=list, blank=True,
        help_text='["HR", "DE"] — prazno = svi',
    )

    # Rokovi
    filing_deadline_rule = models.CharField(
        max_length=100, blank=True,
        help_text='Pravilo za rok: "jan-15" (fiksni), "month+20" (PDV), "year+4m" (PD)',
    )

    # XML output
    xml_template_name = models.CharField(
        max_length=100, blank=True,
        help_text='Naziv XML generatora za e-Porezna export',
    )

    # Verzioniranje
    is_active = models.BooleanField(default=True)
    supersedes = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='superseded_by',
        help_text='Prethodna verzija ovog obrasca',
    )
    valid_from = models.DateField(help_text='Od kada vrijedi (porezna godina)')
    valid_until = models.DateField(null=True, blank=True, help_text='Do kada vrijedi')

    # AI kontekst za pravni štit
    ai_system_prompt = models.TextField(
        blank=True,
        default=(
            'Ti si porezni kalkulator, NE porezni savjetnik. '
            'Prikazuješ simulacije i izračune na temelju unesenih podataka '
            'i trenutno važećih poreznih stopa. '
            'NIKADA ne koristi riječi: preporučujem, savjetujem, trebali biste. '
            'UVIJEK koristi: simulacija pokazuje, izračun rezultira, prema važećim stopama. '
            'Na kraju svake poruke dodaj: "Ovo je informativni izračun, ne pravni savjet."'
        ),
        verbose_name='AI System Prompt (pravni štit)',
    )

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        unique_together = [('form_type', 'version')]
        ordering = ['form_type', '-valid_from']
        verbose_name = 'Predložak obrasca'
        verbose_name_plural = 'Predlošci obrazaca'

    def __str__(self):
        return f'{self.form_type} {self.version} — {self.name}'

    @property
    def step_count(self):
        return len(self.schema.get('steps', []))

    def get_step(self, index):
        steps = self.schema.get('steps', [])
        if 0 <= index < len(steps):
            return steps[index]
        return None

    def get_field_names(self):
        """Sva polja iz svih koraka — za validaciju."""
        names = []
        for step in self.schema.get('steps', []):
            for field in step.get('fields', []):
                names.append(field['name'])
        return names


# ═══════════════════════════════════════════════════════════════════
#  2. WIZARD SESSION — Draft s B2B2C referralom
# ═══════════════════════════════════════════════════════════════════

class TaxWizardSession(models.Model):
    """
    Jedna sesija popunjavanja poreznog obrasca.
    Korisnik može pauzirati i nastaviti (AJAX auto-save na svaki korak).

    B2B2C flow:
      1. Klijent ispuni wizard (ili računovođa za njega)
      2. referred_by = Marijin user → ona vidi draft na svom dashboardu
      3. Marija pregleda, korigira, finalizira
      4. XML export → ePorezna
    """

    class Status(models.TextChoices):
        DRAFT      = 'draft',      _('Nacrt')
        REVIEW     = 'review',     _('Čeka pregled računovođe')
        CORRECTION = 'correction', _('Vraćeno na ispravak')
        FINALIZED  = 'final',      _('Finalizirano')
        SUBMITTED  = 'submitted',  _('Predano na ePorezna')
        ACCEPTED   = 'accepted',   _('Prihvaćeno od Porezne')
        REJECTED   = 'rejected',   _('Odbijeno od Porezne')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=64, unique=True, db_index=True)

    # Tko popunjava
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='tax_sessions',
        verbose_name='Korisnik',
    )
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='tax_sessions',
        verbose_name='Firma',
    )

    # B2B2C — referral link (računovođa koja vidi draft)
    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='referred_tax_sessions',
        verbose_name='Računovođa (referral)',
        help_text='Ako je klijent došao preko računovođe, ona vidi draft',
    )
    referral_company = models.ForeignKey(
        'companies.Company', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_tax_sessions',
        verbose_name='Računovodstveni servis',
        help_text='Konjik d.o.o., Korpaš d.o.o., itd.',
    )

    # Koji obrazac
    template = models.ForeignKey(
        TaxFormTemplate, on_delete=models.PROTECT,
        related_name='sessions',
        verbose_name='Predložak obrasca',
    )
    tax_year = models.IntegerField(verbose_name='Porezna godina')
    tax_month = models.IntegerField(
        null=True, blank=True,
        verbose_name='Porezni mjesec (za mjesečne obrasce)',
    )
    tax_quarter = models.IntegerField(
        null=True, blank=True,
        verbose_name='Porezni kvartal',
    )

    # Wizard state
    current_step = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT,
    )

    # JSON podaci — SVE što korisnik unese, po koracima
    form_data = models.JSONField(
        default=dict,
        verbose_name='Podaci obrasca',
        help_text='{"q1_primitak": 12500, "q2_primitak": 14200, ...}',
    )

    # AI interakcije — poruke, sugestije, upozorenja
    ai_messages = models.JSONField(
        default=list,
        verbose_name='AI poruke',
        help_text='[{"step": 2, "type": "info", "message": "...", "timestamp": "..."}]',
    )

    # Izračunati rezultati (cache — ne računa se svaki put)
    calculated_results = models.JSONField(
        default=dict,
        verbose_name='Izračunati rezultati',
        help_text='{"porez": 183.60, "tier": 2, "refund_estimate": 847.00, ...}',
    )

    # Integritet — hash svih podataka za audit trail
    data_hash = models.CharField(max_length=64, blank=True)

    # XML output
    xml_file = models.FileField(
        upload_to='tax_wizard/exports/%Y/', blank=True,
        verbose_name='XML export',
    )
    pdf_file = models.FileField(
        upload_to='tax_wizard/previews/%Y/', blank=True,
        verbose_name='PDF preview',
    )

    # Workflow timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Review trail
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_tax_sessions',
        verbose_name='Pregledao/la',
    )
    review_notes = models.TextField(blank=True, verbose_name='Bilješke recenzenta')

    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    locale = models.CharField(
        max_length=5, default='hr',
        help_text='hr, en, de — za višejezični wizard',
    )
    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'tax_year']),
            models.Index(fields=['referred_by', 'status']),
            models.Index(fields=['template', 'status']),
            models.Index(fields=['status', '-updated_at']),
        ]
        verbose_name = 'Porezna sesija'
        verbose_name_plural = 'Porezne sesije'

    def __str__(self):
        return (
            f'{self.template.form_type} {self.tax_year} — '
            f'{self.company.name} [{self.get_status_display()}]'
        )

    def save(self, *args, **kwargs):
        # Integritetni hash — audit trail
        if self.form_data:
            raw = json.dumps(self.form_data, sort_keys=True, default=str)
            self.data_hash = hashlib.sha256(raw.encode()).hexdigest()
        super().save(*args, **kwargs)

    @property
    def progress_percent(self):
        """Postotak dovršenosti wizarda."""
        total = self.template.step_count
        if total == 0:
            return 0
        return min(100, int((self.current_step / total) * 100))

    @property
    def is_editable(self):
        return self.status in (self.Status.DRAFT, self.Status.CORRECTION)

    @property
    def is_overdue(self):
        """Je li rok za podnošenje prošao?"""
        deadline = self.get_filing_deadline()
        if deadline:
            return timezone.now().date() > deadline
        return False

    def get_filing_deadline(self):
        """Izračunaj rok na temelju template pravila."""
        rule = self.template.filing_deadline_rule
        if not rule:
            return None

        year = self.tax_year

        # Fiksni datumi: "jan-15", "mar-02", "apr-30"
        if '-' in rule and len(rule.split('-')) == 2:
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
            }
            parts = rule.split('-')
            month_str, day_str = parts[0].lower(), parts[1]
            if month_str in month_map:
                from datetime import date as dt_date
                # Rok je u sljedećoj godini (za godišnje obrasce)
                return dt_date(year + 1, month_map[month_str], int(day_str))

        # Mjesečni: "month+20" → 20. u sljedećem mjesecu
        if rule.startswith('month+'):
            day = int(rule.replace('month+', ''))
            from datetime import date as dt_date
            month = (self.tax_month or 12) + 1
            yr = year if month <= 12 else year + 1
            if month > 12:
                month -= 12
            return dt_date(yr, month, min(day, 28))

        return None

    def add_ai_message(self, step, msg_type, message):
        """Dodaj AI poruku u sesiju."""
        self.ai_messages.append({
            'step': step,
            'type': msg_type,  # info, warning, success, simulation
            'message': message,
            'timestamp': timezone.now().isoformat(),
        })


# ═══════════════════════════════════════════════════════════════════
#  3. POREZNI KALENDAR — Rokovi + notifikacije
# ═══════════════════════════════════════════════════════════════════

class TaxDeadline(models.Model):
    """
    Porezna obveza za konkretnu firmu u konkretnom periodu.
    Generira se automatski na početku godine iz TaxFormTemplate + Company profil.

    Notifikacije:
      30 dana → email
      14 dana → WhatsApp
       3 dana → email + WhatsApp + in-app (HITNO)
       0 dana → propušten rok alert
    """

    class Priority(models.TextChoices):
        LOW      = 'low',      _('Niska')
        NORMAL   = 'normal',   _('Normalna')
        HIGH     = 'high',     _('Visoka')
        CRITICAL = 'critical', _('Kritična')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='tax_deadlines',
    )
    template = models.ForeignKey(
        TaxFormTemplate, on_delete=models.CASCADE,
        related_name='deadlines',
    )
    tax_year = models.IntegerField()
    tax_month = models.IntegerField(null=True, blank=True)
    tax_quarter = models.IntegerField(null=True, blank=True)

    # Rok
    deadline_date = models.DateField(verbose_name='Rok za podnošenje')
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.NORMAL,
    )

    # Status
    is_filed = models.BooleanField(default=False)
    filed_at = models.DateTimeField(null=True, blank=True)
    session = models.ForeignKey(
        TaxWizardSession, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='deadlines',
        help_text='Povezana wizard sesija (ako postoji)',
    )

    # Notifikacije poslane
    notified_30d = models.BooleanField(default=False)
    notified_14d = models.BooleanField(default=False)
    notified_3d = models.BooleanField(default=False)
    notified_overdue = models.BooleanField(default=False)

    # Kazne
    penalty_min = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Minimalna zakonska kazna za propust (EUR)',
    )
    penalty_max = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Maksimalna zakonska kazna za propust (EUR)',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        unique_together = [('company', 'template', 'tax_year', 'tax_month')]
        ordering = ['deadline_date']
        indexes = [
            models.Index(fields=['deadline_date', 'is_filed']),
            models.Index(fields=['company', 'is_filed', 'deadline_date']),
        ]
        verbose_name = 'Porezni rok'
        verbose_name_plural = 'Porezni rokovi'

    def __str__(self):
        status = '✅' if self.is_filed else '⏳'
        return f'{status} {self.template.form_type} — {self.company.name} — {self.deadline_date}'

    @property
    def days_remaining(self):
        delta = self.deadline_date - timezone.now().date()
        return delta.days

    @property
    def is_overdue(self):
        return not self.is_filed and self.days_remaining < 0

    @property
    def urgency_level(self):
        """Za UI — boja/ikona."""
        if self.is_filed:
            return 'success'
        days = self.days_remaining
        if days < 0:
            return 'overdue'
        if days <= 3:
            return 'critical'
        if days <= 14:
            return 'warning'
        return 'normal'


# ═══════════════════════════════════════════════════════════════════
#  4. AI SIMULACIJA — Salary/Dividend + Olakšice
# ═══════════════════════════════════════════════════════════════════

class TaxSimulation(models.Model):
    """
    Rezultat AI simulacije — npr. salary vs. dividend optimizer,
    ZPP-DOH retroaktivni povrat, tier optimizacija.

    PRAVNI ŠTIT: Svaka simulacija završava s disclaimer-om.
    Riječi "preporučujem/savjetujem" su zabranjene u output-u.
    """

    class SimType(models.TextChoices):
        SALARY_DIVIDEND    = 'salary_div',    _('Plaća vs. dividenda')
        DEDUCTION_FINDER   = 'deduction',     _('Pronađene olakšice')
        ZPP_DOH_RETRO      = 'zpp_retro',     _('ZPP-DOH retroaktivno (5 god)')
        TIER_OPTIMIZATION  = 'tier_opt',      _('Paušal tier optimizacija')
        VAT_THRESHOLD      = 'vat_threshold', _('PDV prag 60K monitoring')
        PRIREZ_COMPARISON  = 'prirez',        _('Usporedba prireza po općinama')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        TaxWizardSession, null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='simulations',
    )
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='tax_simulations',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='tax_simulations',
    )

    sim_type = models.CharField(max_length=20, choices=SimType.choices)

    # Input parametri simulacije
    input_params = models.JSONField(
        default=dict,
        help_text='{"gross_salary": 3500, "annual_profit": 80000, ...}',
    )

    # Rezultati
    results = models.JSONField(
        default=dict,
        help_text=(
            '{"scenarios": ['
            '  {"label": "Scenarij A: Plaća 3.500€/mj", "total_tax": 18240, ...},'
            '  {"label": "Scenarij B: Plaća 2.000€/mj + dividenda", "total_tax": 15890, ...}'
            '], "optimal_scenario": "B", "savings_eur": 2350}'
        ),
    )

    # Količina uštede (za dashboard sorting)
    estimated_savings = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Procjenjena ušteda (EUR)',
    )

    # Disclaimer — uvijek prisutan
    disclaimer = models.TextField(
        default=(
            'Ovo je informativni izračun temeljen na trenutno važećim poreznim '
            'stopama i unesenim podacima. Ne predstavlja porezni ili pravni savjet. '
            'Za službeno tumačenje obratite se ovlaštenom poreznom savjetniku ili '
            'nadležnoj ispostavi Porezne uprave.'
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'sim_type']),
        ]
        verbose_name = 'Porezna simulacija'
        verbose_name_plural = 'Porezne simulacije'

    def __str__(self):
        return f'{self.get_sim_type_display()} — {self.company.name} ({self.estimated_savings}€ ušteda)'


# ═══════════════════════════════════════════════════════════════════
#  5. POTPOMOGNUTA PODRUČJA — Auto-detekcija olakšica
# ═══════════════════════════════════════════════════════════════════

class PotpomognutoPodručje(models.Model):
    """
    Službeni popis potpomognutih općina/gradova (Zakon o potpomognutim područjima).
    Koristi se za automatsku detekciju povećanog osobnog odbitka.

    Grupa I:  osobni odbitak = 700€/mj (umjesto 600€)
    Grupa II: osobni odbitak = 650€/mj (umjesto 600€)

    AI match: korisnik unese adresu → provjeri JLS → primijeni koeficijent.
    """

    class Group(models.TextChoices):
        I  = 'I',  _('I. skupina — 700€ osobni odbitak')
        II = 'II', _('II. skupina — 650€ osobni odbitak')

    name = models.CharField(max_length=200, verbose_name='Naziv JLS')
    county = models.CharField(max_length=100, verbose_name='Županija')
    group = models.CharField(max_length=5, choices=Group.choices)
    zip_codes = models.JSONField(
        default=list,
        help_text='Poštanski brojevi koji pripadaju ovom JLS-u',
    )
    osobni_odbitak = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text='Mjesečni osobni odbitak (EUR)',
    )

    # Prirez stopa za tu JLS
    prirez_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=0,
        help_text='Stopa prireza (npr. 0.1000 = 10%)',
    )

    is_active = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['group', 'county', 'name']
        verbose_name = 'Potpomognuto područje'
        verbose_name_plural = 'Potpomognuta područja'

    def __str__(self):
        return f'{self.name} ({self.county}) — Grupa {self.group}'

    @classmethod
    def find_by_zip(cls, zip_code):
        """Pronađi JLS po poštanskom broju."""
        return cls.objects.filter(
            is_active=True,
            zip_codes__contains=zip_code,
        ).first()


# ═══════════════════════════════════════════════════════════════════
#  6. PAUŠAL TIER TABLICA — Dinamička (iz Admin panela)
# ═══════════════════════════════════════════════════════════════════

class PausalTier(models.Model):
    """
    Razredi paušalnog oporezivanja — dinamički, ne hardkodirano.
    Marija ažurira kad Vlada promijeni granice.

    2026 stope:
      Tier 1: 0 - 12.500€     → 1.530€ poreza/god (127,50€/mj)
      Tier 2: 12.501 - 17.500€ → 2.142€ poreza/god (178,50€/mj)
      Tier 3: 17.501 - 25.000€ → 3.060€ poreza/god (255,00€/mj)
      Tier 4: 25.001 - 40.000€ → 4.896€ poreza/god (408,00€/mj)
      Tier 5: 40.001 - 60.000€ → 7.344€ poreza/god (612,00€/mj)
    """

    valid_year = models.IntegerField(verbose_name='Porezna godina')
    tier_number = models.PositiveSmallIntegerField(verbose_name='Razred')
    min_income = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='Donja granica (EUR)',
    )
    max_income = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='Gornja granica (EUR)',
    )
    annual_tax = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Godišnji porez (EUR)',
    )
    monthly_tax = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Mjesečni porez (EUR)',
    )
    # Doprinosi (MIO + zdravstveno) — paušalci plaćaju fiksno
    monthly_contributions = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('290.98'),
        verbose_name='Mjesečni doprinosi (EUR)',
        help_text='MIO I. + zdravstveno (fiksni iznos)',
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [('valid_year', 'tier_number')]
        ordering = ['valid_year', 'tier_number']
        verbose_name = 'Paušalni razred'
        verbose_name_plural = 'Paušalni razredi'

    def __str__(self):
        return (
            f'{self.valid_year} Tier {self.tier_number}: '
            f'{self.min_income}-{self.max_income}€ → {self.annual_tax}€/god'
        )

    @classmethod
    def get_tier_for_income(cls, income, year=None):
        """Odredi tier za dani primitak."""
        if year is None:
            year = timezone.now().year
        return cls.objects.filter(
            valid_year=year,
            is_active=True,
            min_income__lte=income,
            max_income__gte=income,
        ).first()

    @classmethod
    def get_all_tiers(cls, year=None):
        """Svi tierovi za godinu — za slider/optimizer UI."""
        if year is None:
            year = timezone.now().year
        return cls.objects.filter(valid_year=year, is_active=True)


# ═══════════════════════════════════════════════════════════════════
#  7. OSOBNI ODBITAK KOEFICIJENTI — Dinamička tablica
# ═══════════════════════════════════════════════════════════════════

class OsobniOdbitakKoeficijent(models.Model):
    """
    Koeficijenti za uvećanje osobnog odbitka — dinamički iz Admin panela.

    2026:
      Uzdržavani član:           0.5  → +300€/mj
      1. dijete:                 0.5  → +300€/mj
      2. dijete:                 0.7  → +420€/mj
      3. dijete:                 1.0  → +600€/mj
      Djelomična invalidnost:    0.3  → +180€/mj
      100% invalidnost:          1.0  → +600€/mj
      HRVI:                      0.5-1.5 ovisno o grupi
    """

    class Category(models.TextChoices):
        DEPENDENT        = 'dependent',     _('Uzdržavani član')
        CHILD_1          = 'child_1',       _('1. dijete')
        CHILD_2          = 'child_2',       _('2. dijete')
        CHILD_3          = 'child_3',       _('3. dijete')
        CHILD_4          = 'child_4',       _('4. dijete')
        CHILD_5_PLUS     = 'child_5_plus',  _('5. i svako daljnje dijete')
        PARTIAL_DISABILITY = 'partial_dis', _('Djelomična invalidnost')
        FULL_DISABILITY  = 'full_dis',      _('100% invalidnost')
        HRVI_GROUP_1     = 'hrvi_1',        _('HRVI I. skupina')
        HRVI_GROUP_2     = 'hrvi_2',        _('HRVI II. skupina')
        HRVI_OTHER       = 'hrvi_other',    _('HRVI ostale skupine')

    valid_year = models.IntegerField(verbose_name='Porezna godina')
    category = models.CharField(max_length=20, choices=Category.choices)
    coefficient = models.DecimalField(
        max_digits=5, decimal_places=2,
        verbose_name='Koeficijent',
    )
    base_amount = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('600'),
        verbose_name='Osnovica (EUR/mj)',
        help_text='Osnovni osobni odbitak na koji se primjenjuje koeficijent',
    )
    monthly_amount = models.DecimalField(
        max_digits=8, decimal_places=2,
        verbose_name='Mjesečni iznos uvećanja (EUR)',
        help_text='base_amount × coefficient',
    )

    # AI hint za detekciju
    detection_hint = models.TextField(
        blank=True,
        help_text=(
            'Kako AI prepoznaje ovu olakšicu? Npr. '
            '"Provjeri ima li korisnik djecu u sustavu, '
            'pitaj za potvrdu o invalidnosti, '
            'provjeri adresu za potpomognuto područje"'
        ),
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [('valid_year', 'category')]
        ordering = ['valid_year', 'category']
        verbose_name = 'Koeficijent osobnog odbitka'
        verbose_name_plural = 'Koeficijenti osobnog odbitka'

    def __str__(self):
        return (
            f'{self.valid_year} {self.get_category_display()}: '
            f'{self.coefficient} → +{self.monthly_amount}€/mj'
        )

    def save(self, *args, **kwargs):
        # Auto-calculate monthly_amount
        self.monthly_amount = (self.base_amount * self.coefficient).quantize(
            Decimal('0.01')
        )
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════
#  8. AUDIT LOG — Tko je što radio, za compliance
# ═══════════════════════════════════════════════════════════════════

class TaxAuditLog(models.Model):
    """
    Nepromjenjivi audit trail za sve radnje u tax_wizard-u.
    Zakonska obveza čuvanja: 11 godina.
    """

    class Action(models.TextChoices):
        CREATE      = 'create',     _('Kreiranje')
        UPDATE      = 'update',     _('Ažuriranje')
        FINALIZE    = 'finalize',   _('Finalizacija')
        SUBMIT      = 'submit',     _('Podnošenje')
        REVIEW      = 'review',     _('Pregled')
        CORRECTION  = 'correction', _('Ispravak')
        SIMULATE    = 'simulate',   _('Simulacija')
        XML_EXPORT  = 'xml_export', _('XML export')
        PDF_EXPORT  = 'pdf_export', _('PDF export')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        TaxWizardSession, on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='+',
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    details = models.JSONField(
        default=dict,
        help_text='Detalji akcije — diff podataka, stari/novi status, itd.',
    )
    data_hash_before = models.CharField(max_length=64, blank=True)
    data_hash_after = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', '-created_at']),
        ]
        verbose_name = 'Porezni audit log'
        verbose_name_plural = 'Porezni audit logovi'

    def __str__(self):
        return f'{self.get_action_display()} — {self.session} — {self.created_at:%d.%m.%Y %H:%M}'


# ═══════════════════════════════════════════════════════════════════
#  9. PARTNER TAX ACCOUNT — B2B2C distribucija (Marija = distributer)
# ═══════════════════════════════════════════════════════════════════

class PartnerTaxAccount(models.Model):
    """
    Računovodstveni servis kao distributer poreznih usluga.

    B2B2C flow:
      1. Marija (računovođa) registrira se kao partner
      2. Dobije unique referral link: /porez/ref/MARIJA2026
      3. Šalje link klijentima (WhatsApp, email)
      4. Klijent ispuni wizard → Marija vidi draft
      5. Na plaćanju: Stripe split 70/30

    brand_name + brand_logo → white-label wizard za klijente.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='tax_partner_account',
        verbose_name='Firma partnera',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='tax_partner_accounts',
        verbose_name='Vlasnik računa',
    )

    # Branding — white-label
    brand_name = models.CharField(
        max_length=200, verbose_name='Naziv branda',
        help_text='Prikazuje se klijentu umjesto "LIMIT Connect"',
    )
    brand_logo = models.ImageField(
        upload_to='tax_wizard/brands/', blank=True,
        verbose_name='Logo partnera',
    )
    brand_color = models.CharField(
        max_length=7, default='#C8A96E',
        verbose_name='Primarna boja',
        help_text='HEX boja za wizard UI',
    )

    # Referral
    referral_code = models.CharField(
        max_length=20, unique=True, db_index=True,
        verbose_name='Referral kod',
        help_text='Jedinstveni kod za tracking (npr. MARIJA2026)',
    )

    # Provizija
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.3000'),
        verbose_name='Stopa provizije',
        help_text='0.30 = 30% od svake porezne prijave',
    )

    # Stripe Connect
    stripe_connect_id = models.CharField(
        max_length=100, blank=True,
        verbose_name='Stripe Connect Account ID',
        help_text='acct_XXXXX — za split payment',
    )

    # Statistike (denormalizirano za brzi dashboard)
    total_referrals = models.PositiveIntegerField(
        default=0, verbose_name='Ukupno klijenata',
    )
    total_sessions = models.PositiveIntegerField(
        default=0, verbose_name='Ukupno sesija',
    )
    total_earned = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Ukupno zarađeno (EUR)',
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Partner Tax Account'
        verbose_name_plural = 'Partner Tax Accounts'
        indexes = [
            models.Index(fields=['referral_code']),
        ]

    def __str__(self):
        return f'{self.brand_name} ({self.company.name}) — {self.total_referrals} klijenata'

    @property
    def referral_url(self):
        return f'/porezni-savjetnik/ref/{self.referral_code}/'
