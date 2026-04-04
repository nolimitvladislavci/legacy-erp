from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


class InventoryItem(models.Model):
    CATEGORY_CHOICES = [
        ('material',   _('Materijal')),
        ('tool',       _('Alat')),
        ('equipment',  _('Oprema')),
        ('consumable', _('Potrošni materijal')),
        ('product',    _('Gotov proizvod')),
        ('service',    _('Usluga')),
        ('food',       _('Hrana')),
        ('drink',      _('Piće')),
        ('dessert',    _('Desert')),
        ('special',    _('Posebna ponuda')),
        ('other',      _('Ostalo')),
    ]

    # Multitenancy
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='inventory_items',
        verbose_name=_('Tvrtka'),
    )

    # ── SplitAllocation — Agro-Turizam 360 ──
    reserved_inhouse = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Rezervirano in-house'),
        help_text=_('Količina rezervirana za gastro/konobu — ne ide na marketplace')
    )
    reserved_marketplace = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Rezervirano marketplace'),
        help_text=_('Količina na aktivnim marketplace listinzima')
    )
    allocation_buffer_pct = models.PositiveIntegerField(
        default=10,
        verbose_name=_('Buffer (%)'),
        help_text=_('Postotak zalihe koji se drži kao sigurnosni buffer')
    )

    @property
    def unreserved_qty(self):
        """Slobodna količina — nije ni in-house ni marketplace."""
        return max(0, self.quantity - self.reserved_inhouse - self.reserved_marketplace)

    @property
    def buffer_qty(self):
        """Buffer količina — minimum koji se ne prodaje."""
        return self.quantity * self.allocation_buffer_pct / 100

    @property
    def marketplace_available(self):
        """Koliko se još može staviti na marketplace."""
        return max(0, self.unreserved_qty - self.buffer_qty)

    def should_delist(self):
        """Treba li skinuti s marketplace-a zbog nedovoljnih zaliha?"""
        return self.reserved_inhouse > (self.quantity - self.buffer_qty)

    objects = CompanyManager()

    name     = models.CharField(max_length=200, verbose_name=_('Naziv'))
    sku      = models.CharField(max_length=50, verbose_name=_('SKU / Šifra'))
    barcode  = models.CharField(max_length=100, blank=True, verbose_name=_('Barkod / EAN'))
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other', verbose_name=_('Kategorija'))
    description = models.TextField(blank=True, verbose_name=_('Opis'))
    unit     = models.CharField(max_length=20, default='kom', verbose_name=_('Jedinica mjere'))

    # ── W1A: KLASIFIKACIJA (BORG-0 popunjava) ────────────────────────
    ITEM_CLASS_CHOICES = [
        ('tangible',   _('Materijalno (roba/materijal)')),
        ('service',    _('Usluga (ne ide u skladište)')),
        ('intangible', _('Nematerijalno (IP/licence)')),
        ('asset',      _('Imovina (osnovna sredstva)')),
        ('financial',  _('Financijsko (devize/vrijednosnice)')),
    ]
    FISCAL_TREATMENT_CHOICES = [
        ('standard',     _('Standardno — fiskalizira')),
        ('service_cash', _('Usluga — fiskalizira pri gotovinskoj naplati')),
        ('exempt_pdv',   _('Oslobođeno PDV-a')),
        ('no_fiscal',    _('Ne fiskalizira (imovina/IP)')),
        ('currency',     _('Deviza — posebna evidencija')),
        ('pfand',        _('Ambalaža/Pfand — poseban tretman')),
    ]
    TRADE_TYPE_CHOICES = [
        ('retail',    _('Maloprodaja (B2C)')),
        ('wholesale', _('Veleprodaja (B2B)')),
        ('both',      _('Oboje')),
        ('internal',  _('Interno — ne prodaje se')),
    ]

    item_class       = models.CharField(max_length=15, choices=ITEM_CLASS_CHOICES,
                                        default='tangible', db_index=True, verbose_name=_('Klasa artikla'))
    fiscal_treatment = models.CharField(max_length=15, choices=FISCAL_TREATMENT_CHOICES,
                                        default='standard', db_index=True, verbose_name=_('Fiskalni tretman'))
    trade_type       = models.CharField(max_length=15, choices=TRADE_TYPE_CHOICES,
                                        default='both', verbose_name=_('Tip prodaje'))

    # ── W1A: VELEPRODAJNE CIJENE ──────────────────────────────────────
    wholesale_price    = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                            verbose_name=_('Veleprodajna cijena (bez PDV)'))
    min_order_qty      = models.DecimalField(max_digits=10, decimal_places=2, default=1,
                                            verbose_name=_('Min. narudžba (veleprodaja)'))
    price_valid_until  = models.DateField(null=True, blank=True, verbose_name=_('Cijena vrijedi do'))
    vat_excluded_price = models.BooleanField(default=False,
                                            verbose_name=_('Cijena bez PDV-a (veleprodaja)'))

    # ── W1A: IMOVINA / ASSET ─────────────────────────────────────────
    asset_purchase_date       = models.DateField(null=True, blank=True, verbose_name=_('Datum nabave imovine'))
    asset_useful_life_years   = models.PositiveSmallIntegerField(null=True, blank=True,
                                                                 verbose_name=_('Vijek trajanja (god.)'))
    asset_depreciation_method = models.CharField(max_length=10, blank=True,
                                                 choices=[('linear', 'Linearna'), ('declining', 'Degresivna')],
                                                 verbose_name=_('Metoda amortizacije'))
    asset_current_value       = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                                    verbose_name=_('Sadašnja vrijednost'))
    asset_location            = models.CharField(max_length=200, blank=True, verbose_name=_('Fizička lokacija'))
    asset_serial_number       = models.CharField(max_length=100, blank=True, verbose_name=_('Serijski broj'))
    asset_inventory_number    = models.CharField(max_length=50, blank=True, verbose_name=_('Inventarni broj'))

    # ── W1A: CARINSKA / PODRIJETLO ───────────────────────────────────
    customs_tariff     = models.CharField(max_length=15, blank=True, verbose_name=_('Carinska tarifa (HS kod)'))
    country_of_origin  = models.CharField(max_length=2, blank=True, verbose_name=_('Zemlja podrijetla (ISO)'))

    # Količine
    quantity     = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Trenutna zaliha'))
    min_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Minimalna zaliha'))
    max_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Maksimalna zaliha'))

    # Cijene
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Nabavna cijena'))
    wholesale_min_qty = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name='Min. kol. veleprodaja', help_text='Ispod ove kolicine — maloprodajna cijena')
    purchase_date     = models.DateField(null=True, blank=True, verbose_name='Datum nabave', help_text='Za amortizaciju (assets)')
    unit_price     = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Prodajna cijena'))

    # PDV
    tax_rate = models.ForeignKey(
        'companies.TaxRate', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_('PDV stopa'),
    )


    # ── DSFinV-K / KassenSichV flags ─────────────────────────────────────
    # Livestock link — za mlijecne/mesne proizvode
    livestock_animal = models.ForeignKey(
        'livestock.Livestock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='products',
        verbose_name='Vezano grlo',
        help_text='Za pracenje karencije — blokira prodaju ako grlo u karenciji',
    )

    # Flock link — za jaja/perad iz udruge modula
    source_flock = models.ForeignKey(
        'udruge.Flock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inventory_products',
        verbose_name=_('Izvorno jato'),
        help_text=_('Za karencija enforcement — blokira POS prodaju dok je jato pod lijekovima'),
    )

    is_pfand = models.BooleanField(
        default=False,
        verbose_name=_("Pfand (povratna ambalaza)"),
        help_text=_("Kaucija za casu/bocu — DSFinV-K GV_TYP=Umsatz, SKR03=8404"),
    )

    # ── Nonprofit flag ────────────────────────────────────────────────
    is_nonprofit_activity = models.BooleanField(
        default=False,
        verbose_name=_("Neprofitna djelatnost"),
        help_text=_("Clanarina, donacija, dotacija — NE fiskalizira se, NE pdv"),
    )
    linked_pfand_item = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="parent_articles",
        verbose_name=_("Vezani Pfand artikl"),
        help_text=_("Ako je postavljeno, pri prodaji ovog artikla automatski se dodaje Pfand stavka."),
    )
    pfand_tax_override = models.DecimalField(
        max_digits=5, decimal_places=2, default=19,
        verbose_name=_("PDV stopa Pfanda (%)"),
        help_text=_("Obično 19% za Leergut u DE. Ostavite 19 ako niste sigurni."),
    )
    is_tip = models.BooleanField(
        default=False,
        verbose_name=_("Napojnica radnika (TrinkgeldAN)"),
        help_text=_("Napojnica za radnika — DSFinV-K GV_TYP=TrinkgeldAN, UST=0pct"),
    )
    is_tip_employer = models.BooleanField(
        default=False,
        verbose_name=_("Napojnica vlasnika (TrinkgeldAG)"),
        help_text=_("Napojnica za vlasnika — DSFinV-K GV_TYP=TrinkgeldAG, UST=19pct"),
    )
    kalo_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name=_("Kalo %"),
        help_text="Prirodni kalo (npr. 2.5%)",
    )
    is_weighable = models.BooleanField(
        default=False,
        verbose_name=_("Prodaje se na vagu"),
        help_text="Ako je označeno, POS traži unos težine (kg) pri svakom dodavanju",
    )

    # ── Stockable guard ──────────────────────────────────────────
    NON_STOCKABLE_CATEGORIES = ('service',)
    # is_stockable property moved to W1A business logic block below
    dsfinvk_gv_typ = models.CharField(
        max_length=30, blank=True,
        verbose_name=_("DSFinV-K GV_TYP override"),
        help_text=_("Prazno = automatski Umsatz. Samo za posebne slucajeve."),
    )

    location = models.CharField(max_length=100, blank=True, verbose_name=_('Lokacija u skladištu'))
    supplier = models.ForeignKey(
        'partners.Partner', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_('Dobavljač'),
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivan'))

    # Slika artikla
    image = models.ImageField(
        upload_to='inventory/', blank=True, null=True,
        verbose_name=_('Slika'),
    )
    # Webshop integracija
    webshop_visible = models.BooleanField(
        default=False,
        verbose_name=_('Vidljiv u webshopu'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Artikl')
        verbose_name_plural = _('Artikli')
        ordering = ['name']
        # Unique SKU per company
        unique_together = [('company', 'sku')]

    def __str__(self):
        return f"{self.name} ({self.sku}) – {self.quantity} {self.unit}"

    # ── W1A: Poslovna logika (BORG-0 klasifikacija omogućuje) ────────

    def should_track_stock(self):
        """Da li ovaj artikl ide u fizičko skladište?"""
        return self.item_class in ('tangible', 'asset')

    def should_fiscalize(self):
        """Da li ovaj artikl ide u fiskalizaciju?"""
        return self.fiscal_treatment in ('standard', 'service_cash', 'pfand')

    def get_price_for_buyer(self, buyer_type='b2c', quantity=1):
        """Vrati ispravnu cijenu ovisno o tipu kupca.
        Returns: dict(price, vat_included, price_type)
        """
        from decimal import Decimal
        if buyer_type in ('b2b', 'wholesale') and self.wholesale_price > 0 and qty >= float(self.wholesale_min_qty or 1):
            if quantity >= float(self.min_order_qty):
                return {
                    'price': self.wholesale_price,
                    'vat_included': not self.vat_excluded_price,
                    'price_type': 'wholesale',
                }
        return {
            'price': self.unit_price,
            'vat_included': True,
            'price_type': 'retail',
        }

    def get_depreciation_annual(self):
        """Godišnja linearna amortizacija za asset."""
        if self.item_class != 'asset':
            return 0
        if not self.asset_purchase_date or not self.asset_useful_life_years:
            return 0
        if self.asset_depreciation_method == 'linear':
            return float(self.purchase_price) / self.asset_useful_life_years
        return 0

    @property
    def is_stockable(self):
        """Usluge, napojnice, IP i nonprofit NEMAJU fizičku zalihu."""
        if self.item_class in ('service', 'intangible', 'financial'):
            return False
        if self.category in self.NON_STOCKABLE_CATEGORIES:
            return False
        if self.is_tip or self.is_tip_employer:
            return False
        return True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.webshop_visible:
            try:
                from inventory.sync import sync_to_webshop
                sync_to_webshop(self)
            except Exception:
                pass
    @property
    def is_low_stock(self):
        return self.quantity <= self.min_quantity

    @property
    def margin_percent(self):
        if self.purchase_price and self.purchase_price > 0:
            return round((self.unit_price - self.purchase_price) / self.purchase_price * 100, 2)
        return None

    @property
    def stock_value(self):
        return round(self.quantity * self.purchase_price, 2)

    @property
    def selling_value(self):
        return round(self.quantity * self.unit_price, 2)


class StockMovement(models.Model):
    TYPE_CHOICES = [
        ('in',           _('Ulaz (nabava)')),
        ('out',          _('Izlaz (prodaja/upotreba)')),
        ('internal_use', _('Interna upotreba (repromaterijal)')),
        ('adjustment',   _('Korekcija zalihe')),
        ('transfer',     _('Prijenos na drugu lokaciju')),
        ('return',       _('Povrat dobavljaču')),
        ('donation_in',  _('Ulaz (materijalna donacija)')),
        ('writeoff',     _('Otpis / Kalo')),
        ('consumption',  _('Utrošak (proizvodnja)')),
        ('production',   _('Proizvedeno')),
        ('scrap',        _('Škart (proizvodnja)')),
    ]

    item          = models.ForeignKey(InventoryItem, on_delete=models.CASCADE,
                                       related_name='movements', verbose_name=_('Artikl'))
    movement_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name=_('Vrsta kretanja'))
    quantity      = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Količina'))
    unit_price    = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                         verbose_name=_('Cijena po jedinici (u trenutku kretanja)'))

    # Veza na račun (automatski izlaz zalihe pri fakturiranju)
    invoice       = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_movements',
        verbose_name=_('Vezani račun'),
    )

    # Veza na proizvodni nalog
    production_order = models.ForeignKey(
        'production.ProductionOrder', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_movements',
        verbose_name=_('Radni nalog'),
    )
    batch_number = models.CharField(max_length=50, blank=True, verbose_name=_('Broj šarže'))
    stock_before = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    stock_after = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

    reason        = models.CharField(max_length=255, blank=True, verbose_name=_('Razlog / Napomena'))
    performed_by  = models.ForeignKey(User, on_delete=models.SET_NULL,
                                       null=True, blank=True, verbose_name=_('Izvršio'))
    created_at    = models.DateTimeField(auto_now_add=True)

    # Materijalna donacija polja (za donation_in tip)
    donor_name = models.CharField(max_length=200, blank=True, verbose_name=_('Donator'))
    donor_oib = models.CharField(max_length=13, blank=True, verbose_name=_('OIB donatora'))
    fair_market_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name=_('Fer trzisna vrijednost'),
        help_text=_('Obavezno za donation_in — procjena vrijednosti za knjizenje'),
    )

    class Meta:
        verbose_name = _('Kretanje zalihe')
        verbose_name_plural = _('Kretanja zalihe')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.item.name} {self.get_movement_type_display()} {self.quantity}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update item quantity after movement
        item = self.item
        if self.movement_type == 'in':
            item.quantity = models.F('quantity') + self.quantity
        elif self.movement_type in ('out', 'internal_use', 'return'):
            item.quantity = models.F('quantity') - self.quantity
        elif self.movement_type == 'adjustment':
            item.quantity = self.quantity  # direct set
        item.save(update_fields=['quantity'])
        item.refresh_from_db()


