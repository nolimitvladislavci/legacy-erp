import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


class Invoice(models.Model):
    DOCTYPE_CHOICES = [
        ('PO', _('Ponuda')),
        ('P',  _('Predračun')),
        ('R',  _('Račun')),
        ('A',  _('Avansni račun')),
        ('S',  _('Storno račun')),
        ('GS', _('Gutschrift (DE)')),
        ('FA', _('Faktura (B2B)')),
        ('URA', _('Ulazni racun')),
        ('RN', _('Racun - gotovina')),
        ('OTP', _('Otpremnica (Lieferschein)')),
        ('ZR',  _('Zbirni račun (Sammelrechnung)')),
        ('NAR', _('Narudžbenica')),
    ]
    STATUS_CHOICES = [
        ('DRAFT',     _('Nacrt')),
        ('CONFIRMED',  _('Potvrdjeno')),
        ('FISCALIZED', _('Fiskalizirano')),
        ('SENT',      _('Poslano')),
        ('ACCEPTED',  _('Prihvaćeno')),
        ('REJECTED',  _('Odbijeno')),
        ('EXPIRED',   _('Isteklo')),
        ('PAID',      _('Plaćeno')),
        ('UNPAID',    _('Neplaćeno')),
        ('OVERDUE',   _('Dospijelo')),
        ('CANCELLED', _('Otkazano')),
        ('STORNO',    _('Stornirano')),
    ]
    PAYMENT_CHOICES = [
        ('TRANSAKCIJSKI', _('Transakcijski račun')),
        ('GOTOVINA',      _('Gotovina')),
        ('KARTICA',       _('Kartica')),
        ('VIRMAN',        _('Virman')),
        ('ÜBERWEISUNG',   _('Überweisung (DE)')),
        ('BAR',           _('Bar (DE)')),
    ]
    COUNTRY_CHOICES = [
        ('HR', 'Hrvatska'),
        ('DE', 'Deutschland'),
    ]

    # Identifikacija
    doctype     = models.CharField(max_length=10, choices=DOCTYPE_CHOICES, default='R', verbose_name=_('Vrsta'))
    country     = models.CharField(max_length=2, choices=COUNTRY_CHOICES, default='HR', verbose_name=_('Zemlja'))
    uuid         = models.UUIDField(default=uuid.uuid4, unique=True)
    client_token = models.UUIDField(default=__import__("uuid").uuid4, unique=True,
                                     verbose_name='Client portal token')
    number      = models.CharField(max_length=50, unique=True, verbose_name=_('Broj računa'))
    internal_id = models.CharField(max_length=50, blank=True, verbose_name=_('Interni ID'))

    # Datumi
    date_issued   = models.DateTimeField(verbose_name=_('Datum izdavanja'))
    date_due      = models.DateField(null=True, blank=True, verbose_name=_('Rok plaćanja'))
    date_delivery = models.DateField(null=True, blank=True, verbose_name=_('Datum isporuke'))

    # Klijent (denormalizirani podaci za PDF)
    client_name    = models.CharField(max_length=200, verbose_name=_('Klijent / Empfänger'))
    client_address = models.TextField(blank=True, verbose_name=_('Adresa'))
    client_city    = models.CharField(max_length=100, blank=True, verbose_name=_('Grad / PLZ Stadt'))
    client_country = models.CharField(max_length=100, blank=True, default='Hrvatska', verbose_name=_('Država'))
    client_oib     = models.CharField(max_length=30, blank=True, verbose_name=_('OIB / USt-IdNr'))
    client_email   = models.EmailField(blank=True, verbose_name=_('Email klijenta'))

    # Plaćanje
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES,
                                       default='TRANSAKCIJSKI', verbose_name=_('Način plaćanja'))
    currency       = models.CharField(max_length=3, default='EUR', verbose_name=_('Valuta'))
    iban           = models.CharField(max_length=34, blank=True, verbose_name=_('IBAN za uplatu'))
    swift          = models.CharField(max_length=11, blank=True, verbose_name=_('SWIFT/BIC'))
    reference_number = models.CharField(max_length=50, blank=True, verbose_name=_('Poziv na broj'))

    # Iznosi
    subtotal    = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Iznos bez PDV/MwSt'))
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=25, verbose_name=_('PDV/MwSt %'))
    tax_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('PDV/MwSt iznos'))
    total       = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Ukupno / Gesamt'))

    # Fiskalizacija (HR)
    is_fiscalized   = models.BooleanField(default=False, verbose_name=_('Fiskalizirano'))
    zki             = models.CharField(max_length=32, null=True, blank=True, verbose_name='ZKI')
    jir             = models.CharField(max_length=36, null=True, blank=True, verbose_name='JIR')
    operator_oib    = models.CharField(max_length=11, blank=True, verbose_name=_('OIB operatera'))
    fiscal_datetime = models.DateTimeField(null=True, blank=True, verbose_name=_('Datum fiskalizacije'))

    tax_status = models.CharField(
        max_length=20,
        blank=True,
        default='standard',
        verbose_name='PDV status racuna',
        help_text='standard, reduced, zero, reverse_charge, exempt, pausalac, kleinunternehmer',
    )

    # Dodatno
    note          = models.TextField(blank=True, verbose_name=_('Napomena / Anmerkung'))
    internal_note = models.TextField(blank=True, verbose_name=_('Interna napomena'))
    qr_code_base64 = models.TextField(null=True, blank=True)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name=_('Status'))
    storno_of     = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name='storno_invoices', verbose_name=_('Storno od računa'))
    cancel_reason = models.CharField(max_length=200, blank=True, verbose_name=_('Razlog storniranja'))

    # Tvrtka izdavatelj (denormalizirani podaci za PDF/arhivu)
    issuer_name    = models.CharField(max_length=200, blank=True, verbose_name=_('Naziv izdavatelja'))
    issuer_address = models.CharField(max_length=255, blank=True)
    issuer_oib     = models.CharField(max_length=30, blank=True)
    issuer_iban    = models.CharField(max_length=34, blank=True)
    issuer_swift   = models.CharField(max_length=11, blank=True, default='', verbose_name='Issuer BIC/SWIFT')
    issuer_email   = models.EmailField(blank=True)
    issuer_phone   = models.CharField(max_length=50, blank=True)

    # Fiskalizacijska polja - prodajno mjesto i operater
    business_location = models.ForeignKey(
        'invoicing.BusinessLocation', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Poslovni prostor'))
    operator = models.ForeignKey(
        'invoicing.FiscalOperator', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Operater'))
    invoice_sequence = models.PositiveIntegerField(
        default=1, verbose_name=_('Redni broj u prostoru'))

    # Veze na master podatke (normalizirano)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
        verbose_name=_('Tvrtka izdavatelj'),
    )
    objects = CompanyManager()
    invoice_profile = models.ForeignKey(
        'invoicing.InvoiceProfile', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='profile_invoices',
        verbose_name=_('Profil fakturiranja'),
    )
    partner = models.ForeignKey(
        'partners.Partner', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
        verbose_name=_('Partner (klijent)'),
    )

    # NKD djelatnost (ispisuje se na računu / ponudi)
    nkd_code = models.ForeignKey(
        'companies.NKDCode', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_('NKD djelatnost'),
        help_text=_('Prikazuje se na računu i ponudi'),
    )


    # ── Synesis arhiva ────────────────────────────────────────────────
    synesis_id = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Synesis ID',
        help_text='Originalni ID iz Synesis MDB baze',
    )
    synesis_year = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Synesis godina',
        help_text='Godina iz koje je uvezena faktura',
    )

    # ── Klasifikacija po HR propisima ────────────────────────────────
    invoice_type = models.CharField(
        max_length=30,
        choices=[
            ('racun', _('Račun')),
            ('avansni', _('Avansni račun (predujam)')),
            ('storno', _('Storno račun')),
            ('odobrenje', _('Knjižno odobrenje')),
            ('zaduzenje', _('Knjižno zaduženje')),
            ('zbirni', _('Zbirni račun')),
            ('vlastita_potrosnja', _('Vlastita potrošnja')),
            ('zavrsni', _('Završni račun')),
        ],
        default='racun',
        verbose_name=_('Vrsta računa'),
    )
    tax_classification = models.CharField(
        max_length=5,
        choices=[
            ('R1', _('R1 — obveznik PDV-a')),
            ('R2', _('R2 — mali porezni obveznik')),
        ],
        default='R1',
        verbose_name=_('Porezna oznaka'),
    )
    place_of_supply = models.CharField(
        max_length=20,
        choices=[
            ('domestic', _('Tuzemni')),
            ('intra_eu_b2b', _('Intra-EU B2B (reverse charge)')),
            ('intra_eu_b2c', _('Intra-EU B2C (OSS)')),
            ('export', _('Izvoz (izvan EU)')),
        ],
        default='domestic',
        verbose_name=_('Mjesto oporezivanja'),
    )
    # Veza za avansne/završne račune
    related_invoice = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='related_invoices',
        verbose_name=_('Povezani račun'),
        help_text=_('Za storno → original, za završni → avansni'),
    )

    archive_hash = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Archive hash',
        help_text='SHA-256 hash originalnog zapisa za integritet',
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name='Zaključano',
        help_text='Synesis arhivske fakture se ne mogu editirati',
    )
    deletion_protected_until = models.DateField(
        null=True, blank=True,
        verbose_name='Zaštita od brisanja do',
        help_text='Zakonska obveza čuvanja (11 godina od izdavanja)',
    )

    # Workflow chain (Ponuda → Predračun → Račun)
    source_document = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='derived_documents',
        verbose_name=_('Izvorni dokument'),
        help_text=_('Ponuda ili predračun iz kojeg je kreiran ovaj dokument'),
    )
    validity_date = models.DateField(
        null=True, blank=True,
        verbose_name=_('Rok važnosti'),
        help_text=_('Rok do kojeg ponuda / predračun vrijedi'),
    )

    # Izvor kreiranja
    SOURCE_CHOICES = [
        ('wizard_field', 'Terenski wizard'),
        ('wizard_office', 'Uredski wizard'),
        ('pos', 'POS'),
        ('api', 'API'),
        ('import', 'Import'),
        ('synesis', 'Synesis arhiva'),
        ('manual', 'Ručni unos'),
        ('duplicate', 'Duplikat'),
        ('from_quote', 'Iz ponude'),
        ('eracun', 'e-Racun'),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual',
                               blank=True, verbose_name=_('Izvor'))

    # Projekt (veza na worktime.Project)
    project = models.ForeignKey(
        'worktime.Project', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
        verbose_name=_('Projekt'),
    )

    # Fotografija (terenski rad)
    photo = models.ImageField(upload_to='invoices/photos/%Y/%m/', blank=True,
                               verbose_name=_('Fotografija'))

    # PDF datoteka
    pdf_file = models.FileField(upload_to='invoices/pdf/%Y/%m/', blank=True,
                                 verbose_name=_('PDF datoteka'))

    # Meta
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='created_invoices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoicing_invoice'
        verbose_name = _('Račun')
        verbose_name_plural = _('Računi')
        ordering = ['-date_issued']

    def __str__(self):
        return f"{self.number} \u2013 {self.client_name} ({self.total} {self.currency})"

    def clean(self):
        from django.core.exceptions import ValidationError
        from konto.models import AccountingPeriod
        is_draft = (self.status == 'DRAFT')

        # Zaključano razdoblje: blokiraj samo ne-DRAFT dokumente
        if self.date_issued and hasattr(self, 'company') and self.company_id:
            if not is_draft and AccountingPeriod.is_period_locked(self.company, self.date_issued.year, self.date_issued.month):
                raise ValidationError(f"Razdoblje {self.date_issued.month:02d}/{self.date_issued.year} je zaključano. Izdavanje računa nije moguće.")

        # DocumentValidator — 8 pravila (Sprint 1E)
        # DRAFT: samo WARN/INFO upozorenja, nikad BLOCK
        # BLOCK se okida tek na tranziciji DRAFT -> ISSUED/SENT/FISCALIZED
        try:
            from invoicing.document_validator import validator
            issues = validator.validate(self)
            if not is_draft:
                blocking = [i for i in issues if i.severity.value == 'block']
                if blocking:
                    raise ValidationError({i.field or '__all__': i.message for i in blocking})
            self._validation_warnings = [i for i in issues if i.severity.value in ('warn', 'info')]
        except ValidationError:
            raise
        except Exception:
            pass

    def save(self, *args, **kwargs):
        """
        Zakonska zaštita:
        1. Fiskalizirani/zaključani račun se ne smije mijenjati (ZOR čl.9, Zakon o fiskalizaciji)
        2. deletion_protected_until se automatski postavlja na datum_izdavanja + 11 godina (ZOR čl.10)
        """
        from django.core.exceptions import PermissionDenied

        # ── Guard: zaključano obračunsko razdoblje (Mina 1) ─────────────────
        if not self.pk and self.date_issued and hasattr(self, 'company') and self.company_id:
            from konto.models import AccountingPeriod
            _dt = self.date_issued
            if hasattr(_dt, 'date'):
                _dt = _dt.date()
            if AccountingPeriod.is_period_locked(self.company, _dt.year, _dt.month):
                raise PermissionDenied(
                    f"Razdoblje {_dt.month:02d}/{_dt.year} je zaključano. "
                    f"Nova faktura se ne može kreirati u zatvorenom periodu. "
                    f"Koristite sljedeći otvoreni mjesec ili kontaktirajte administratora."
                )

        # ── Guard: zaključani račun ──────────────────────────────────────────
        if self.pk:
            _uf = kwargs.get('update_fields')
            # Polja koja se smiju mijenjati čak i na zaključanom računu
            _safe_fields = {
                'qr_code_base64', 'pdf_file', 'photo', 'updated_at',
                'is_locked', 'deletion_protected_until', 'archive_hash',
                'jir', 'zki', 'is_fiscalized', 'fiscal_datetime',
                'operator_oib', 'issuer_phone',
            }
            if self.is_locked and _uf is not None and not set(_uf).issubset(_safe_fields):
                raise PermissionDenied(
                    f"Račun {self.number} je zaključan (fiskaliziran/arhiviran) "
                    f"i ne može se mijenjati. Izdajte Storno račun."
                )

        # ── Auto: postavi deletion_protected_until = datum + 11 godina ──────
        if not self.deletion_protected_until and self.date_issued:
            try:
                issued = self.date_issued
                if hasattr(issued, 'date'):
                    issued = issued.date()
                self.deletion_protected_until = issued.replace(year=issued.year + 11)
            except Exception:
                pass

        # ── Auto: SHA-256 archive_hash za integritet dokumenta ──────────
        import hashlib
        hash_source = "|".join([
            str(self.number or ""),
            str(self.total or "0"),
            str(self.jir or ""),
            str(self.zki or ""),
            str(self.date_issued or ""),
            str(self.client_name or ""),
            str(self.issuer_oib or ""),
        ])
        self.archive_hash = hashlib.sha256(hash_source.encode("utf-8")).hexdigest()

        # ── Auto: fiscal_rules check (ne blokira, samo bilježi) ─────────
        if not getattr(self, '_skip_fiscal_check', False):
            try:
                from invoicing.fiscal_rules import should_fiscalize
                should, reason = should_fiscalize(self)
                if not should and self.doctype in ('R', 'RN', 'A', 'FA'):
                    if not self.internal_note or 'fiscal_skip' not in self.internal_note:
                        self.internal_note = (self.internal_note or '') + chr(10) + '[fiscal_skip: %s]' % reason
            except Exception:
                pass

        super().save(*args, **kwargs)

    def recalculate(self):
        from decimal import Decimal
        items = self.items.all()
        self.subtotal = sum(i.total_price for i in items)
        # Calculate tax from per-item tax_rate (not flat tax_percent)
        self.tax_amount = sum(
            i.total_price * i.tax_rate / Decimal('100')
            for i in items
        )
        self.total = self.subtotal + self.tax_amount
        return self

    @property
    def is_hr(self):
        return self.country == 'HR'

    @property
    def is_de(self):
        return self.country == 'DE'

    @property
    def effective_iban(self):
        """Uvijek vrati IBAN izdavatelja bez obzira na koji je field pohranjen.
        issuer_iban je canonical; iban je legacy field za stare zapise."""
        return self.issuer_iban or self.iban or ''

    @property
    def effective_swift(self):
        """Uvijek vrati SWIFT izdavatelja (issuer_swift > swift > prazan string)."""
        return self.issuer_swift or self.swift or ''


