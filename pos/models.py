"""
POS Kasa — Point of Sale module
Podržava HR fiskalizaciju, bar kod skeniranje i integraciju s invoicing app.
"""
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


class POSTerminal(models.Model):
    """
    Fizička blagajna / kasa.
    Jedna tvrtka može imati više kasa (npr. Kasa 1, Kasa 2).
    Svaka kasa je vezana uz BusinessLocation radi fiskalizacije.
    """
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='pos_terminals',
        verbose_name=_('Tvrtka'),
    )
    objects = CompanyManager()
    business_location = models.ForeignKey(
        'invoicing.BusinessLocation', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pos_terminals',
        verbose_name=_('Poslovni prostor (za fiskalizaciju)'),
    )
    name          = models.CharField(max_length=100, verbose_name=_('Naziv kase'), help_text='Npr. Kasa 1, Šank, Blagajna')
    terminal_code = models.CharField(max_length=20, verbose_name=_('Kod terminala'), help_text='Jedinstveni kod npr. KS001')
    description   = models.CharField(max_length=255, blank=True, verbose_name=_('Opis / Lokacija'))
    is_active     = models.BooleanField(default=True, verbose_name=_('Aktivna'))
    branch        = models.ForeignKey(
        'companies.CompanyBranch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pos_terminals',
        verbose_name='Podružnica',
    )
    pos_type      = models.CharField(
        max_length=15,
        choices=[('quick', 'Brza blagajna'), ('retail', 'Maloprodaja'), ('restaurant', 'Restoran'), ('field', 'Terenska prodaja'), ('service', 'Usluge'), ('reception', 'Recepcija'), ('gym', 'Fitness / Gym'), ('appointment', 'Termini / Salon')],
        default='retail',
        verbose_name=_('Tip POS sučelja'),
    )
    # Filter artikala — svaki terminal vidi samo relevantne kategorije
    category_filter = models.CharField(
        max_length=200, blank=True, verbose_name=_('Filter kategorija'),
        help_text=_('Comma-separated: food,drink,dessert ili prazno=sve. Optika: product,service'),
    )
    access_token  = models.CharField(
        max_length=32, unique=True, blank=True, null=True,
        verbose_name="QR pristupni token",
        help_text="Auto-generiran. QR kod na zidu - skeniraj, blagajna se otvori.",
    )
    created_at    = models.DateTimeField(auto_now_add=True)
    # Training mode (HR-P13)
    is_training   = models.BooleanField(default=False, verbose_name=_("Training modus"),
        help_text="Bonovi se NE fiskaliziraju. Watermark OBUKA na svim bonovima.")
    # Customer Display token (HR-P12)
    display_token = models.CharField(max_length=32, unique=True, blank=True, null=True,
        verbose_name="Customer Display token",
        help_text="Token za pristup ekranu kupca (drugi ekran/tablet).")

    # Context-Aware QuickActions (POS kao Centar Svijeta)
    quick_actions = models.JSONField(
        default=list, blank=True,
        verbose_name="Brze tipke (QuickActions)",
        help_text="JSON lista akcija. Prazno = auto-generiranje po pos_type.",
    )

    def get_quick_actions(self):
        """Vraca brze tipke — korisnicke ako postoje, inace default po pos_type."""
        if self.quick_actions:
            return self.quick_actions
        bt = getattr(self.company, "business_type", "doo") if self.company_id else "doo"
        return get_default_quick_actions(self.pos_type, bt)

    def save(self, *args, **kwargs):
        if not self.access_token:
            import secrets
            self.access_token = secrets.token_urlsafe(20)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name        = _('POS terminal (kasa)')
        verbose_name_plural = _('POS terminali (kase)')
        unique_together     = [('company', 'terminal_code')]
        ordering            = ['company', 'name']

    def __str__(self):
        return f'{self.name} ({self.terminal_code})'


class POSSession(models.Model):
    """
    Smjena / dnevno otvaranje blagajne.
    Svaka smjena se otvara i zatvara — obavezno za fiskalizaciju (Z-izvješće).
    """
    class Status(models.TextChoices):
        OPEN   = 'open',   _('Otvorena')
        CLOSED = 'closed', _('Zatvorena')
        Z_DONE = 'z_done', _('Z-izvješće generirano')

    terminal      = models.ForeignKey(POSTerminal, on_delete=models.CASCADE,
                                       related_name='sessions', verbose_name=_('Terminal'))
    operator      = models.ForeignKey(User, on_delete=models.SET_NULL,
                                       null=True, related_name='pos_sessions', verbose_name=_('Operater'))
    session_number = models.PositiveIntegerField(verbose_name=_('Broj smjene'))

    opened_at     = models.DateTimeField(auto_now_add=True, verbose_name=_('Otvorena u'))
    closed_at     = models.DateTimeField(null=True, blank=True, verbose_name=_('Zatvorena u'))

    opening_cash  = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                         verbose_name=_('Gotovina pri otvaranju (€)'))
    closing_cash  = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                         verbose_name=_('Prebrojana gotovina pri zatvaranju (€)'))

    status        = models.CharField(max_length=15, choices=Status.choices,
                                      default=Status.OPEN, verbose_name=_('Status'))
    z_report_number = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Broj Z-izvješća'))
    notes         = models.TextField(blank=True, verbose_name=_('Napomene'))

    # Terenska prodaja
    is_field_session  = models.BooleanField(default=False, verbose_name=_('Terenska smjena'))
    vehicle_plate     = models.CharField(max_length=20, blank=True, verbose_name=_('Reg. oznaka vozila'))
    route_name        = models.CharField(max_length=200, blank=True, verbose_name=_('Ruta'))
    loaded_items_json = models.JSONField(null=True, blank=True, verbose_name=_('Utovareni artikli'))
    returned_items_json = models.JSONField(null=True, blank=True, verbose_name=_('Vraceni artikli'))

    # Training mode (HR-P13) — session-level
    is_training = models.BooleanField(default=False, verbose_name=_("Training smjena"))
    # Multi-operator: blagajnici koji su radili u ovoj smjeni
    active_cashiers = models.ManyToManyField(
        'pos.POSCashier', blank=True,
        related_name='sessions_worked',
        verbose_name=_('Blagajnici u smjeni'),
    )

    class Meta:
        verbose_name        = _('POS smjena')
        verbose_name_plural = _('POS smjene')
        unique_together     = [('terminal', 'session_number')]
        ordering            = ['-opened_at']

    def __str__(self):
        return f'Smjena #{self.session_number} – {self.terminal} ({self.get_status_display()})'

    @property
    def total_sales(self):
        return self.receipts.filter(
            status=POSReceipt.Status.PAID
        ).aggregate(models.Sum('total'))['total__sum'] or Decimal('0.00')

    @property
    def total_cash_sales(self):
        return self.receipts.filter(
            status=POSReceipt.Status.PAID,
            payment_lines__method=POSPaymentLine.Method.CASH,
        ).aggregate(models.Sum('payment_lines__amount'))['payment_lines__amount__sum'] or Decimal('0.00')

    @property
    def total_deposits_amount(self):
        return sum(d.amount for d in self.cash_deposits.filter(deposit_type='deposit'))

    @property
    def total_withdrawals_amount(self):
        return sum(d.amount for d in self.cash_deposits.filter(deposit_type='withdrawal'))

    @property
    def expected_closing_cash(self):
        return self.opening_cash + self.total_cash_sales + self.total_deposits_amount - self.total_withdrawals_amount

    @property
    def cash_difference(self):
        return self.closing_cash - self.expected_closing_cash