from decimal import ROUND_HALF_UP, Decimal

# ── PRIMKA (GOODS RECEIPT) ─────────────────────────────────────────────────────

class GoodsReceipt(models.Model):
    STATUS_CHOICES = [
        ('draft',             _('Nacrt')),
        ('confirmed',         _('Potvrđena')),
        ('pending_invoice',   _('Primljeno bez računa')),
        ('cancelled',         _('Otkazana')),
    ]
    company         = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True, verbose_name=_('Tvrtka'),
    )
    objects         = CompanyManager()
    receipt_number  = models.CharField(max_length=50, blank=True, verbose_name=_('Broj primke'))
    supplier        = models.ForeignKey(
        'partners.Partner', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='goods_receipts', verbose_name=_('Dobavljač'),
    )
    date            = models.DateField(verbose_name=_('Datum primke'))
    document_number = models.CharField(max_length=100, blank=True, verbose_name=_('Broj dostavnice/fakture'))
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name=_('Status'))
    notes           = models.TextField(blank=True, verbose_name=_('Napomene'))
    created_by      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Kreirao'),
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    total_purchase  = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           verbose_name=_('Ukupna nabavna vrijednost'))
    total_selling   = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           verbose_name=_('Ukupna prodajna vrijednost'))

    # --- HR Primka klasifikacija (2026-03-14) ---
    receipt_type = models.CharField(
        max_length=30,
        choices=[
            ("supplier", _("Primka od dobavljača")),
            ("return", _("Povratna primka")),
            ("transfer", _("Međuskladišnica (ulaz)")),
            ("inventory", _("Inventurni višak")),
            ("consignment", _("Konsignacijska primka")),
            ("complaint", _("Reklamacijska primka")),
        ],
        default="supplier",
        verbose_name=_("Vrsta primke"),
    )
    linked_invoice_number = models.CharField(
        max_length=100, blank=True,
        verbose_name=_("Broj ulaznog računa"),
        help_text=_("Broj fakture dobavljača"),
    )
    warehouse = models.CharField(
        max_length=100, blank=True, default="Glavno skladište",
        verbose_name=_("Skladište"),
    )
    received_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="goods_received",
        verbose_name=_("Primio robu"),
    )
    received_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_("Datum/vrijeme prijema"),
    )
    is_consignment = models.BooleanField(
        default=False,
        verbose_name=_("Konsignacija"),
        help_text=_("Roba na čuvanje/prodaju za tuđi račun"),
    )
    condition_notes = models.TextField(
        blank=True,
        verbose_name=_("Napomena o stanju"),
        help_text=_("Oštećenja, manjak, nesukladnosti"),
    )

    # Fix 1: Pending invoice tracking
    invoice_due_date = models.DateField(
        null=True, blank=True,
        verbose_name=_("Očekivani datum računa"),
        help_text=_("Kada se očekuje ulazni račun od dobavljača"),
    )
    linked_invoice = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='goods_receipts',
        verbose_name=_("Vezani ulazni račun"),
    )

    # Fix 3: Retail valuation flag
    is_retail_valuation = models.BooleanField(
        default=False,
        verbose_name=_("Maloprodajno zaduženje"),
        help_text=_("Ako DA, knjiženje po MPC (3000/2200/3900). Ako NE, po nabavnoj (3000/1400/2200)."),
    )


    class Meta:
        verbose_name        = _('Primka')
        verbose_name_plural = _('Primke')
        ordering            = ['-date', '-created_at']

    def __str__(self):
        return f"Primka {self.receipt_number} – {self.date}"

    def confirm(self):
        """Confirm receipt: update InventoryItem prices, create PriceChange + StockMovement records.
        Consignment receipts skip stock/price updates and book to off-balance accounts.
        All confirmed receipts get an automatic journal entry."""
        from django.db import transaction as _tx
        is_consignment = self.is_consignment or self.receipt_type == 'consignment'

        with _tx.atomic():
            total_purchase = Decimal('0')
            total_selling  = Decimal('0')

            for ri in self.items.select_related('inventory_item').all():
                item   = ri.inventory_item
                old_pp = item.purchase_price
                old_up = item.unit_price
                new_pp = ri.cost_price_unit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                new_up = ri.selling_price_gross.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                if not is_consignment:
                    # Normal receipt: update prices and stock
                    item.purchase_price = new_pp
                    item.unit_price     = new_up
                    item.save(update_fields=['purchase_price', 'unit_price'])
                    PriceChange.objects.create(
                        inventory_item=item,
                        goods_receipt=self,
                        old_purchase_price=old_pp,
                        new_purchase_price=new_pp,
                        old_unit_price=old_up,
                        new_unit_price=new_up,
                        changed_by=self.created_by,
                    )
                    StockMovement.objects.create(
                        item=item,
                        movement_type='in',
                        quantity=ri.quantity,
                        unit_price=new_pp,
                        reason=f'Primka {self.receipt_number}',
                        performed_by=self.created_by,
                    )

                    # LOT/batch auto-creation (Drone #3)
                    if ri.batch_number or ri.expiry_date:
                        batch = StockBatch.objects.create(
                            company=self.company,
                            item=item,
                            batch_number=ri.batch_number or '',
                            quantity=ri.quantity,
                            expected_weight=ri.quantity if item.is_weighable else 0,
                            expiry_date=ri.expiry_date,
                            location=self.warehouse or '',
                        )
                        ri.stock_batch = batch
                        ri.save(update_fields=['stock_batch'])

                total_purchase += ri.total_cost_price
                total_selling  += ri.total_selling_gross

            self.status         = 'confirmed'
            self.total_purchase = total_purchase.quantize(Decimal('0.01'))
            self.total_selling  = total_selling.quantize(Decimal('0.01'))
            if is_consignment:
                self.notes = (self.notes or '') + '\n[KONSIGNACIJA] Roba nije zadužena na zalihu.'
            self.save(update_fields=['status', 'total_purchase', 'total_selling', 'notes'])

            # Activity tracking
            try:
                from worktime.tracker import track
                if hasattr(self, '_confirmed_by') and self._confirmed_by:
                    track(self._confirmed_by, 'INV', 'GOODS_RECEIPT', ref=self.grn_number,
                          detail='Primka %s, %d stavki' % (self.grn_number, self.items.count()),
                          company=self.company)
            except Exception:
                pass

            # Fix 3: automatic journal entry
            self._create_journal_entry()

    def _create_journal_entry(self):
        """Create konto booking from confirmed GoodsReceipt."""
        from konto.models import JournalEntry, LedgerLine, KontoAccount
        import logging
        log = logging.getLogger('inventory')

        company = self.company
        if not company:
            return

        is_consignment = self.is_consignment or self.receipt_type == 'consignment'

        def _get_or_create_account(code, name, account_type):
            acc, _ = KontoAccount.objects.get_or_create(
                company=company, code=code,
                defaults={'name': name, 'account_type': account_type},
            )
            return acc

        # Generate entry number
        from datetime import date as _date
        year = _date.today().year
        prefix = f'PRIM-{year}-'
        last = JournalEntry.objects.filter(
            company=company, entry_number__startswith=prefix,
        ).order_by('-entry_number').first()
        seq = 1
        if last and last.entry_number:
            try:
                seq = int(last.entry_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                pass
        entry_number = f'{prefix}{seq:04d}'

        nabavna = float(self.total_purchase or 0)

        # -- Consignment: off-balance D 9100 / P 9900 --
        if is_consignment:
            if nabavna <= 0:
                return
            je = JournalEntry.objects.create(
                company=company,
                entry_number=entry_number,
                date=self.date,
                description=f'Konsignacija {self.receipt_number} — {self.supplier or ""}',
                source_type='manual',
                is_posted=True,
                created_by=self.created_by,
            )
            acc_9100 = _get_or_create_account('9100', 'Roba na konsignaciji (izvanbilančna)', 'equity')
            acc_9900 = _get_or_create_account('9900', 'Izvanbilančna obveza', 'equity')
            LedgerLine.objects.create(journal_entry=je, account=acc_9100, side='debit',
                                      amount=Decimal(str(nabavna)), description=f'Primka {self.receipt_number}')
            LedgerLine.objects.create(journal_entry=je, account=acc_9900, side='credit',
                                      amount=Decimal(str(nabavna)), description=f'Primka {self.receipt_number}')
            log.info('Konsignacija knjizena: %s (D9100/P9900 %.2f)', self.receipt_number, nabavna)
            return

        # -- Transfer: no purchase booking --
        if self.receipt_type == 'transfer':
            return

        # -- Inventory surplus: D 3000 / P 7900 --
        if self.receipt_type == 'inventory':
            if nabavna <= 0:
                return
            je = JournalEntry.objects.create(
                company=company,
                entry_number=entry_number,
                date=self.date,
                description=f'Inventurni višak {self.receipt_number}',
                source_type='manual',
                is_posted=True,
                created_by=self.created_by,
            )
            acc_3000 = _get_or_create_account('3000', 'Roba u skladištu', 'asset')
            acc_7900 = _get_or_create_account('7900', 'Ostali prihodi', 'income')
            LedgerLine.objects.create(journal_entry=je, account=acc_3000, side='debit',
                                      amount=Decimal(str(nabavna)), description=f'Višak {self.receipt_number}')
            LedgerLine.objects.create(journal_entry=je, account=acc_7900, side='credit',
                                      amount=Decimal(str(nabavna)), description=f'Višak {self.receipt_number}')
            log.info('Inventurni visak knjizen: %s (D3000/P7900 %.2f)', self.receipt_number, nabavna)
            return

        # -- Return: reverse booking D 2200 / P 3000 --
        if self.receipt_type == 'return':
            if nabavna <= 0:
                return
            je = JournalEntry.objects.create(
                company=company,
                entry_number=entry_number,
                date=self.date,
                description=f'Povratna primka {self.receipt_number} — {self.supplier or ""}',
                source_type='manual',
                is_posted=True,
                created_by=self.created_by,
            )
            acc_2200 = _get_or_create_account('2200', 'Dobavljači', 'liability')
            acc_3000 = _get_or_create_account('3000', 'Roba u skladištu', 'asset')
            LedgerLine.objects.create(journal_entry=je, account=acc_2200, side='debit',
                                      amount=Decimal(str(nabavna)), description=f'Povrat {self.receipt_number}')
            LedgerLine.objects.create(journal_entry=je, account=acc_3000, side='credit',
                                      amount=Decimal(str(nabavna)), description=f'Povrat {self.receipt_number}')
            log.info('Povratna primka knjizena: %s (D2200/P3000 %.2f)', self.receipt_number, nabavna)
            return

        # -- Standard supplier receipt --
        if nabavna <= 0:
            return

        prodajna = float(self.total_selling or 0)
        desc = f'Primka {self.receipt_number} — {self.supplier or ""}'

        je = JournalEntry.objects.create(
            company=company,
            entry_number=entry_number,
            date=self.date,
            description=desc,
            source_type='manual',
            is_posted=True,
            created_by=self.created_by,
        )

        if self.is_retail_valuation and prodajna > 0:
            # Maloprodajno zaduzenje: D 3000 (MPC) / P 2200 (nabavna) + P 3900 (RUC)
            ruc = prodajna - nabavna
            acc_3000 = _get_or_create_account('3000', 'Roba u skladištu', 'asset')
            acc_2200 = _get_or_create_account('2200', 'Dobavljači', 'liability')
            acc_3900 = _get_or_create_account('3900', 'Razlika u cijeni (RUC)', 'liability')
            LedgerLine.objects.create(journal_entry=je, account=acc_3000, side='debit',
                                      amount=Decimal(str(prodajna)).quantize(Decimal('0.01')),
                                      description=f'MPC {self.receipt_number}')
            LedgerLine.objects.create(journal_entry=je, account=acc_2200, side='credit',
                                      amount=Decimal(str(nabavna)).quantize(Decimal('0.01')),
                                      description=f'Dobavljac {self.receipt_number}')
            if ruc > 0:
                LedgerLine.objects.create(journal_entry=je, account=acc_3900, side='credit',
                                          amount=Decimal(str(ruc)).quantize(Decimal('0.01')),
                                          description=f'RUC {self.receipt_number}')
            log.info('Maloprodajna primka knjizena: %s (D3000 %.2f / P2200 %.2f + P3900 %.2f)',
                     self.receipt_number, prodajna, nabavna, ruc)
        else:
            # Veleprodajno zaduzenje: D 3000 (nabavna) + D 1400 (pretporez) / P 2200 (ukupno)
            total_vat = float(sum(
                ri.selling_price_vat * ri.quantity
                for ri in self.items.all()
            ) or 0)
            ukupno = nabavna + total_vat

            acc_3000 = _get_or_create_account('3000', 'Roba u skladištu', 'asset')
            acc_2200 = _get_or_create_account('2200', 'Dobavljači', 'liability')
            LedgerLine.objects.create(journal_entry=je, account=acc_3000, side='debit',
                                      amount=Decimal(str(nabavna)).quantize(Decimal('0.01')),
                                      description=f'Nabavna {self.receipt_number}')
            if total_vat > 0:
                acc_1400 = _get_or_create_account('1400', 'Pretporez (ulazni PDV)', 'asset')
                LedgerLine.objects.create(journal_entry=je, account=acc_1400, side='debit',
                                          amount=Decimal(str(total_vat)).quantize(Decimal('0.01')),
                                          description=f'Pretporez {self.receipt_number}')
            LedgerLine.objects.create(journal_entry=je, account=acc_2200, side='credit',
                                      amount=Decimal(str(ukupno)).quantize(Decimal('0.01')),
                                      description=f'Dobavljac {self.receipt_number}')
            log.info('Veleprodajna primka knjizena: %s (D3000 %.2f + D1400 %.2f / P2200 %.2f)',
                     self.receipt_number, nabavna, total_vat, ukupno)


class GoodsReceiptItem(models.Model):
    receipt        = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE,
                                        related_name='items', verbose_name=_('Primka'))
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT,
                                        verbose_name=_('Artikl'))
    quantity       = models.DecimalField(max_digits=10, decimal_places=3, default=1,
                                          verbose_name=_('Količina'))
    # Nabavna kalkulacija (HR/DE)
    purchase_price_unit  = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                                verbose_name=_('Nabavna cijena/jed.'))
    dependent_costs_unit = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                                verbose_name=_('Zavisni troškovi/jed.'))
    cost_price_unit      = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                                verbose_name=_('Nabavna cijena s troš.'))
    # Prodajni obračun
    margin_percent       = models.DecimalField(max_digits=6,  decimal_places=2, default=0,
                                                verbose_name=_('Marža (%)'))
    margin_amount        = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                                verbose_name=_('Iznos marže'))
    selling_price_net    = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                                verbose_name=_('Prodajna cijena bez PDV'))
    tax_rate             = models.DecimalField(max_digits=5,  decimal_places=2, default=25,
                                                verbose_name=_('PDV stopa (%)'))
    selling_price_vat    = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                                verbose_name=_('Iznos PDV-a'))
    selling_price_gross  = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                                verbose_name=_('MPC (s PDV-om)'))
    # Ukupni iznosi retka
    total_purchase_price = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                                verbose_name=_('Uk. nabavna'))
    total_cost_price     = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                                verbose_name=_('Uk. nabavna s troš.'))
    total_selling_gross  = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                                verbose_name=_('Uk. MPC'))

    # LOT / batch tracking (Drone #3)
    batch_number = models.CharField(
        max_length=100, blank=True,
        verbose_name=_('Broj sarze / LOT'),
        help_text=_('LOT oznaka sa ambalaže dobavljača'),
    )
    expiry_date = models.DateField(
        null=True, blank=True,
        verbose_name=_('Datum isteka roka'),
    )
    stock_batch = models.ForeignKey(
        'StockBatch', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='goods_receipt_items',
        verbose_name=_('Kreirana sarža'),
    )

    class Meta:
        verbose_name        = _('Stavka primke')
        verbose_name_plural = _('Stavke primke')

    def __str__(self):
        return f"{self.inventory_item.name} × {self.quantity}"

    def calculate(self):
        R  = ROUND_HALF_UP
        pp = Decimal(str(self.purchase_price_unit  or 0))
        dc = Decimal(str(self.dependent_costs_unit or 0))
        cp = pp + dc
        self.cost_price_unit = cp
        mp = Decimal(str(self.margin_percent or 0))
        ma = (cp * mp / Decimal('100')).quantize(Decimal('0.0001'), rounding=R)
        self.margin_amount = ma
        sn = cp + ma
        self.selling_price_net = sn
        tp = Decimal(str(self.tax_rate or 0))
        va = (sn * tp / Decimal('100')).quantize(Decimal('0.0001'), rounding=R)
        self.selling_price_vat = va
        sg = (sn + va).quantize(Decimal('0.0001'), rounding=R)
        self.selling_price_gross = sg
        qty = Decimal(str(self.quantity or 0))
        self.total_purchase_price = (pp * qty).quantize(Decimal('0.01'), rounding=R)
        self.total_cost_price     = (cp * qty).quantize(Decimal('0.01'), rounding=R)
        self.total_selling_gross  = (sg * qty).quantize(Decimal('0.01'), rounding=R)

    def save(self, *args, **kwargs):
        self.calculate()
        super().save(*args, **kwargs)