class InvoiceItem(models.Model):
    invoice      = models.ForeignKey(Invoice, on_delete=models.CASCADE,
                                      related_name='items', verbose_name=_('Račun'))
    description  = models.TextField(verbose_name=_('Opis'), default='')
    quantity     = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name=_('Količina'))
    unit         = models.CharField(max_length=10, default='kom', verbose_name=_('Jed.mjera'))
    unit_price   = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Jed.cijena'))
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name=_('Popust %'))
    total_price  = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Ukupno'))
    gross_total  = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Ukupno s PDV'))
    tax_rate     = models.DecimalField(max_digits=5, decimal_places=2, default=25, verbose_name=_('PDV %'))

    # Normalizirana veza na TaxRate model
    tax_rate_obj = models.ForeignKey(
        'companies.TaxRate', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_('PDV stopa'),
        help_text=_('Veza na poreznu stopu iz registra'),
    )

    # Grupiranje i sortiranje stavki na računu
    section = models.CharField(max_length=100, blank=True, default='', verbose_name=_('Sekcija'),
                                help_text=_('Opcionalano grupiranje stavki na računu'))
    sort_order = models.PositiveIntegerField(default=0, verbose_name=_('Redoslijed'))

    # Veza na InventoryItem (opcionalno - za praćenje zaliha)
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoice_items',
        verbose_name=_('Artikl iz zalihe'),
    )

    class Meta:
        db_table = 'invoicing_invoiceitem'
        verbose_name = _('Stavka računa')
        verbose_name_plural = _('Stavke računa')

    def __str__(self):
        return f"{self.description} \xd7 {self.quantity} = {self.total_price}"

    def save(self, *args, **kwargs):
        # Sync tax_rate from tax_rate_obj if set
        if self.tax_rate_obj_id and self.tax_rate_obj:
            self.tax_rate = self.tax_rate_obj.rate
        self.total_price = round(
            Decimal(str(self.quantity)) * Decimal(str(self.unit_price)) * (1 - Decimal(str(self.discount_percent)) / Decimal('100')), 2
        )
        self.gross_total = round(self.total_price * (1 + Decimal(str(self.tax_rate)) / Decimal('100')), 2)
        super().save(*args, **kwargs)