class POSReceipt(models.Model):
    """
    Jedan račun / bon na blagajni.
    Automatski kreira Invoice (+ fiskalizira ga za HR).
    """
    class Status(models.TextChoices):
        OPEN      = 'open',      _('Otvoreni bon')
        PAID      = 'paid',      _('Plaćen')
        CANCELLED = 'cancelled', _('Storniran / Otkazan')
        REFUNDED  = 'refunded',  _('Povrat')

    uuid           = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    session        = models.ForeignKey(POSSession, on_delete=models.CASCADE,
                                        related_name='receipts', verbose_name=_('Smjena'))
    receipt_number = models.PositiveIntegerField(verbose_name=_('Broj bona'))
    global_number  = models.PositiveIntegerField(
        null=True, blank=True, db_index=True,
        verbose_name=_('Globalni redni broj'),
        help_text=_('Jedinstven po firmi, bez duplikata. Za fiskalizaciju i analizu.'),
    )

    # Veza na Invoice (kreira se automatski pri plaćanju + fiskalizira)
    invoice        = models.OneToOneField(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pos_receipt',
        verbose_name=_('Fiskalni račun'),
    )

    # Iznosi (denormalizirani za brzinu)
    subtotal   = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Iznos bez PDV'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('PDV'))
    total      = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Ukupno'))
    discount   = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Popust'))
    consumption_tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Porez na potrošnju'),
        help_text=_('Lokalni porez na ugostiteljske usluge (čl.20 ZLP). Osnovica = prihod bez PDV-a.'))

    status     = models.CharField(max_length=15, choices=Status.choices,
                                   default=Status.OPEN, verbose_name=_('Status'))
    table_number = models.CharField(max_length=20, blank=True, verbose_name=_('Stol / Zona'),
                                     help_text=_('Za ugostiteljstvo: broj stola'))
    note       = models.CharField(max_length=255, blank=True, verbose_name=_('Napomena na bonu'))

    # R1 racun — kupac (B2B poslovna vecera, reprezentacija)
    buyer_oib  = models.CharField(max_length=20, blank=True, verbose_name=_('OIB kupca (R1)'),
        help_text=_('Za R1 racun — OIB tvrtke kupca'))
    buyer_name = models.CharField(max_length=200, blank=True, verbose_name=_('Naziv kupca (R1)'))
    buyer_address = models.CharField(max_length=255, blank=True, verbose_name=_('Adresa kupca'))

    # Clan udruge (membership discount tracking)
    member_name = models.CharField(max_length=200, blank=True, verbose_name=_('Ime clana'),
        help_text=_('Clan udruge koji je ostvario popust'))
    member_clan_id = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Clan ID'),
        help_text=_('FK na udruge.Clan — za audit trail popusta'))
    member_discount_applied = models.DecimalField(max_digits=5, decimal_places=2, default=0,
        verbose_name=_('Primijenjeni clanski popust (%)'))

    is_r1      = models.BooleanField(default=False, verbose_name=_('R1 racun'),
        help_text=_('Racun s podacima kupca — za knjizenje reprezentacije'))

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at        = models.DateTimeField(null=True, blank=True, verbose_name=_('Plaćen u'))
    cancel_reason  = models.CharField(max_length=200, blank=True, verbose_name=_('Razlog storniranja'))

    # Event-sourced storno: negativni bon referencira originalni
    parent_receipt = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='refund_receipts',
        verbose_name=_('Originalni bon (za storno/povrat)'),
    )

    # Audit trail (B-03)
    client_ip      = models.GenericIPAddressField(null=True, blank=True, verbose_name=_('IP adresa'))
    client_ua      = models.CharField(max_length=300, blank=True, verbose_name=_('User Agent'))

    # B-14: Kanal narudzbe
    order_source   = models.CharField(
        max_length=15, blank=True, default='pos',
        choices=[('pos','POS blagajna'), ('qr','QR narudzba'), ('web','Webshop'), ('api','API')],
        verbose_name=_('Kanal narudzbe'),
    )

    # Training bon (HR-P13)
    is_training    = models.BooleanField(default=False, verbose_name=_("Training bon"),
        help_text=_("Bon iz obuke — nema fiskalnu vrijednost"))
    # Multi-cashier: tko je izdao ovaj racun (PIN switch unutar smjene)
    cashier        = models.ForeignKey(
        'pos.POSCashier', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='receipts',
        verbose_name=_('Blagajnik'),
    )

    # Fiskalizacija (FINA CIS)
    zki            = models.CharField(max_length=32, null=True, blank=True,
                                       verbose_name='ZKI (Zaštitni kod izdavatelja)')
    jir            = models.CharField(max_length=40, null=True, blank=True,
                                       verbose_name='JIR (Jedinstveni identifikator računa)')
    fiscal_datetime = models.DateTimeField(null=True, blank=True,
                                            verbose_name='Datum/vrijeme fiskalizacije')
    fiscal_retry_count = models.PositiveSmallIntegerField(default=0,
                                                          verbose_name='Broj pokušaja fiskalizacije')
    fiscal_last_error = models.CharField(max_length=200, blank=True, default='',
                                          verbose_name='Zadnja greška fiskalizacije')

    # TSE / KassenSichV (DE fiskalizacija)
    tse_transaction_number = models.CharField(max_length=50, null=True, blank=True,
                                               verbose_name='TSE Transaktionsnummer')
    tse_signature_counter = models.PositiveIntegerField(null=True, blank=True,
                                                         verbose_name='TSE Signaturzähler')
    tse_hash = models.TextField(blank=True, default='',
                                 verbose_name='TSE Signaturwert (hash)')
    tse_serial_number = models.CharField(max_length=100, blank=True, default='',
                                          verbose_name='TSE Seriennummer')
    tse_start_time = models.DateTimeField(null=True, blank=True, verbose_name='TSE Start')
    tse_end_time = models.DateTimeField(null=True, blank=True, verbose_name='TSE Ende')
    tse_error = models.CharField(max_length=200, blank=True, default='', verbose_name='TSE greška')

    class Meta:
        verbose_name        = _('POS bon / račun')
        verbose_name_plural = _('POS bonovi / računi')
        unique_together     = [('session', 'receipt_number')]
        ordering            = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.global_number:
            from django.db.models import Max
            from django.db import transaction as _tx
            company = self.session.terminal.company
            # Atomic global_number: lock company row to serialize (race condition fix)
            with _tx.atomic():
                from companies.models import Company
                Company.objects.select_for_update().filter(pk=company.pk).first()
                last = POSReceipt.objects.filter(
                    session__terminal__company=company
                ).aggregate(m=Max('global_number'))['m'] or 0
                self.global_number = last + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Bon #{self.global_number or self.receipt_number} – {self.total} EUR ({self.get_status_display()})'

    def recalculate(self):
        """Reizračunaj iznose iz stavki — Decimal.quantize(ROUND_HALF_UP)."""
        _Q = Decimal('0.01')
        items = self.items.all()
        self.subtotal = sum(
            (i.quantity * i.unit_price * (1 - i.discount_percent / 100)).quantize(_Q, rounding=ROUND_HALF_UP)
            for i in items
        ) or Decimal('0')
        self.tax_amount = sum(
            (i.quantity * i.unit_price * (1 - i.discount_percent / 100) * (i.tax_rate / 100)).quantize(_Q, rounding=ROUND_HALF_UP)
            for i in items
        ) or Decimal('0')
        self.total = (self.subtotal + self.tax_amount - self.discount).quantize(_Q, rounding=ROUND_HALF_UP)
        return self

    @property
    def chain_link_safe(self):
        """Safe accessor za hash chain link — vraca None umjesto DoesNotExist."""
        try:
            return self.chain_link
        except Exception:
            return None


class POSReceiptItem(models.Model):
    """
    Stavka na bonu — artikl skeniran barkodom ili dodan ručno.
    """
    receipt        = models.ForeignKey(POSReceipt, on_delete=models.CASCADE,
                                        related_name='items', verbose_name=_('Bon'))
    # Direktna veza na artikl iz zalihe (via barcode scan)
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pos_items',
        verbose_name=_('Artikl (zaliha)'),
    )
    barcode        = models.CharField(max_length=100, blank=True, verbose_name=_('Barkod'),
                                       help_text=_('Uneseno skeniranjem'))
    description    = models.CharField(max_length=255, verbose_name=_('Naziv artikla'))
    quantity       = models.DecimalField(max_digits=10, decimal_places=3, default=1, verbose_name=_('Količina'))
    unit           = models.CharField(max_length=20, default='kom', verbose_name=_('Jed.mjera'))
    unit_price     = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Cijena bez PDV'))
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name=_('Popust %'))
    tax_rate       = models.DecimalField(max_digits=5, decimal_places=2, default=25, verbose_name=_('PDV %'))
    tax_rate_obj   = models.ForeignKey(
        'companies.TaxRate', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_('PDV stopa'),
    )

    # ── DSFinV-K flags (auto-set from InventoryItem ili rucno) ────────────
    is_pfand_return = models.BooleanField(
        default=False,
        verbose_name=_("Povrat Pfanda"),
        help_text=_("Negativan iznos — DSFinV-K GV_TYP=Pfandrueckzahlung"),
    )
    is_tip = models.BooleanField(
        default=False,
        verbose_name=_("Napojnica"),
        help_text=_("DSFinV-K GV_TYP=TrinkgeldAN ili TrinkgeldAG"),
    )
    is_tip_employer = models.BooleanField(
        default=False,
        verbose_name=_("Napojnica vlasnika (AG)"),
    )
    is_nonprofit_activity = models.BooleanField(
        default=False,
        verbose_name=_("Neprofitna djelatnost"),
        help_text=_("Clanarina/donacija — ne fiskalizira se"),
    )

    # LOT slijedivost (EU 178/2002, Zakon o sigurnosti hrane)
    stock_batch = models.ForeignKey(
        'inventory.StockBatch', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pos_items',
        verbose_name=_('Sarza (LOT)'),
    )
    lot_number = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name=_('LOT broj'),
        help_text=_('Denormalizirano — trajno na bonu cak i ako se sarza obrise'),
    )
    expiry_date = models.DateField(
        null=True, blank=True,
        verbose_name=_('Rok trajanja'),
    )

    total_price    = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          verbose_name=_('Ukupno s PDV'))

    class Meta:
        verbose_name        = _('Stavka bona')
        verbose_name_plural = _('Stavke bona')

    def __str__(self):
        return f'{self.description} x{self.quantity} = {self.total_price}'

    def save(self, *args, **kwargs):
        if self.tax_rate_obj_id:
            self.tax_rate = self.tax_rate_obj.rate
        if self.inventory_item_id and self.inventory_item:
            if not self.description:
                self.description = self.inventory_item.name
            if not self.barcode:
                self.barcode = self.inventory_item.barcode
        net = Decimal(str(self.quantity)) * Decimal(str(self.unit_price)) * (
            1 - Decimal(str(self.discount_percent)) / 100
        )
        self.total_price = (net * (1 + Decimal(str(self.tax_rate)) / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)


class POSPaymentLine(models.Model):
    """
    Kako je plaćen bon — podržava split plaćanja (npr. 20€ gotovina + 30€ kartica).
    """
    class Method(models.TextChoices):
        CASH       = 'CASH',       _('Gotovina')
        CARD       = 'CARD',       _('Kartica')
        MOBILE     = 'MOBILE',     _('Mobilno plaćanje (mPOS)')
        VOUCHER    = 'VOUCHER',    _('Bon / Voucher')
        ACCOUNT    = 'ACCOUNT',    _('Na račun (klijent)')
        CRYPTO     = 'CRYPTO',     _('Kriptovalute')
        REVOLUT    = 'REVOLUT',    _('Revolut')
        AIRCASH    = 'AIRCASH',    _('Aircash')

    receipt        = models.ForeignKey(POSReceipt, on_delete=models.CASCADE,
                                        related_name='payment_lines', verbose_name=_('Bon'))
    method         = models.CharField(max_length=12, choices=Method.choices, verbose_name=_('Način plaćanja'))
    amount         = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Iznos'))
    change_given   = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          verbose_name=_('Vraćeno kusur'))
    card_reference = models.CharField(max_length=100, blank=True,
                                       verbose_name=_('Referenca kartice / autorizacijski kod'))
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Linija plaćanja')
        verbose_name_plural = _('Linije plaćanja')

    def __str__(self):
        return f'{self.get_method_display()} {self.amount} EUR'