class PriceChange(models.Model):
    inventory_item     = models.ForeignKey(InventoryItem, on_delete=models.CASCADE,
                                            related_name='price_changes', verbose_name=_('Artikl'))
    goods_receipt      = models.ForeignKey(GoodsReceipt, on_delete=models.SET_NULL,
                                            null=True, blank=True, verbose_name=_('Primka'))
    old_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Stara nabavna'))
    new_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Nova nabavna'))
    old_unit_price     = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Stara prodajna'))
    new_unit_price     = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Nova prodajna'))
    changed_by         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                            verbose_name=_('Promijenio'))
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Promjena cijene')
        verbose_name_plural = _('Promjene cijena')
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.inventory_item.name}: {self.old_unit_price}→{self.new_unit_price}"


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 10: Continuous Blind Inventory — StockBatch + InventoryCountLog
# ══════════════════════════════════════════════════════════════════════════════

class StockBatch(models.Model):
    """
    Physical batch of goods in the warehouse.
    Tracks expected weight, expiry, and quarantine status.
    FEFO (First Expired First Out) ordering by default.
    """
    QUARANTINE_CHOICES = [
        ('active', _('Aktivna')),
        ('quarantine', _('HACCP karantena')),
        ('disposed', _('Zbrinuto')),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='stock_batches', verbose_name=_('Tvrtka'),
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE,
        related_name='stock_batches', verbose_name=_('Artikl'),
    )
    batch_number = models.CharField(max_length=100, blank=True, verbose_name=_('Broj sarze / LOT'))

    # Slijedivost — iz kojeg jata dolazi ova šarža
    source_flock = models.ForeignKey(
        'udruge.Flock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_batches',
        verbose_name=_('Izvorno jato'),
        help_text=_('LOT-level karencija: blokira samo OVU šaržu, ne sve artikle'),
    )

    expected_weight = models.DecimalField(
        max_digits=10, decimal_places=3, default=0,
        verbose_name=_('Ocekivana tezina (kg)'),
    )
    actual_weight = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name=_('Zadnja izmjerena tezina (kg)'),
    )
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Kolicina (kom)'),
    )
    expiry_date = models.DateField(null=True, blank=True, verbose_name=_('Datum isteka'))
    quarantine_status = models.CharField(
        max_length=20, choices=QUARANTINE_CHOICES, default='active',
        verbose_name=_('Status'),
    )
    quarantine_reason = models.CharField(max_length=255, blank=True, verbose_name=_('Razlog karantene'))
    location = models.CharField(max_length=100, blank=True, verbose_name=_('Lokacija'))
    last_counted_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Zadnje brojanje'))
    last_counted_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Zadnje brojao'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Sarzna zaliha')
        verbose_name_plural = _('Sarzne zalihe')
        ordering = ['expiry_date', 'created_at']  # FEFO

    def __str__(self):
        exp = self.expiry_date.strftime('%d.%m.%Y') if self.expiry_date else 'bez roka'
        return f"{self.item.name} LOT:{self.batch_number} ({exp})"

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        from datetime import date
        return self.expiry_date < date.today()

    @property
    def kalo_tolerance(self):
        """Max allowed weight loss from kalo (percentage from item)."""
        return self.item.kalo_percent or 0

    @property
    def min_acceptable_weight(self):
        """Minimum weight before triggering theft alert."""
        if not self.expected_weight:
            return 0
        tol = self.kalo_tolerance
        return float(self.expected_weight) * (1 - float(tol) / 100)

    def check_quarantine(self):
        """Auto-quarantine if expired."""
        if self.is_expired and self.quarantine_status == 'active':
            self.quarantine_status = 'quarantine'
            self.quarantine_reason = 'Automatska karantena: istekao rok trajanja'
            self.save(update_fields=['quarantine_status', 'quarantine_reason', 'updated_at'])
            return True
        return False