class InvoiceEvent(models.Model):
    """Audit trail — every action on an invoice is logged here for the Timeline."""
    EVENT_TYPES = [
        ('created', 'Dokument kreiran'),
        ('lookup', 'Lookup partnera'),
        ('vies_ok', 'VIES potvrda'),
        ('vies_fail', 'VIES negativan'),
        ('reverse_charge', 'Reverse Charge primijenjen'),
        ('item_added', 'Stavka dodana'),
        ('item_weighed', 'Stavka izvagana'),
        ('rollwagen_bound', 'Rollwagen vezan'),
        ('dispatched', 'Otpremljeno'),
        ('fiscalized', 'Fiskalizirano'),
        ('paid', 'Placeno'),
        ('storno_partial', 'Djelomicni storno'),
        ('storno_full', 'Potpuni storno'),
        ('sent_email', 'Poslano emailom'),
        ('sent_whatsapp', 'Poslano WhatsApp'),
        ('morphed', 'Dokument mutirao'),
        ('status_change', 'Promjena statusa'),
        ('edited', 'Izmjena podataka'),
        ('note', 'Biljeska'),
    ]
    invoice = models.ForeignKey(
        'Invoice', on_delete=models.CASCADE,
        related_name='events',
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    title = models.CharField(max_length=200)
    detail = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    # ── Audit: tko je editirao, s kojeg uređaja ─────────────────────────────
    # ZOR čl. 9 + GoBD §147 — dokazivost svake izmjene
    updated_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoice_events_updated',
        verbose_name='Izvršio izmjenu',
    )
    client_ip = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name='IP adresa',
        help_text='IP adresa korisnika koji je izvršio akciju',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invoicing_invoice_event'
        ordering = ['-created_at']
        verbose_name = 'Invoice Event'

    def __str__(self):
        return f"{self.event_type}: {self.title}"

    def to_dict(self):
        return {
            'id': self.pk,
            'event_type': self.event_type,
            'title': self.title,
            'detail': self.detail,
            'metadata': self.metadata,
            'actor': self.actor.get_full_name() if self.actor else '',
            'created_at': self.created_at.isoformat() if self.created_at else '',
            'time_display': self.created_at.strftime('%H:%M') if self.created_at else '',
            'date_display': self.created_at.strftime('%d.%m.%Y') if self.created_at else '',
        }