# ── POS POSTAVKE & BLAGAJNICI ─────────────────────────────────────────────────

class POSSettings(models.Model):
    """Postavke POS sustava po tvrtki (pisač, fiskalizacija)."""
    PRINTER_TYPES = [
        ('thermal_usb', 'Termalni USB'),
        ('thermal_net', 'Termalni mrežni (ESC/POS)'),
        ('a4',          'A4 pisač'),
    ]
    company      = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='pos_settings', verbose_name=_('Tvrtka'),
    )
    # Printer
    printer_type = models.CharField(
        max_length=15, choices=PRINTER_TYPES, default='thermal_usb',
        verbose_name=_('Tip pisača'),
    )
    printer_ip   = models.CharField(max_length=50, blank=True, verbose_name=_('IP adresa pisača'))
    printer_port = models.IntegerField(default=9100, verbose_name=_('Port'))
    # Fiscal
    fiscal_cert          = models.FileField(
        upload_to='pos/certs/', null=True, blank=True,
        verbose_name=_('Fiskalni certifikat (.p12)'),
    )
    fiscal_cert_password = models.CharField(
        max_length=255, blank=True, verbose_name=_('Lozinka certifikata'),
    )
    fiscal_oib    = models.CharField(max_length=11, blank=True, verbose_name=_('OIB tvrtke'))
    fiscal_active = models.BooleanField(default=False, verbose_name=_('Fiskalizacija aktivna'))

    # ── BEZ PAPIRA — Delivery opcije ─────────────────────────────────────
    DELIVERY_CHOICES = [
        ('thermal', 'Termalni ispis (80mm)'),
        ('a4',      'A4 ispis'),
        ('email',   'Email račun'),
        ('whatsapp', 'WhatsApp račun'),
        ('qr',      'QR kod na stolu (gost skenira)'),
        ('none',    'Bez ispisa (BEZ PAPIRA)'),
    ]
    receipt_delivery = models.CharField(
        max_length=12, choices=DELIVERY_CHOICES, default='thermal',
        verbose_name=_('Dostava računa'),
        help_text=_('Kako se račun dostavlja gostu nakon naplate'),
    )
    # Opcija: auto-print ili samo na zahtjev
    auto_print = models.BooleanField(
        default=True, verbose_name=_('Auto ispis'),
        help_text=_('Automatski ispiši nakon naplate (false = ispis samo na gumb)'),
    )
    # ESC/POS drawer kick
    drawer_kick = models.BooleanField(
        default=False, verbose_name=_('Otvori ladicu'),
        help_text=_('Pošalji ESC/POS komandu za otvaranje ladice za novac'),
    )
    # WhatsApp
    whatsapp_default_msg = models.CharField(
        max_length=200, blank=True, default='Hvala na posjetu! Evo Vas racun:',
        verbose_name=_('WhatsApp poruka'),
    )
    # Email
    receipt_email_subject = models.CharField(
        max_length=100, blank=True, default='Vas racun - {company}',
        verbose_name=_('Email subject'),
    )
    # Blagajnički izvještaj
    use_cashier_report = models.BooleanField(
        default=True, verbose_name=_('Koristi blagajnički izvještaj'),
        help_text=_('Generiraj detaljan blagajnički izvještaj na kraju smjene'),
    )
    cashier_report_ai_check = models.BooleanField(
        default=True, verbose_name=_('AI kontrola izvještaja'),
        help_text=_('AI provjerava anomalije, razlike, sumnjive transakcije'),
    )
    auto_print_zreport = models.BooleanField(
        default=False, verbose_name=_('Auto-print Z-reporta'),
        help_text=_('Automatski printaj Z-report pri zatvaranju smjene'),
    )
    # ── POCKET MODE — Mobitel = blagajna ─────────────────────────────────
    pocket_mode = models.BooleanField(
        default=False, verbose_name=_('Pocket Mode'),
        help_text=_(
            'Mobitel kao jedini uređaj. Auto: digital receipt, '
            'bez printera, pokretna prodaja, offline-first.'
        ),
    )
    pocket_location_label = models.CharField(
        max_length=100, blank=True, default='POKRETNA PRODAJA',
        verbose_name=_('Oznaka prostora (fiskalizacija)'),
        help_text=_('Za čl.28a Zakona o fiskalizaciji'),
    )


    # ── POREZ NA POTROŠNJU (Zakon o lokalnim porezima, NN 115/16) ────────
    consumption_tax_active = models.BooleanField(
        default=False, verbose_name=_('Porez na potrošnju aktivan'),
        help_text=_('Lokalni porez za ugostiteljske usluge. JLS propisuje stopu do 3%.'),
    )
    consumption_tax_rate = models.DecimalField(
        max_digits=4, decimal_places=2, default=3,
        verbose_name=_('Stopa poreza na potrošnju (%)'),
        help_text=_('Najčešće 3% — provjeriti odluku JLS-a (općina/grad).'),
    )
    consumption_tax_jls_name = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name=_('Naziv JLS-a'),
        help_text=_('Općina/grad kojoj se uplaćuje porez (za PP-MI-PO).'),
    )
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('POS postavke')
        verbose_name_plural = _('POS postavke')

    def __str__(self):
        return f'POS postavke – {self.company}'


class POSCashier(models.Model):
    """Blagajnik s PIN kodom i dozvolama."""
    company      = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='pos_cashiers', verbose_name=_('Tvrtka'),
    )
    name         = models.CharField(max_length=100, verbose_name=_('Ime blagajnika'))
    pin_hash     = models.CharField(max_length=64, blank=True, verbose_name=_('PIN hash'))
    can_void     = models.BooleanField(default=False, verbose_name=_('Može stornirati'))
    can_discount = models.BooleanField(default=False, verbose_name=_('Može davati popust'))
    max_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name=_('Max popust (%)'),
    )
    oib          = models.CharField(max_length=20, blank=True, default='',
                     verbose_name=_('OIB operatera'),
                     help_text=_('Zakonski obavezno za fiskalizaciju (čl. 9. Zakona o fiskalizaciji)'))
    is_active    = models.BooleanField(default=True, verbose_name=_('Aktivan'))
    user         = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pos_cashier_profiles',
        verbose_name=_('Django korisnik'),
        help_text=_('Povezani korisnik za evidenciju radnog vremena'),
    )
    clock_in_at  = models.DateTimeField(null=True, blank=True, verbose_name=_('Prijava u'))
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('POS blagajnik')
        verbose_name_plural = _('POS blagajnici')
        ordering            = ['name']

    def __str__(self):
        return self.name

    def set_pin(self, pin_str):
        import hashlib, secrets
        salt = secrets.token_hex(4)  # 8 hex chars
        dk = hashlib.pbkdf2_hmac('sha256', pin_str.strip().encode(), salt.encode(), 150_000)
        # Format: p$8salt$24hash = ~36 chars (fits varchar 64)
        self.pin_hash = 'p$%s$%s' % (salt, dk.hex()[:24])

    def check_pin(self, pin_str):
        import hashlib
        pin_str = pin_str.strip()
        if not self.pin_hash:
            return False
        # Backward compat: stari SHA256 hash (64 hex chars, no $)
        if '$' not in self.pin_hash:
            if self.pin_hash == hashlib.sha256(pin_str.encode()).hexdigest():
                # Auto-upgrade to PBKDF2
                self.set_pin(pin_str)
                self.save(update_fields=['pin_hash'])
                return True
            return False
        # Novi PBKDF2 format: p$salt$hash
        parts = self.pin_hash.split('$')
        if len(parts) != 3:
            return False
        _, salt, stored_hash = parts
        dk = hashlib.pbkdf2_hmac('sha256', pin_str.encode(), salt.encode(), 150_000)
        return dk.hex()[:24] == stored_hash