class InventoryCountLog(models.Model):
    """Audit trail for every inventory count submitted."""
    RESULT_CHOICES = [
        ('ok', _('U redu')),
        ('kalo', _('Prirodni kalo')),
        ('theft_alert', _('Upozorenje: moguca kradja')),
        ('surplus', _('Visak')),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        verbose_name=_('Tvrtka'),
    )
    batch = models.ForeignKey(
        'StockBatch', on_delete=models.CASCADE,
        related_name='count_logs', verbose_name=_('Sarza'),
    )
    expected_weight = models.DecimalField(max_digits=10, decimal_places=3, verbose_name=_('Ocekivana tezina'))
    actual_weight = models.DecimalField(max_digits=10, decimal_places=3, verbose_name=_('Izmjerena tezina'))
    difference_kg = models.DecimalField(max_digits=10, decimal_places=3, verbose_name=_('Razlika (kg)'))
    difference_pct = models.DecimalField(max_digits=6, decimal_places=2, verbose_name=_('Razlika (%)'))
    kalo_tolerance_pct = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=_('Tolerancija kala (%)'))
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, verbose_name=_('Rezultat'))
    counted_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, verbose_name=_('Brojao'),
    )
    notes = models.TextField(blank=True, verbose_name=_('Napomena'))
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Zapisnik inventure')
        verbose_name_plural = _('Zapisnici inventure')
        ordering = ['-created_at']

    def __str__(self):
        return f"Count {self.batch} -> {self.result} ({self.difference_pct}%)"