class DunningRule(models.Model):
    CHANNEL_CHOICES = [
        ('email',    'Email'),
        ('whatsapp', 'WhatsApp'),
        ('both',     'Email + WhatsApp'),
    ]
    TONE_CHOICES = [
        ('gentle', 'Blagi podsjetnik'),
        ('firm',   'Asertivan zahtjev'),
        ('legal',  'Formalna opomena'),
    ]

    company      = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                      related_name='dunning_rules')
    step         = models.PositiveIntegerField(verbose_name='Korak')
    days_overdue = models.PositiveIntegerField(verbose_name='Dana kasnjenja')
    channel      = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='email')
    tone         = models.CharField(max_length=20, choices=TONE_CHOICES, default='gentle')
    cc_admin     = models.BooleanField(default=False, verbose_name='CC company_admin')
    is_active    = models.BooleanField(default=True)

    class Meta:
        unique_together = ('company', 'step')
        ordering = ['company', 'step']
        verbose_name = 'Pravilo opomene'
        verbose_name_plural = 'Pravila opomena'

    def __str__(self):
        return (f"{self.company.name} | Korak {self.step}: "
                f"D+{self.days_overdue} [{self.channel}/{self.tone}]")



class DunningHistory(models.Model):
    """Audit log for every dunning reminder sent."""
    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
    ]
    STATUS_CHOICES = [
        ("sent", "Poslano"),
        ("failed", "Neuspjelo"),
        ("bounced", "Odbijeno"),
    ]

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="dunning_history",
        verbose_name=_("Tvrtka"),
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE,
        related_name="dunning_history",
        verbose_name=_("Racun"),
    )
    dunning_rule = models.ForeignKey(
        DunningRule, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="history",
        verbose_name=_("Pravilo opomene"),
    )
    step = models.PositiveIntegerField(verbose_name=_("Korak"))
    channel_used = models.CharField(max_length=20, choices=CHANNEL_CHOICES, verbose_name=_("Kanal"))
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Poslano"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="sent", verbose_name=_("Status"))
    error_message = models.TextField(blank=True, default="", verbose_name=_("Greska"))
    email_subject = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Predmet"))
    email_body = models.TextField(blank=True, default="", verbose_name=_("Sadrzaj"))
    recipient_email = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Primatelj"))

    objects = CompanyManager()

    class Meta:
        db_table = "invoicing_dunninghistory"
        ordering = ["-sent_at"]
        verbose_name = _("Dunning povijest")
        verbose_name_plural = _("Dunning povijest")

    def __str__(self):
        return f"Opomena #{self.step} za {self.invoice.number} ({self.status})"