# ══════════════════════════════════════════════════════════════════════════════
# GASTRO POS — Stolovi, narudzbe, kuhinja
# ══════════════════════════════════════════════════════════════════════════════

class Table(models.Model):
    TABLE_TYPES = [
        ('table', _('Stol')),
        ('bar', _('Sank')),
        ('terrace', _('Terasa')),
        ('room', _('Soba')),
        ('vip', _('VIP')),
    ]
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='gastro_tables', verbose_name=_('Tvrtka'),
    )
    objects = CompanyManager()
    branch = models.ForeignKey(
        'companies.CompanyBranch', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='gastro_tables',
        verbose_name=_('Podruznica'),
    )
    name = models.CharField(max_length=50, verbose_name=_('Naziv'))
    table_type = models.CharField(
        max_length=15, choices=TABLE_TYPES, default='table',
        verbose_name=_('Tip'),
    )
    capacity = models.PositiveIntegerField(default=4, verbose_name=_('Kapacitet'))
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivan'))
    is_occupied = models.BooleanField(default=False, verbose_name=_('Zauzet'))
    qr_code = models.CharField(
        max_length=64, unique=True, blank=True,
        verbose_name=_('QR kod'),
    )
    floor = models.CharField(max_length=30, blank=True, verbose_name=_('Kat / Zona'))

    class Meta:
        verbose_name = _('Stol')
        verbose_name_plural = _('Stolovi')
        ordering = ['floor', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_table_type_display()})'

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.qr_code = uuid.uuid4().hex[:16]
        super().save(*args, **kwargs)


class GastroOrder(models.Model):
    STATUS_CHOICES = [
        ('new', _('Nova')),
        ('confirmed', _('Potvrdena')),
        ('preparing', _('U pripremi')),
        ('ready', _('Gotovo')),
        ('delivering', _('Na putu')),
        ('delivered', _('Dostavljeno')),
        ('paid', _('Placeno')),
        ('cancelled', _('Otkazano')),
    ]
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='gastro_orders', verbose_name=_('Tvrtka'),
    )
    objects = CompanyManager()
    table = models.ForeignKey(
        'pos.Table', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders',
        verbose_name=_('Stol'),
    )
    receipt = models.ForeignKey(
        'pos.POSReceipt', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='gastro_orders',
        verbose_name=_('POS Bon'),
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='new',
        verbose_name=_('Status'),
    )
    guest_name = models.CharField(max_length=100, blank=True, verbose_name=_('Ime gosta'))
    guest_phone = models.CharField(max_length=30, blank=True, verbose_name=_('Telefon'))
    guest_email = models.EmailField(blank=True, verbose_name=_('Email gosta'))
    claimed_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='claimed_orders',
        verbose_name=_('Preuzeo konobar'),
    )
    claimed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Vrijeme preuzimanja'))
    delivered_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='delivered_orders',
        verbose_name=_('Dostavio konobar'),
    )
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Vrijeme dostave'))
    notes = models.TextField(blank=True, verbose_name=_('Napomene'))
    tracking_token = models.CharField(
        max_length=32, unique=True, blank=True,
        verbose_name=_('Token pracenja'),
    )
    estimated_ready_time = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Predvideno vrijeme'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Gastro narudzba')
        verbose_name_plural = _('Gastro narudzbe')
        ordering = ['-created_at']

    def __str__(self):
        tbl = self.table.name if self.table else 'N/A'
        return f'Narudzba #{self.pk} - {tbl} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        if not self.tracking_token:
            self.tracking_token = uuid.uuid4().hex[:32]
        super().save(*args, **kwargs)


class GastroOrderItem(models.Model):
    order = models.ForeignKey(
        GastroOrder, on_delete=models.CASCADE,
        related_name='items', verbose_name=_('Narudzba'),
    )
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='gastro_order_items',
        verbose_name=_('Artikl'),
    )
    quantity = models.DecimalField(
        max_digits=10, decimal_places=3, default=1,
        verbose_name=_('Kolicina'),
    )
    notes = models.CharField(max_length=255, blank=True, verbose_name=_('Napomene'))
    is_ready = models.BooleanField(default=False, verbose_name=_('Spremno'))

    class Meta:
        verbose_name = _('Stavka narudzbe')
        verbose_name_plural = _('Stavke narudzbe')

    def __str__(self):
        name = self.inventory_item.name if self.inventory_item else 'N/A'
        return f'{name} x{self.quantity}'


# ══════════════════════════════════════════════════════════════════════════════

# ======================================================================
# GUEST LOYALTY - Digital stamp card
# ======================================================================

class LoyaltyProgram(models.Model):
    PROGRAM_TYPES = [
        ('stamp', _('Stamp Card')),
        ('discount', _('Popust')),
        ('combo', _('Combo Deal')),
    ]
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='loyalty_programs', verbose_name=_('Tvrtka'),
    )
    objects = CompanyManager()
    name = models.CharField(max_length=100, verbose_name=_('Naziv'))
    program_type = models.CharField(max_length=15, choices=PROGRAM_TYPES, default='stamp')
    stamps_required = models.IntegerField(default=5, verbose_name=_('Potrebno pecata'))
    reward_description = models.CharField(max_length=200, blank=True, verbose_name=_('Opis nagrade'))
    applicable_category = models.CharField(max_length=20, blank=True, verbose_name=_('Kategorija'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Program lojalnosti')
        verbose_name_plural = _('Programi lojalnosti')

    def __str__(self):
        return f'{self.name} ({self.stamps_required}x)'


class GuestLoyalty(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='guest_loyalties', verbose_name=_('Tvrtka'),
    )
    objects = CompanyManager()
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.CASCADE, related_name='entries')
    guest_email = models.EmailField(verbose_name=_('Email gosta'))
    guest_name = models.CharField(max_length=100, blank=True)
    stamps = models.IntegerField(default=0, verbose_name=_('Pecati'))
    rewards_claimed = models.IntegerField(default=0, verbose_name=_('Nagrade iskoristene'))
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_visit = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'program', 'guest_email')
        verbose_name = _('Lojalnost gosta')
        verbose_name_plural = _('Lojalnosti gostiju')

    def __str__(self):
        return f'{self.guest_email} - {self.program.name} ({self.stamps}/{self.program.stamps_required})'

    @property
    def has_reward(self):
        return self.stamps >= self.program.stamps_required

    @property
    def stamps_remaining(self):
        return max(0, self.program.stamps_required - self.stamps)


# ======================================================================
# WAITER SHIFTS & HEARTBEAT
# ======================================================================

class WaiterShift(models.Model):
    """Tracks waiter shifts with heartbeat pings every 5 min."""
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE,
        related_name='waiter_shifts', verbose_name=_('Konobar'),
    )
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='waiter_shifts', verbose_name=_('Tvrtka'),
    )
    objects = CompanyManager()
    started_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Pocetak smjene'))
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Kraj smjene'))
    last_heartbeat = models.DateTimeField(auto_now_add=True, verbose_name=_('Zadnji ping'))
    heartbeat_count = models.IntegerField(default=0, verbose_name=_('Broj pingova'))
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivna'))
    total_orders_claimed = models.IntegerField(default=0)
    total_orders_delivered = models.IntegerField(default=0)

    class Meta:
        verbose_name = _('Smjena konobara')
        verbose_name_plural = _('Smjene konobara')
        ordering = ['-started_at']

    def __str__(self):
        name = self.user.get_full_name() or self.user.username
        return f'{name} - {self.started_at:%d.%m. %H:%M}'

    @property
    def duration_minutes(self):
        from django.utils import timezone
        end = self.ended_at or timezone.now()
        return int((end - self.started_at).total_seconds() / 60)

    @property
    def duration_display(self):
        mins = self.duration_minutes
        h, m = divmod(mins, 60)
        return f'{h}h {m:02d}min'

    @property
    def is_heartbeat_stale(self):
        from django.utils import timezone
        if not self.is_active:
            return False
        return (timezone.now() - self.last_heartbeat).total_seconds() > 600  # 10 min = 2 missed


# EXPIRY TRACKING — Rokovi trajanja artikala
# ══════════════════════════════════════════════════════════════════════════════