# ════════════════════════════════════════════════════════════
# WAREHOUSE — Skladišta (lokacije)
# ════════════════════════════════════════════════════════════

class Warehouse(models.Model):
    """Skladiste/prodajno mjesto unutar firme."""
    WAREHOUSE_TYPES = [
        ('production', _('Proizvodnja/centrala')),
        ('retail', _('Prodajno mjesto')),
        ('storage', _('Skladiste')),
        ('vehicle', _('Vozilo/teren')),
    ]

    id = models.AutoField(primary_key=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='warehouses', verbose_name=_('Tvrtka'))
    objects = CompanyManager()
    name = models.CharField(max_length=100, verbose_name=_('Naziv'))
    code = models.CharField(max_length=20, blank=True, verbose_name=_('Sifra'))
    warehouse_type = models.CharField(max_length=20, choices=WAREHOUSE_TYPES,
                                       default='storage', verbose_name=_('Tip'))
    address = models.CharField(max_length=255, blank=True, verbose_name=_('Adresa'))
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivno'))
    is_default = models.BooleanField(default=False, verbose_name=_('Glavno skladiste'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Skladiste')
        verbose_name_plural = _('Skladista')
        unique_together = ('company', 'code')
        ordering = ['name']

    def __str__(self):
        return '%s (%s)' % (self.name, self.get_warehouse_type_display())


class WarehouseTransfer(models.Model):
    """Medjuskladisnica / Izdatnica — prijenos robe izmedju skladista."""
    STATUS_CHOICES = [
        ('draft', _('Nacrt')),
        ('confirmed', _('Potvrdjeno')),
        ('in_transit', _('U prijenosu')),
        ('received', _('Zaprimljeno')),
        ('cancelled', _('Otkazano')),
    ]

    id = models.AutoField(primary_key=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='warehouse_transfers', verbose_name=_('Tvrtka'))
    objects = CompanyManager()
    transfer_number = models.CharField(max_length=50, blank=True, verbose_name=_('Broj dokumenta'))
    date = models.DateField(verbose_name=_('Datum'))
    source_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT,
                                          related_name='transfers_out', verbose_name=_('Iz skladista'))
    destination_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT,
                                               related_name='transfers_in', verbose_name=_('U skladiste'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft',
                               verbose_name=_('Status'))
    notes = models.TextField(blank=True, verbose_name=_('Napomena'))
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='created_transfers', verbose_name=_('Kreirao'))
    confirmed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='confirmed_transfers', verbose_name=_('Potvrdio'))
    received_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='received_transfers', verbose_name=_('Zaprimio'))
    confirmed_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Medjuskladisnica')
        verbose_name_plural = _('Medjuskladisnice')
        ordering = ['-date', '-created_at']

    def __str__(self):
        return '%s: %s -> %s' % (self.transfer_number, self.source_warehouse.name, self.destination_warehouse.name)

    def confirm(self, user=None):
        """Potvrdi izdatnicu — razduzi izvor, zadruzi odrediste kad se zaprimi."""
        from django.utils import timezone
        if self.status != 'draft':
            raise ValueError('Samo nacrt se moze potvrditi')
        # Razduzi izvorno skladiste
        for item in self.items.all():
            StockMovement.objects.create(
                company=self.company,
                inventory_item=item.inventory_item,
                movement_type='out',
                quantity=item.quantity,
                reason='Izdatnica %s -> %s' % (self.source_warehouse.name, self.destination_warehouse.name),
                performed_by=user,
            )
        self.status = 'in_transit'
        self.confirmed_by = user
        self.confirmed_at = timezone.now()
        self.save(update_fields=['status', 'confirmed_by', 'confirmed_at'])

        # Activity tracking
        try:
            from worktime.tracker import track
            if user:
                track(user, 'INV', 'TRANSFER_OUT', ref=self.transfer_number,
                      detail='Izdatnica %s -> %s' % (self.source_warehouse.name, self.destination_warehouse.name),
                      company=self.company)
        except Exception:
            pass

    def receive(self, user=None):
        """Zaprimi robu na odredisnom skladistu."""
        from django.utils import timezone
        if self.status != 'in_transit':
            raise ValueError('Samo potvrdjeni prijenos se moze zaprimiti')
        for item in self.items.all():
            StockMovement.objects.create(
                company=self.company,
                inventory_item=item.inventory_item,
                movement_type='in',
                quantity=item.quantity,
                reason='Zaprimljeno iz %s (MS %s)' % (self.source_warehouse.name, self.transfer_number),
                performed_by=user,
            )
        self.status = 'received'
        self.received_by = user
        self.received_at = timezone.now()
        self.save(update_fields=['status', 'received_by', 'received_at'])