class ExpiryBatch(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='expiry_batches', verbose_name=_('Tvrtka'),
    )
    objects = CompanyManager()
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.CASCADE,
        related_name='expiry_batches', verbose_name=_('Artikl'),
    )
    batch_number = models.CharField(max_length=100, blank=True, verbose_name=_('Broj sarze'))
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Kolicina'),
    )
    expiry_date = models.DateField(verbose_name=_('Datum isteka'))
    alert_days_before = models.PositiveIntegerField(
        default=3, verbose_name=_('Upozorenje dana prije'),
    )
    is_removed = models.BooleanField(default=False, verbose_name=_('Uklonjeno'))

    class Meta:
        verbose_name = _('Sarzni rok')
        verbose_name_plural = _('Sarzni rokovi')
        ordering = ['expiry_date']

    def __str__(self):
        return f'{self.inventory_item.name} - {self.batch_number} (exp: {self.expiry_date})'

    @property
    def days_until_expiry(self):
        from datetime import date
        return (self.expiry_date - date.today()).days

    @property
    def is_expired(self):
        return self.days_until_expiry < 0

    @property
    def is_warning(self):
        d = self.days_until_expiry
        return 0 <= d <= self.alert_days_before




# ══════════════════════════════════════════════════════════════════════════════
# VAUČERI / BONOVI
# ══════════════════════════════════════════════════════════════════════════════

class Voucher(models.Model):
    """Vaučer / Bon s određenom vrijednosti koji se koristi kao metoda plaćanja."""
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='vouchers', verbose_name=_('Tvrtka'),
    )
    objects = CompanyManager()
    # Tip vaucera: odredjuje PDV tretman pri prodaji
    VOUCHER_TYPE_CHOICES = [
        ('multi', 'Visenamjenski (Mehrzweck) — bez PDV pri prodaji'),
        ('single', 'Jednonamjenski (Einzweck) — s PDV pri prodaji'),
    ]
    voucher_type = models.CharField(
        max_length=15, choices=VOUCHER_TYPE_CHOICES, default='multi',
        verbose_name=_('Tip vaucera'),
        help_text=_('Visenamjenski = obveza pri prodaji (bez PDV). Jednonamjenski = prihod s PDV.'),
    )
    # Konto knjizenje
    is_sold = models.BooleanField(default=False, verbose_name=_('Prodan'),
        help_text=_('True = kreiran prodajom na POS-u'))
    sold_receipt = models.ForeignKey(
        'pos.POSReceipt', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sold_vouchers', verbose_name=_('Bon prodaje'),
    )
    code            = models.CharField(max_length=20, unique=True, verbose_name=_('Kod vaučera'))
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Izvorna vrijednost (€)'))
    remaining       = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Preostalo (€)'))
    expiry_date     = models.DateField(null=True, blank=True, verbose_name=_('Rok valjanosti'))
    is_active       = models.BooleanField(default=True, verbose_name=_('Aktivan'))
    notes           = models.CharField(max_length=200, blank=True, verbose_name=_('Napomena'))
    created_by      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_vouchers', verbose_name=_('Kreirao'),
    )
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Vaučer')
        verbose_name_plural = _('Vaučeri')
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.code} — {self.remaining}/{self.original_amount} EUR'

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        from datetime import date
        return self.expiry_date < date.today()

    @property
    def is_usable(self):
        return self.is_active and not self.is_expired and self.remaining > 0

class CashDeposit(models.Model):
    """Polog gotovine u blagajnu (međupolog tijekom smjene)."""
    DEPOSIT_TYPES = [
        ('deposit',    _('Polog')),
        ('withdrawal', _('Isplata')),
    ]

    session     = models.ForeignKey(
        POSSession, on_delete=models.CASCADE,
        related_name='cash_deposits', verbose_name=_('Smjena'),
    )
    operator    = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='cash_deposits', verbose_name=_('Operater'),
    )
    deposit_type = models.CharField(
        max_length=15, choices=DEPOSIT_TYPES, default='deposit',
        verbose_name=_('Vrsta'),
    )
    amount      = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name=_('Iznos (€)'),
    )
    note        = models.CharField(max_length=200, blank=True, verbose_name=_('Napomena'))
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Polog/Isplata')
        verbose_name_plural = _('Polozi/Isplate')
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.get_deposit_type_display()} {self.amount} EUR — smjena #{self.session.session_number}'