class WarehouseTransferItem(models.Model):
    """Stavka medjuskladisnice."""
    transfer = models.ForeignKey(WarehouseTransfer, on_delete=models.CASCADE,
                                  related_name='items', verbose_name=_('Medjuskladisnica'))
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT,
                                        verbose_name=_('Artikl'))
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=1,
                                    verbose_name=_('Kolicina'))
    note = models.CharField(max_length=200, blank=True, verbose_name=_('Napomena'))

    class Meta:
        verbose_name = _('Stavka medjuskladisnice')
        verbose_name_plural = _('Stavke medjuskladisnice')

    def __str__(self):
        return '%s x %s' % (self.inventory_item.name, self.quantity)


# ═══════════════════════════════════════════════════════════════
# INVENTURA — Godišnji popis imovine
# HR: Zakon o računovodstvu čl.11, Pravilnik o popisu
# DE: HGB §240 (Stichtagsinventur), §241 (vereinfachte Inventur)
# ═══════════════════════════════════════════════════════════════

class Inventura(models.Model):
    """
    Glavni dokument inventure (popisa).
    Jedan dokument = jedna inventurna sesija za jedno skladište.
    """
    TYPE_CHOICES = [
        ('annual', _('Godišnji popis')),          # HR čl.11 / DE §240
        ('periodic', _('Periodički popis')),      # DE §241 permanente Inventur
        ('spot', _('Izvanredni popis')),           # Ad-hoc / revizija
        ('sample', _('Stichprobeninventur')),      # DE §241 Abs.1
    ]
    STATUS_CHOICES = [
        ('draft', _('Priprema')),
        ('in_progress', _('U tijeku')),
        ('counting', _('Brojanje')),
        ('completed', _('Završeno')),
        ('approved', _('Odobreno')),
        ('cancelled', _('Poništeno')),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='inventuras', verbose_name=_('Tvrtka'),
    )
    inventura_number = models.CharField(
        max_length=50, blank=True, verbose_name=_('Broj popisa'),
        help_text=_('Auto: INV-YYYY/NNNNN'),
    )
    inventura_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default='annual',
        verbose_name=_('Vrsta popisa'),
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft',
        verbose_name=_('Status'),
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Skladište'),
    )
    date_started = models.DateField(verbose_name=_('Datum početka'))
    date_completed = models.DateField(
        null=True, blank=True, verbose_name=_('Datum završetka'),
    )
    # Pravilnik: popis se radi na datum bilance (31.12.)
    reference_date = models.DateField(
        verbose_name=_('Datum stanja'),
        help_text=_('Datum na koji se utvrđuje stanje (obično 31.12.)'),
    )
    category_filter = models.CharField(
        max_length=20, blank=True, verbose_name=_('Filtar kategorije'),
        help_text=_('Prazno = sve kategorije'),
    )
    notes = models.TextField(blank=True, verbose_name=_('Napomene'))
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='inventuras_created', verbose_name=_('Kreirao'),
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='inventuras_approved', verbose_name=_('Odobrio'),
    )
    approved_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Datum odobrenja'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-date_started', '-created_at']
        verbose_name = _('Inventura')
        verbose_name_plural = _('Inventure')
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'reference_date']),
        ]

    def __str__(self):
        return '%s (%s)' % (self.inventura_number or 'DRAFT', self.get_status_display())

    def save(self, *args, **kwargs):
        if not self.inventura_number:
            self._assign_number()
        super().save(*args, **kwargs)

    def _assign_number(self):
        from datetime import date
        year = self.reference_date.year if self.reference_date else date.today().year
        prefix = 'INV-%d/' % year
        last = (Inventura.objects
                .filter(company=self.company, inventura_number__startswith=prefix)
                .exclude(pk=self.pk)
                .order_by('-inventura_number')
                .values_list('inventura_number', flat=True)
                .first())
        if last:
            try:
                last_num = int(last.split('/')[-1])
            except (ValueError, IndexError):
                last_num = 0
        else:
            last_num = 0
        self.inventura_number = '%s%05d' % (prefix, last_num + 1)

    @property
    def total_items(self):
        return self.items.count()

    @property
    def counted_items(self):
        return self.items.filter(counted_at__isnull=False).count()

    @property
    def progress_percent(self):
        total = self.total_items
        if total == 0:
            return 0
        return round(self.counted_items / total * 100)

    @property
    def total_difference_value(self):
        from decimal import Decimal
        return sum(
            (i.difference_value or Decimal('0'))
            for i in self.items.filter(counted_at__isnull=False)
        )

    @property
    def surplus_count(self):
        return self.items.filter(counted_at__isnull=False, difference_qty__gt=0).count()

    @property
    def shortage_count(self):
        return self.items.filter(counted_at__isnull=False, difference_qty__lt=0).count()

    def start_counting(self):
        """Inicijaliziraj sve stavke iz trenutnog stanja skladišta."""
        if self.status not in ('draft',):
            raise ValueError(_('Inventura je već pokrenuta.'))
        company_items = InventoryItem.objects.filter(
            company=self.company, is_active=True
        )
        if self.category_filter:
            company_items = company_items.filter(category=self.category_filter)
        for item in company_items:
            InventuraItem.objects.get_or_create(
                inventura=self,
                inventory_item=item,
                defaults={
                    'expected_qty': item.quantity,
                    'unit_price': item.purchase_price or item.unit_price,
                    'unit': item.unit,
                },
            )
        self.status = 'counting'
        self.save()

    def complete(self, user=None):
        """Zaključi inventuru — izračunaj razlike."""
        if self.status not in ('counting', 'in_progress'):
            raise ValueError(_('Inventura nije u statusu brojanja.'))
        from datetime import date
        self.status = 'completed'
        self.date_completed = date.today()
        self.save()

        # Activity tracking
        try:
            from worktime.tracker import track
            if user:
                track(user, 'INV', 'INVENTURA_COMPLETE', ref='INV-%d' % self.pk,
                      detail='Inventura zavrsena, %d stavki' % self.items.count(),
                      company=self.company)
        except Exception:
            pass

    def approve_and_adjust(self, user):
        """
        Odobri inventuru i generiraj korekcije zaliha.
        Zakonski: razlike se knjige kao manjak (rashod) ili višak (prihod).
        """
        if self.status != 'completed':
            raise ValueError(_('Inventura mora biti završena prije odobrenja.'))
        from django.utils import timezone
        for inv_item in self.items.filter(counted_at__isnull=False).exclude(difference_qty=0):
            diff = inv_item.difference_qty
            if diff > 0:
                # Višak — adjustment IN
                StockMovement.objects.create(
                    item=inv_item.inventory_item,
                    movement_type='adjustment',
                    quantity=abs(diff),
                    unit_price=inv_item.unit_price,
                    reason='Inventura %s — višak' % self.inventura_number,
                    performed_by=user,
                )
            elif diff < 0:
                # Manjak — adjustment OUT
                StockMovement.objects.create(
                    item=inv_item.inventory_item,
                    movement_type='adjustment',
                    quantity=-abs(diff),
                    unit_price=inv_item.unit_price,
                    reason='Inventura %s — manjak' % self.inventura_number,
                    performed_by=user,
                )
        self.status = 'approved'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()