class GastroReview(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    order = models.OneToOneField('GastroOrder', on_delete=models.CASCADE, related_name='review')
    guest_name = models.CharField(max_length=100)
    guest_email = models.EmailField(blank=True)
    rating = models.PositiveSmallIntegerField()  # 1-5
    comment = models.TextField(blank=True)
    food_rating = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-5
    service_rating = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-5
    ambience_rating = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-5
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return "{} - {} zvjezdica".format(self.guest_name, self.rating)


# ═══════════════════════════════════════════════════════════════
# POSDailyReport — Trajno spremanje dnevnih utržaka
# ═══════════════════════════════════════════════════════════════

class POSDailyReport(models.Model):
    """
    Agregirani dnevni izvještaj blagajne.
    Auto-generira se na zatvaranju sesije.
    Sprema sve ukupne iznose umjesto on-the-fly izračuna.
    """
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='pos_daily_reports', verbose_name=_('Tvrtka'),
    )
    terminal = models.ForeignKey(
        POSTerminal, on_delete=models.CASCADE,
        related_name='daily_reports', verbose_name=_('Terminal'),
    )
    session = models.OneToOneField(
        POSSession, on_delete=models.CASCADE,
        related_name='daily_report', verbose_name=_('Smjena'),
    )
    date = models.DateField(verbose_name=_('Datum'))
    # Ukupni iznosi
    total_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name=_('Ukupan promet'),
    )
    cash_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name=_('Gotovina'),
    )
    card_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name=_('Kartica'),
    )
    mobile_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name=_('Mobilno plaćanje'),
    )
    voucher_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name=_('Vaučeri'),
    )
    account_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name=_('Na račun'),
    )
    # Brojevi
    receipt_count = models.PositiveIntegerField(default=0, verbose_name=_('Broj računa'))
    cancelled_count = models.PositiveIntegerField(default=0, verbose_name=_('Stornirani'))
    # Prosjek
    average_ticket = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name=_('Prosječan račun'),
    )
    # Gotovina
    opening_cash = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name=_('Početna gotovina'),
    )
    closing_cash = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name=_('Završna gotovina'),
    )
    cash_difference = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name=_('Razlika gotovine'),
    )
    # Detaljni breakdowni
    tax_breakdown = models.JSONField(
        default=dict, blank=True, verbose_name=_('PDV razrada'),
        help_text=_('{"25.00": {"base": 100, "tax": 25, "total": 125}, ...}'),
    )
    consumption_tax_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Porez na potrošnju ukupno'),
    )
    cashier_breakdown = models.JSONField(
        default=dict, blank=True, verbose_name=_('Po blagajnicima'),
        help_text=_('{"Ana": {"count": 10, "total": 500}, ...}'),
    )
    # ── Marketplace / Online prodaja ──
    marketplace_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name=_('Marketplace promet'),
        help_text=_('Ukupan promet od online tržnice za ovaj dan'),
    )
    marketplace_order_count = models.PositiveIntegerField(
        default=0, verbose_name=_('Marketplace narudžbe'),
    )
    gastro_bridge_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name=_('Gastro Bridge promet'),
        help_text=_('Promet od Last Call prebacivanja'),
    )
    # Z-report PDF
    z_report_pdf = models.FileField(
        upload_to='pos/zreports/%Y/%m/', blank=True,
        verbose_name=_('Z-report PDF'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Dnevni izvještaj POS')
        verbose_name_plural = _('Dnevni izvještaji POS')
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['company', 'date']),
            models.Index(fields=['terminal', 'date']),
        ]

    def __str__(self):
        return '%s — %s — %s EUR' % (self.date, self.terminal.name, self.total_revenue)

    @classmethod
    def generate_from_session(cls, session):
        """Generiraj dnevni izvještaj iz zatvorene sesije."""
        from decimal import Decimal
        from django.db.models import Sum, Count, Q

        receipts = session.receipts.filter(status='paid')
        cancelled = session.receipts.filter(status='cancelled').count()

        # Payment breakdown
        from pos.models import POSPaymentLine
        payment_qs = POSPaymentLine.objects.filter(receipt__session=session, receipt__status='paid')
        cash = payment_qs.filter(method='CASH').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        card = payment_qs.filter(method='CARD').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        mobile = payment_qs.filter(method='MOBILE').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        voucher = payment_qs.filter(method='VOUCHER').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        account = payment_qs.filter(method='ACCOUNT').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        total = cash + card + mobile + voucher + account
        count = receipts.count()

        # Tax breakdown
        from pos.models import POSReceiptItem
        tax_items = POSReceiptItem.objects.filter(receipt__session=session, receipt__status='paid')
        tax_bd = {}
        for item in tax_items:
            rate_key = str(item.tax_rate)
            if rate_key not in tax_bd:
                tax_bd[rate_key] = {'base': 0, 'tax': 0, 'total': 0}
            net = float(item.total_price / (1 + item.tax_rate / 100)) if item.tax_rate else float(item.total_price)
            tax_amount = float(item.total_price) - net
            tax_bd[rate_key]['base'] = Decimal(str(tax_bd[rate_key]['base'] + net)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            tax_bd[rate_key]['tax'] = Decimal(str(tax_bd[rate_key]['tax'] + tax_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            tax_bd[rate_key]['total'] = Decimal(str(tax_bd[rate_key]['total'] + float(item.total_price))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Cashier breakdown (s napojnicama per NN 156/2023)
        cashier_bd = {}
        for r in receipts.select_related('cashier').prefetch_related('items'):
            name = r.cashier.name if r.cashier else r.note or 'Nepoznat'
            if name not in cashier_bd:
                cashier_bd[name] = {'count': 0, 'total': 0, 'tips': 0}
            cashier_bd[name]['count'] += 1
            cashier_bd[name]['total'] = round(cashier_bd[name]['total'] + float(r.total), 2)
            # Napojnice per cashier (samo employee tips, ne AG)
            tip_sum = sum(
                float(item.unit_price * item.quantity)
                for item in r.items.all()
                if item.is_tip and not item.is_tip_employer
            )
            cashier_bd[name]['tips'] = round(cashier_bd[name].get('tips', 0) + tip_sum, 2)

        report, created = cls.objects.update_or_create(
            session=session,
            defaults={
                'company': session.terminal.company,
                'terminal': session.terminal,
                'date': (session.closed_at or session.opened_at).date(),
                'total_revenue': total,
                'cash_total': cash,
                'card_total': card,
                'mobile_total': mobile,
                'voucher_total': voucher,
                'account_total': account,
                'receipt_count': count,
                'cancelled_count': cancelled,
                'average_ticket': round(total / count, 2) if count else Decimal('0'),
                'opening_cash': session.opening_cash,
                'closing_cash': session.closing_cash or Decimal('0'),
                'cash_difference': (session.closing_cash or Decimal('0')) - session.expected_closing_cash,
                'tax_breakdown': tax_bd,
                'cashier_breakdown': cashier_bd,
                'consumption_tax_total': receipts.aggregate(ct=Sum('consumption_tax_amount'))['ct'] or Decimal('0'),
            },
        )

        # Sprint 1F: Auto-generate Z-report PDF
        if not report.z_report_pdf:
            try:
                from pos.pdf_service import generate_z_report_pdf
                from django.core.files.base import ContentFile
                pdf_bytes = generate_z_report_pdf(report)
                report.z_report_pdf.save(
                    'z_report_%s_%s.pdf' % (report.terminal.terminal_code, report.date),
                    ContentFile(pdf_bytes),
                    save=True,
                )
            except Exception as e:
                import logging
                logging.getLogger('pos').warning('Z-report PDF failed: %s', e)

        return report



# ═══════════════════════════════════════════════════════════════
# ImprovementSuggestion — Knjiga boljitaka
# ═══════════════════════════════════════════════════════════════

class ImprovementSuggestion(models.Model):
    """Dinamicka knjiga boljitaka — zaposlenici i sustav predlazu poboljsanja."""
    class Status(models.TextChoices):
        NEW        = 'new',        _('Novo')
        REVIEWED   = 'reviewed',   _('Pregledano')
        ACCEPTED   = 'accepted',   _('Prihvaceno')
        DONE       = 'done',       _('Rijeseno')
        REJECTED   = 'rejected',   _('Odbijeno')

    class Source(models.TextChoices):
        USER       = 'user',       _('Korisnik')
        SYSTEM     = 'system',     _('Sustav (AI)')
        ANONYMOUS  = 'anonymous',  _('Anonimno')

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='improvement_suggestions',
    )
    author = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='improvement_suggestions',
    )
    source = models.CharField(max_length=12, choices=Source.choices, default='user')
    title = models.CharField(max_length=200, verbose_name=_('Naslov'))
    description = models.TextField(verbose_name=_('Opis'))
    category = models.CharField(max_length=50, blank=True, verbose_name=_('Kategorija'),
        help_text=_('pos, inventory, workflow, ux, other'))
    priority = models.PositiveSmallIntegerField(default=3, verbose_name=_('Prioritet'),
        help_text=_('1=kriticno, 5=nice-to-have'))
    status = models.CharField(max_length=12, choices=Status.choices, default='new')
    admin_note = models.TextField(blank=True, verbose_name=_('Biljeska admina'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Prijedlog poboljsanja')
        verbose_name_plural = _('Prijedlozi poboljsanja')
        ordering = ['priority', '-created_at']

    def __str__(self):
        return '[P%d] %s' % (self.priority, self.title)


# ═══════════════════════════════════════════════════════════════
# KnjigaPrigovora — Zakonska evidencija prigovora potrošača
# HR: Zakon o zaštiti potrošača (čl. 10), Zakon o ugostiteljskoj dj.
# Kazne: 1.500 — 3.500 EUR za nepostojanje/neispravnu evidenciju
# ═══════════════════════════════════════════════════════════════

class KnjigaPrigovora(models.Model):
    """
    Knjiga boljitaka — evidencija prijedloga za poboljšanje i utisaka.
    Zakonski mora sadržavati: kronološki r.br., datum primitka,
    opis, odgovor u roku od 15 dana.
    """
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='prigovori', verbose_name=_('Tvrtka'),
    )
    redni_broj = models.PositiveIntegerField(
        verbose_name=_('Redni broj'),
        help_text=_('Auto-inkrement po tvrtki'),
    )
    datum_primitka = models.DateField(
        auto_now_add=True, verbose_name=_('Datum primitka'),
    )
    ime_potrosaca = models.CharField(
        max_length=200, verbose_name=_('Ime i prezime potrošača'),
    )
    kontakt = models.CharField(
        max_length=200, blank=True, verbose_name=_('Adresa ili e-mail'),
    )
    opis_prigovora = models.TextField(verbose_name=_('Vaš prijedlog'))
    odgovor = models.TextField(blank=True, verbose_name=_('Odgovor'))
    datum_odgovora = models.DateField(
        null=True, blank=True, verbose_name=_('Datum odgovora'),
    )
    # Verifikacija identiteta
    id_photo = models.TextField(blank=True, verbose_name=_('Slika osobne (base64)'))
    signature = models.TextField(blank=True, verbose_name=_('Potpis potrošača (base64)'))
    voice_input = models.BooleanField(default=False, verbose_name=_('Glasovni unos'))
    audio_recording = models.FileField(
        upload_to='prigovori/audio/%Y/%m/', blank=True, null=True,
        verbose_name=_('Zvučni zapis'),
        help_text=_('WebM/MP3 snimka glasovnog prigovora'),
    )

    # ── Tip zapisa (prigovor / pohvala / utisak / reklamacija) ────────
    RECORD_TYPES = [
        ('prigovor', _('Prijedlog za poboljšanje / Verbesserungsvorschlag')),
        ('pohvala', _('Pohvala / Lob')),
        ('utisak', _('Utisak / Eindruck')),
        ('reklamacija', _('Reklamacija / Reklamation')),
        ('prijedlog', _('Prijedlog poboljšanja / Verbesserungsvorschlag')),
    ]
    record_type = models.CharField(
        max_length=20, choices=RECORD_TYPES, default='prigovor',
        verbose_name=_('Vrsta zapisa'),
    )

    # ── Izvorni modul (globalni pristup) ──────────────────────────────
    SOURCE_MODULES = [
        ('pos', 'POS'),
        ('invoicing', _('Fakturiranje')),
        ('rental', _('Smještaj / Vermietung')),
        ('delivery', _('Dostava / Lieferung')),
        ('marketplace', _('Tržnica / Marktplatz')),
        ('webshop', 'Webshop'),
        ('work_orders', _('Radni nalozi / Aufträge')),
        ('appointments', _('Termini / Termine')),
        ('fitness', 'Fitness'),
        ('gastro', _('Gastronomija / Gastronomie')),
        ('general', _('Općenito / Allgemein')),
        ('qr', _('QR kod (potrošač)')),
    ]
    source_module = models.CharField(
        max_length=20, choices=SOURCE_MODULES, default='pos',
        verbose_name=_('Izvorni modul'),
    )
    source_url = models.URLField(
        blank=True, verbose_name=_('Izvorni URL'),
        help_text=_('URL stranice s koje je prigovor poslan'),
    )

    # ── Ocjena (za utiske / pohvale) ─────────────────────────────────
    star_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_('Ocjena (1-5)'),
        help_text=_('Zvjezdice — samo za pohvale i utiske'),
    )

    # ── Kontakt podaci (prošireni) ───────────────────────────────────
    consumer_email = models.EmailField(
        blank=True, verbose_name=_('E-mail potrošača'),
        help_text=_('Za slanje potvrde i odgovora'),
    )
    consumer_phone = models.CharField(
        max_length=30, blank=True, verbose_name=_('Telefon / WhatsApp'),
    )

    # ── SES metadata bundle (pravna valjanost potpisa) ───────────────
    gps_latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        verbose_name=_('GPS širina'),
    )
    gps_longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        verbose_name=_('GPS dužina'),
    )
    device_info = models.CharField(
        max_length=500, blank=True, verbose_name=_('Uređaj'),
        help_text=_('User-Agent + screen resolution'),
    )
    client_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name=_('IP adresa'),
    )
    signature_timestamp = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Vrijeme potpisa'),
        help_text=_('Točan trenutak kada je potpis stavljen'),
    )

    # ── Odgovor — prošireno ──────────────────────────────────────────
    RESPONSE_CHANNELS = [
        ('email', 'E-mail'),
        ('whatsapp', 'WhatsApp'),
        ('post', _('Pošta / Post')),
        ('phone', _('Telefon / Telefon')),
        ('in_person', _('Osobno / Persönlich')),
    ]
    response_channel = models.CharField(
        max_length=15, blank=True, choices=RESPONSE_CHANNELS,
        verbose_name=_('Kanal odgovora'),
    )
    response_sent_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Odgovor poslan'),
    )
    responded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='responded_prigovori', verbose_name=_('Odgovorio/la'),
    )

    # ── Eskalacija ───────────────────────────────────────────────────
    is_escalated = models.BooleanField(
        default=False, verbose_name=_('Eskalirano'),
    )
    escalated_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Eskalirano u'),
    )
    escalation_reason = models.CharField(
        max_length=200, blank=True, verbose_name=_('Razlog eskalacije'),
    )

    # ── Javna vidljivost (za utiske) ─────────────────────────────────
    is_public = models.BooleanField(
        default=False, verbose_name=_('Javno vidljivo'),
        help_text=_('Prikazuje se na web stranici / widgetu'),
    )
    public_display_name = models.CharField(
        max_length=100, blank=True, verbose_name=_('Ime za prikaz'),
        help_text=_('Npr. "Marko P." umjesto punog imena'),
    )

    # ── Zemlja / jezik ───────────────────────────────────────────────
    LANG_CHOICES = [
        ('hr', 'Hrvatski'),
        ('de', 'Deutsch'),
        ('en', 'English'),
    ]
    language = models.CharField(
        max_length=2, choices=LANG_CHOICES, default='hr',
        verbose_name=_('Jezik / Sprache'),
    )

    # AI analiza (Celery task popunjava automatski)
    ai_category = models.CharField(
        max_length=30, blank=True, verbose_name=_('AI kategorija'),
        choices=[
            ('product_quality', 'Kvaliteta proizvoda'),
            ('service', 'Usluga / Osoblje'),
            ('pricing', 'Cijena / Naplata'),
            ('hygiene', 'Higijena / Čistoća'),
            ('wait_time', 'Vrijeme čekanja'),
            ('delivery', 'Dostava / Isporuka'),
            ('warranty', 'Garancija / Reklamacija'),
            ('safety', 'Sigurnost / Ozljeda'),
            ('other', 'Ostalo'),
        ],
    )
    ai_sentiment = models.CharField(
        max_length=15, blank=True, verbose_name=_('AI sentiment'),
        choices=[
            ('critical', 'Kritično — hitno'),
            ('negative', 'Negativno'),
            ('neutral', 'Neutralno'),
            ('constructive', 'Konstruktivno'),
        ],
    )
    ai_priority = models.PositiveSmallIntegerField(
        default=0, verbose_name=_('AI prioritet (1-5)'),
        help_text=_('0=nije analizirano, 5=najhitnije'),
    )
    ai_suggested_response = models.TextField(
        blank=True, verbose_name=_('AI prijedlog odgovora'),
        help_text=_('Claude generira prijedlog odgovora na hrvatskom'),
    )
    ai_analyzed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('AI analizirano'),
    )

    # Certificirani zapis — SHA256(potpis + tekst + datum + redni_broj)
    integrity_hash = models.CharField(
        max_length=64, blank=True, verbose_name=_('Integritetski hash'),
        help_text=_('SHA256 certifikat — dokaz nepromijenjenosti zapisa'),
    )

    # ── Auto-archive u DocumentBlob ──────────────────────────────────
    archive_blob = models.ForeignKey(
        'documents.DocumentBlob', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='prigovori',
        verbose_name=_('Arhivski PDF'),
        help_text=_('Auto-generirani PDF za zakonsku arhivu'),
    )

    # ── ADR/ODR EU Compliance ────────────────────────────────────────
    adr_offered = models.BooleanField(
        default=False, verbose_name=_('ADR ponudjeno'),
        help_text=_('Da li je potrosac obaviijesten o ADR/mirenju'),
    )

    # ── WhatsApp Opt-in (Meta Business API compliance) ───────────────
    whatsapp_consent = models.BooleanField(
        default=False, verbose_name=_('WhatsApp pristanak'),
        help_text=_('Potrošač eksplicitno pristao na WhatsApp komunikaciju'),
    )

    # ── GDPR Content Moderation (Dron #2) ────────────────────────────
    moderation_passed = models.BooleanField(
        default=False, verbose_name=_('Moderacija prošla'),
        help_text=_('Sadržaj prošao AI + ručnu moderaciju za javni prikaz'),
    )
    moderation_note = models.CharField(
        max_length=500, blank=True, verbose_name=_('Moderacijska napomena'),
        help_text=_('AI/admin razlog odobrenja ili odbijanja javnog prikaza'),
    )

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Evidentirao'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Zapis (boljitci)')
        verbose_name_plural = _('Knjiga boljitaka')
        unique_together = [('company', 'redni_broj')]
        ordering = ['-redni_broj']

    def __str__(self):
        type_label = dict(self.RECORD_TYPES).get(self.record_type, self.record_type)
        return '#%d [%s] — %s (%s)' % (self.redni_broj, type_label, self.ime_potrosaca, self.datum_primitka)

    def save(self, *args, **kwargs):
        if not self.redni_broj:
            last = KnjigaPrigovora.objects.filter(
                company=self.company
            ).order_by('-redni_broj').first()
            self.redni_broj = (last.redni_broj + 1) if last else 1
        # Compute integrity hash on first save (certifikacija)
        if not self.integrity_hash and self.opis_prigovora:
            self.integrity_hash = self._compute_hash()
        super().save(*args, **kwargs)

    def _compute_hash(self):
        import hashlib
        raw = '%s|%s|%s|%s|%s|%s' % (
            self.company_id, self.redni_broj or 0,
            self.datum_primitka or '', self.ime_potrosaca,
            self.opis_prigovora, self.record_type,
        )
        if self.signature:
            raw += '|SIG:' + self.signature[:100]
        if self.gps_latitude and self.gps_longitude:
            raw += '|GPS:%s,%s' % (self.gps_latitude, self.gps_longitude)
        if self.signature_timestamp:
            raw += '|TS:' + str(self.signature_timestamp)
        if self.client_ip:
            raw += '|IP:' + self.client_ip
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def verify_integrity(self):
        return self.integrity_hash == self._compute_hash()

    @property
    def needs_response(self):
        """Samo prigovori i reklamacije zahtijevaju zakonski odgovor."""
        return self.record_type in ('prigovor', 'reklamacija')

    @property
    def legal_deadline_days(self):
        """Zakonski rok ovisi o vrsti i zemlji."""
        if not self.needs_response:
            return None
        # HR: ZZP čl.10 = 15 dana, DE: BGB = 14 dana (Widerrufsfrist)
        lang = self.language or 'hr'
        return 14 if lang == 'de' else 15

    @property
    def rok_istekao(self):
        """Zakonski rok istekao?"""
        if not self.needs_response or self.datum_odgovora:
            return False
        from django.utils import timezone
        deadline = self.legal_deadline_days or 15
        return (timezone.now().date() - self.datum_primitka).days > deadline

    @property
    def dana_do_roka(self):
        """Koliko dana ostalo do zakonskog roka."""
        if not self.needs_response or self.datum_odgovora:
            return None
        from django.utils import timezone
        deadline = self.legal_deadline_days or 15
        return deadline - (timezone.now().date() - self.datum_primitka).days

    @property
    def ses_metadata(self):
        """SES metadata bundle za pravnu valjanost."""
        return {
            'gps': {'lat': float(self.gps_latitude), 'lng': float(self.gps_longitude)} if self.gps_latitude else None,
            'ip': self.client_ip,
            'device': self.device_info,
            'signature_time': self.signature_timestamp.isoformat() if self.signature_timestamp else None,
            'integrity_hash': self.integrity_hash,
            'has_signature': bool(self.signature),
            'has_id_photo': bool(self.id_photo),
        }


# ══════════════════════════════════════════════════════════════════════════════
# POS PULSE — AI Živčani Sustav (anomaly detection, heartbeat, alerts)
# ══════════════════════════════════════════════════════════════════════════════

class POSPulseEvent(models.Model):
    """
    Real-time POS event log — anomaly detection, heartbeat, milestones.
    AI živčani sustav: "Sustav koji diše."
    """
    EVENT_TYPES = [
        ('anomaly_cancel', _('Neobičan storno')),
        ('anomaly_discount', _('Neobičan popust')),
        ('anomaly_cash', _('Cash manjak')),
        ('anomaly_void', _('Masovni storno')),
        ('anomaly_speed', _('Prebrza naplata')),
        ('anomaly_refund', _('Sumnjivi povrat')),
        ('heartbeat', _('Terminal heartbeat')),
        ('alert_stock', _('Kritična zaliha')),
        ('alert_fiscal', _('Fiskalizacija fail')),
        ('milestone_100', _('100. bon danas')),
        ('milestone_revenue', _('Revenue milestone')),
        ('shift_open', _('Smjena otvorena')),
        ('shift_close', _('Smjena zatvorena')),
    ]
    SEVERITY_CHOICES = [
        ('info', _('Info')),
        ('warning', _('Upozorenje')),
        ('critical', _('Kritično')),
        ('success', _('Uspjeh')),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='pulse_events',
    )
    terminal = models.ForeignKey(
        'pos.POSTerminal', on_delete=models.CASCADE,
        related_name='pulse_events', null=True, blank=True,
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES, verbose_name=_('Tip'))
    severity = models.CharField(max_length=15, choices=SEVERITY_CHOICES, default='info')
    title = models.CharField(max_length=200, verbose_name=_('Naslov'))
    detail = models.TextField(blank=True, verbose_name=_('Detalji'))
    metadata = models.JSONField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    notified_whatsapp = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('POS Pulse Event')
        verbose_name_plural = _('POS Pulse Events')
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.severity}] {self.title}'