class InventuraItem(models.Model):
    """Jedna stavka popisa — artikl s očekivanom i stvarnom količinom."""
    inventura = models.ForeignKey(
        Inventura, on_delete=models.CASCADE,
        related_name='items', verbose_name=_('Inventura'),
    )
    inventory_item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT,
        related_name='inventura_items', verbose_name=_('Artikl'),
    )
    # Stanje po knjigama na datum popisa
    expected_qty = models.DecimalField(
        max_digits=10, decimal_places=3, default=0,
        verbose_name=_('Knjižno stanje'),
    )
    # Stvarno prebrojano
    counted_qty = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name=_('Stvarno stanje'),
    )
    # Razlika = counted - expected
    difference_qty = models.DecimalField(
        max_digits=10, decimal_places=3, default=0,
        verbose_name=_('Razlika (kol.)'),
    )
    # Cijena za izračun vrijednosti razlike
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        verbose_name=_('Jedinična cijena'),
    )
    # Vrijednost razlike = difference_qty * unit_price
    difference_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Razlika (iznos)'),
    )
    unit = models.CharField(max_length=20, default='kom', verbose_name=_('JMJ'))
    counted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Prebrojao'),
    )
    counted_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Vrijeme brojanja'),
    )
    barcode_scanned = models.BooleanField(
        default=False, verbose_name=_('Skenirano'),
        help_text=_('Je li artikl identificiran barcode skenerom'),
    )
    note = models.CharField(max_length=255, blank=True, verbose_name=_('Napomena'))

    class Meta:
        ordering = ['inventory_item__name']
        verbose_name = _('Stavka inventure')
        verbose_name_plural = _('Stavke inventure')
        unique_together = [('inventura', 'inventory_item')]

    def __str__(self):
        return '%s: %s → %s' % (
            self.inventory_item.name,
            self.expected_qty,
            self.counted_qty if self.counted_qty is not None else '?',
        )

    def save(self, *args, **kwargs):
        if self.counted_qty is not None:
            from decimal import Decimal
            self.difference_qty = self.counted_qty - self.expected_qty
            self.difference_value = self.difference_qty * (self.unit_price or Decimal('0'))
        super().save(*args, **kwargs)


class InventuraCommission(models.Model):
    """
    Popisna komisija — zakonski obavezna (HR Pravilnik o popisu).
    Minimalno: predsjednik + 2 člana.
    """
    ROLE_CHOICES = [
        ('predsjednik', _('Predsjednik komisije')),
        ('clan', _('Član komisije')),
        ('zapisnicar', _('Zapisničar')),
    ]
    inventura = models.ForeignKey(
        Inventura, on_delete=models.CASCADE,
        related_name='commission', verbose_name=_('Inventura'),
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_('Osoba'),
    )
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default='clan',
        verbose_name=_('Uloga'),
    )

    class Meta:
        verbose_name = _('Član komisije')
        verbose_name_plural = _('Popisna komisija')
        unique_together = [('inventura', 'user')]

    def __str__(self):
        return '%s — %s' % (self.user.get_full_name() or self.user.username, self.get_role_display())