# Import ChainLink so Django model discovery includes it
from pos.hashchain import ChainLink  # noqa: F401



# ═══════════════════════════════════════════════════════════════
#  Context-Aware QuickActions — POS kao Centar Svijeta
# ═══════════════════════════════════════════════════════════════

# Action Registry — dozvoljene akcije s validacijom
QUICK_ACTION_REGISTRY = {
    # Univerzalne
    'add_item':       {'label': 'Dodaj artikl',     'requires': ['item_sku']},
    'add_amount':     {'label': 'Brzi iznos',        'requires': []},
    'open_url':       {'label': 'Otvori stranicu',   'requires': ['url']},
    'scan_barcode':   {'label': 'Skeniraj barkod',   'requires': []},
    'open_modal':     {'label': 'Otvori modal',      'requires': ['modal_id']},
    # Rental
    'rental_checkin': {'label': 'Check-in gosta',    'requires': []},
    'rental_checkout': {'label': 'Check-out',        'requires': []},
    'rental_evisitor': {'label': 'eVisitor XML',     'requires': []},
    'rental_ocr':     {'label': 'OCR dokument',      'requires': []},
    # Udruga
    'membership_scan': {'label': 'Skeniraj iskaznicu', 'requires': []},
    'membership_renew': {'label': 'Obnovi clanstvo', 'requires': []},
    'donation':       {'label': 'Donacija',          'requires': []},
    # Field
    'whatsapp_receipt': {'label': 'WhatsApp racun',  'requires': []},
    'gps_location':   {'label': 'GPS lokacija',      'requires': []},
    'fenix_camera':   {'label': 'FenixCamera OCR',    'requires': []},
}


def get_default_quick_actions(pos_type, business_type='doo'):
    """
    Generira defaultne brze tipke ovisno o pos_type i business_type.
    Poziva se automatski ako terminal nema konfiguriranih tipki.
    """
    defaults = {
        'quick': [
            {'icon': 'fa-barcode', 'label': 'Barkod', 'action': 'scan_barcode', 'color': '#3b82f6'},
            {'icon': 'fa-calculator', 'label': 'Brzi iznos', 'action': 'add_amount', 'color': '#c9a84c'},
        ],
        'retail': [
            {'icon': 'fa-barcode', 'label': 'Barkod', 'action': 'scan_barcode', 'color': '#3b82f6'},
            {'icon': 'fa-calculator', 'label': 'Brzi iznos', 'action': 'add_amount', 'color': '#c9a84c'},
            {'icon': 'fa-search', 'label': 'Trazi', 'action': 'open_modal', 'modal_id': 'searchModal', 'color': '#6b7280'},
        ],
        'restaurant': [
            {'icon': 'fa-utensils', 'label': 'Stolovi', 'action': 'open_url', 'url': '/pos/gastro/', 'color': '#f59e0b'},
            {'icon': 'fa-clipboard-list', 'label': 'Narudzbe', 'action': 'open_url', 'url': '/pos/gastro/orders/', 'color': '#3b82f6'},
            {'icon': 'fa-calculator', 'label': 'Brzi iznos', 'action': 'add_amount', 'color': '#c9a84c'},
        ],
        'reception': [
            {'icon': 'fa-sign-in-alt', 'label': 'Check-in', 'action': 'rental_checkin', 'color': '#22c55e'},
            {'icon': 'fa-bed', 'label': 'Nocenje', 'action': 'add_item', 'item_sku': 'NOCENJE', 'color': '#3b82f6'},
            {'icon': 'fa-broom', 'label': 'Cistenje', 'action': 'add_item', 'item_sku': 'CLEANING', 'color': '#f59e0b'},
            {'icon': 'fa-receipt', 'label': 'Pristojba', 'action': 'add_item', 'item_sku': 'TOURIST_TAX', 'color': '#8b5cf6'},
            {'icon': 'fa-camera', 'label': 'OCR Gost', 'action': 'rental_ocr', 'color': '#ec4899'},
            {'icon': 'fa-download', 'label': 'eVisitor', 'action': 'rental_evisitor', 'color': '#14b8a6'},
        ],
        'field': [
            {'icon': 'fa-calculator', 'label': 'Brzi iznos', 'action': 'add_amount', 'color': '#c9a84c'},
            {'icon': 'fa-wrench', 'label': 'Usluga', 'action': 'add_item', 'item_sku': 'SERVICE', 'color': '#3b82f6'},
            {'icon': 'fa-map-marker-alt', 'label': 'GPS', 'action': 'gps_location', 'color': '#22c55e'},
            {'icon': 'fa-whatsapp', 'label': 'WhatsApp', 'action': 'whatsapp_receipt', 'color': '#25D366'},
        ],
        'service': [
            {'icon': 'fa-clock', 'label': 'Sat rada', 'action': 'add_item', 'item_sku': 'HOUR', 'color': '#3b82f6'},
            {'icon': 'fa-tools', 'label': 'Materijal', 'action': 'add_item', 'item_sku': 'MATERIAL', 'color': '#f59e0b'},
            {'icon': 'fa-car', 'label': 'Dolazak', 'action': 'add_item', 'item_sku': 'TRAVEL', 'color': '#6b7280'},
            {'icon': 'fa-calculator', 'label': 'Brzi iznos', 'action': 'add_amount', 'color': '#c9a84c'},
        ],
    }

    actions = defaults.get(pos_type, defaults['retail'])

    # Gym override
    if pos_type == 'gym':
        actions = [
            {'icon': 'fa-id-card', 'label': 'Check-in', 'action': 'membership_scan', 'color': '#22c55e'},
            {'icon': 'fa-sync', 'label': 'Članarina', 'action': 'membership_renew', 'color': '#3b82f6'},
            {'icon': 'fa-dumbbell', 'label': 'Trening', 'action': 'add_item', 'item_sku': 'TRENING', 'color': '#8b5cf6'},
            {'icon': 'fa-flask', 'label': 'Suplementi', 'action': 'scan_barcode', 'color': '#f59e0b'},
        ]

    # Appointment override
    if pos_type == 'appointment':
        actions = [
            {'icon': 'fa-calendar-check', 'label': 'Danas', 'action': 'open_url', 'url': '/appointments/today/', 'color': '#22c55e'},
            {'icon': 'fa-user-clock', 'label': 'Check-in', 'action': 'membership_scan', 'color': '#3b82f6'},
            {'icon': 'fa-calculator', 'label': 'Brzi iznos', 'action': 'add_amount', 'color': '#c9a84c'},
            {'icon': 'fa-whatsapp', 'label': 'WhatsApp', 'action': 'whatsapp_receipt', 'color': '#25D366'},
        ]

    # Udruga override — dodaj membership tipke
    if business_type in ('udruga', 'zadruga', 'ustanova'):
        actions = [
            {'icon': 'fa-id-card', 'label': 'Iskaznica', 'action': 'membership_scan', 'color': '#3b82f6'},
            {'icon': 'fa-sync', 'label': 'Clanarina', 'action': 'membership_renew', 'color': '#22c55e'},
            {'icon': 'fa-heart', 'label': 'Donacija', 'action': 'donation', 'color': '#ec4899'},
            {'icon': 'fa-calculator', 'label': 'Brzi iznos', 'action': 'add_amount', 'color': '#c9a84c'},
        ]

    return actions
