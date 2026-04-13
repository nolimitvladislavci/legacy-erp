from decimal import Decimal
"""
marketplace/models.py - Grossmarkt Online tržnica

Povezuje OPG proizvođače s restoranima.
Jedan order može sadržavati proizvode od više OPG-ova.
"""
from django.conf import settings
from django.db import models, DatabaseError, IntegrityError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist
from core.managers import CompanyManager


class MarketplaceCategory(models.Model):
    """Kategorija proizvoda na tržnici (Povrće, Voće, Mliječni, Meso...)"""
    name = models.CharField(max_length=100, verbose_name=_('Naziv'))
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=10, default='🥬', verbose_name=_('Emoji'))
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE,
        related_name='children', verbose_name=_('Nadkategorija')
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('Kategorija tržnice')
        verbose_name_plural = _('Kategorije tržnice')
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f"{self.icon} {self.name}"


class MarketplaceProduct(models.Model):
    """Proizvod na tržnici - vezan za OPG (seller_company) i njihov InventoryItem."""
    UNIT_CHOICES = [
        ('kg', 'Kilogram'),
        ('g', 'Gram'),
        ('l', 'Litra'),
        ('kom', 'Komad'),
        ('pakiranje', 'Pakiranje'),
        ('kutija', 'Kutija'),
        ('vreca', 'Vreća'),
    ]

    # Veza na OPG
    seller_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='marketplace_products',
        verbose_name=_('Prodavač (OPG)')
    )
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='marketplace_listings',
        verbose_name=_('Artikl iz skladišta')
    )

    # Osnovni podaci
    name = models.CharField(max_length=200, verbose_name=_('Naziv proizvoda'))
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True, verbose_name=_('Opis'))
    category = models.ForeignKey(
        MarketplaceCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='products',
        verbose_name=_('Kategorija')
    )

    # Cijena i dostupnost
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Cijena'))
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='kg', verbose_name=_('Jedinica'))
    min_order_qty = models.DecimalField(max_digits=8, decimal_places=2, default=1, verbose_name=_('Min. narudžba'))
    available_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Dostupna količina'))
    is_available = models.BooleanField(default=True, verbose_name=_('Dostupno'))

    # Sezonalnost
    seasonal_from = models.DateField(null=True, blank=True, verbose_name=_('Sezona od'))
    seasonal_until = models.DateField(null=True, blank=True, verbose_name=_('Sezona do'))

    # Kvaliteta
    is_organic = models.BooleanField(default=False, verbose_name=_('Ekološki'))
    is_eco_certified = models.BooleanField(default=False, verbose_name=_('Eko certifikat'))
    origin_region = models.CharField(max_length=100, blank=True, verbose_name=_('Regija porijekla'))

    # Mediji
    image_main = models.ImageField(upload_to='marketplace/products/', blank=True, null=True, verbose_name=_('Glavna slika'))

    # Skladištenje
    shelf_life_days = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Rok trajanja (dana)'))
    storage_temp_min = models.IntegerField(null=True, blank=True, verbose_name=_('Min temp skladištenja °C'))
    storage_temp_max = models.IntegerField(null=True, blank=True, verbose_name=_('Max temp skladištenja °C'))
    requires_cold_chain = models.BooleanField(default=False, verbose_name=_('Zahtijeva hladni lanac'))
    # Warehouse safety flags
    is_fragile = models.BooleanField(default=False, verbose_name=_("Krhko (ne trpi tezinu)"))
    is_heavy = models.BooleanField(default=False, verbose_name=_("Tesko (25+ kg)"))

    # Statistika
    is_featured = models.BooleanField(default=False, verbose_name=_('Istaknuto'))
    sort_order = models.PositiveIntegerField(default=0)
    total_sold = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count = models.PositiveIntegerField(default=0)

    # Delivery pricing per product
    delivery_fee_per_unit = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name=_("Dostava po jedinici"),
        help_text=_("Cijena dostave po jedinici (kg/kom). 0 = besplatna."),
    )
    free_delivery_above = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name=_("Besplatna dostava iznad"),
        help_text=_("Besplatna dostava za narudzbe iznad ovog iznosa."),
    )
    pickup_available = models.BooleanField(default=True, verbose_name=_("Osobno preuzimanje"))

    # OPG / Disclaimer (zakonska obveza za hranu)
    opg_number = models.CharField(
        max_length=50, blank=True, verbose_name=_('OPG broj'),
        help_text=_('Obavezno za prehrambene proizvode — Zakon o OPG čl.12')
    )
    disclaimer_text = models.TextField(
        blank=True, verbose_name=_('Disclaimer'),
        default='Proizvod dolazi izravno s OPG-a. Prije konzumacije provjerite alergene i rok trajanja.',
    )

    # MarketplaceBridge metadata
    source_model = models.CharField(max_length=50, blank=True, verbose_name=_('Izvorni model'),
                                     help_text=_('npr. EggRecord, MedProizvodnja'))
    source_id    = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Izvorni ID'))
    auto_listed  = models.BooleanField(default=False, verbose_name=_('Auto-objavljeno'))
    expires_at   = models.DateTimeField(null=True, blank=True, verbose_name=_('Istječe'))
    # Auction fields (for collectible items like pigeons)
    is_auction = models.BooleanField(default=False, verbose_name=_('Aukcija'))
    starting_bid = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name=_('Pocetna cijena'),
    )
    current_bid = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name=_('Trenutna ponuda'),
    )
    bid_count = models.PositiveIntegerField(default=0, verbose_name=_('Broj ponuda'))
    auction_status = models.CharField(
        max_length=20, default='', blank=True,
        choices=[
            ('', _('Nije aukcija')),
            ('active', _('Aktivna')),
            ('ending_soon', _('Zavrsava uskoro')),
            ('sold', _('Prodano')),
            ('no_bids', _('Bez ponuda')),
        ],
        verbose_name=_('Status aukcije'),
    )

    delivery_zone_km = models.PositiveIntegerField(null=True, blank=True,
                                                    verbose_name=_('Zona dostave (km)'),
                                                    help_text=_('Geofencing za kvarljive proizvode'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Proizvod na tržnici')
        verbose_name_plural = _('Proizvodi na tržnici')
        ordering = ['sort_order', '-created_at']
        indexes = [
            models.Index(fields=['seller_company', 'is_available']),
            models.Index(fields=['category', 'is_available']),
        ]

    def __str__(self):
        return f"{self.name} — {self.seller_company.name}"

    @property
    def is_in_season(self):
        if not self.seasonal_from and not self.seasonal_until:
            return True
        today = timezone.now().date()
        if self.seasonal_from and today < self.seasonal_from:
            return False
        if self.seasonal_until and today > self.seasonal_until:
            return False
        return True


class MarketplaceOrder(models.Model):
    """Narudžba restorana - može sadržavati proizvode od više OPG-ova."""
    STATUS_CHOICES = [
        ('pending', _('Na čekanju')),
        ('confirmed', _('Potvrđena')),
        ('collecting', _('Prikupljanje')),
        ('in_transit', _('U dostavi')),
        ('delivered', _('Dostavljena')),
        ('completed', _('Završena')),
        ('cancelled', _('Otkazana')),
    ]

    order_number = models.CharField(max_length=20, unique=True, editable=False)
    buyer_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='marketplace_orders',
        verbose_name=_('Kupac (restoran)')
    )
    buyer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Naručio')
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Financije
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Dostava
    delivery_date_requested = models.DateField(null=True, blank=True, verbose_name=_('Željeni datum dostave'))
    delivery_time_window = models.CharField(max_length=50, blank=True, verbose_name=_('Vremenski prozor'))
    delivery_address = models.CharField(max_length=300, blank=True, verbose_name=_('Adresa dostave'))
    delivery_notes = models.TextField(blank=True, verbose_name=_('Napomena za dostavu'))

    # Veze na delivery modul
    assigned_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_deliveries',
        verbose_name=_('Vozač')
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Recurring orders
    is_recurring = models.BooleanField(default=False, verbose_name=_("Ponavljajuca narudzba"))
    recurring_interval = models.CharField(
        max_length=20, blank=True, default="",
        choices=[
            ("daily", _("Dnevno")),
            ("weekly", _("Tjedno")),
            ("biweekly", _("Svaka 2 tjedna")),
            ("monthly", _("Mjesecno")),
        ],
        verbose_name=_("Interval ponavljanja"),
    )
    recurring_source = models.ForeignKey(
        "self", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="recurring_copies",
        verbose_name=_("Izvorna ponavljajuca narudzba"),
    )
    next_recurring_date = models.DateField(null=True, blank=True, verbose_name=_("Sljedece ponavljanje"))

    # Veza na fakturu
    invoice = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='marketplace_orders',
        verbose_name=_('Faktura')
    )

    # Smart Cart fields
    DELIVERY_METHOD_CHOICES = [
        ('standard', _('Standardna dostava')),
        ('express', _('Express dostava')),
        ('gepek_taxi', _('Gepek / Taxi — hitno')),
        ('pickup', _('Osobno preuzimanje')),
    ]
    delivery_method = models.CharField(
        max_length=20, choices=DELIVERY_METHOD_CHOICES,
        default='standard', verbose_name=_('Nacin dostave')
    )
    requires_cold_chain = models.BooleanField(default=False, verbose_name=_('Zahtijeva hladni lanac'))
    cutoff_acknowledged = models.BooleanField(default=False, verbose_name=_('Cut-off potvrden'))
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Narudžba tržnice')
        verbose_name_plural = _('Narudžbe tržnice')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} — {self.buyer_company.name}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            year = timezone.now().year
            last = MarketplaceOrder.objects.filter(
                order_number__startswith=f"MKT-{year}-"
            ).count()
            self.order_number = f"MKT-{year}-{last + 1:05d}"
        super().save(*args, **kwargs)

    def recalculate(self):
        self.subtotal = sum(i.total for i in self.items.all())
        self.total = self.subtotal + self.delivery_fee
        self.save(update_fields=['subtotal', 'total'])


class MarketplaceOrderItem(models.Model):
    """Stavka narudžbe - veže se na proizvod i na OPG."""
    SELLER_STATUS_CHOICES = [
        ('pending', _('Čeka potvrdu')),
        ('confirmed', _('Potvrđeno')),
        ('preparing', _('U pripremi')),
        ('ready', _('Spremno')),
        ('collected', _('Prikupljeno')),
        ('delivered', _('Dostavljeno')),
        ('rejected', _('Odbijeno')),
    ]

    order = models.ForeignKey(
        MarketplaceOrder, on_delete=models.CASCADE,
        related_name='items', verbose_name=_('Narudžba')
    )
    product = models.ForeignKey(
        MarketplaceProduct, on_delete=models.CASCADE,
        verbose_name=_('Proizvod')
    )
    seller_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        verbose_name=_('Prodavač (OPG)')
    )

    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Količina'))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Jedinična cijena'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    seller_status = models.CharField(max_length=20, choices=SELLER_STATUS_CHOICES, default='pending')

    # Traceability
    lot_number = models.CharField(max_length=50, blank=True, verbose_name=_('Broj šarže'))
    harvest_date = models.DateField(null=True, blank=True, verbose_name=_('Datum berbe'))
    expiry_date = models.DateField(null=True, blank=True, verbose_name=_('Rok trajanja'))

    seller_confirmed_at = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)

    # Warehouse: actual weighed quantity (dynamic pricing)
    actual_quantity = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name=_('Stvarna kolicina (vaganje)')
    )
    actual_total = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name=_('Stvarni iznos (nakon vaganja)')
    )
    packed_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='packed_items',
        verbose_name=_('Pakirao')
    )
    packed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Pakirano'))
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Stavka narudžbe')
        verbose_name_plural = _('Stavke narudžbe')

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"

    @property
    def final_quantity(self):
        return self.actual_quantity if self.actual_quantity is not None else self.quantity

    @property
    def final_total(self):
        return self.actual_total if self.actual_total is not None else self.total

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        if self.actual_quantity is not None:
            self.actual_total = self.actual_quantity * self.unit_price
        super().save(*args, **kwargs)


class SellerSubOrder(models.Model):
    """Sub-narudžba za jednog OPG-a iz veće narudžbe."""
    STATUS_CHOICES = [
        ('pending', _('Čeka potvrdu')),
        ('confirmed', _('Potvrđeno')),
        ('ready', _('Spremno za preuzimanje')),
        ('collected', _('Preuzeto')),
        ('delivered', _('Dostavljeno')),
        ('rejected', _('Odbijeno')),
    ]

    marketplace_order = models.ForeignKey(
        MarketplaceOrder, on_delete=models.CASCADE,
        related_name='sub_orders', verbose_name=_('Glavna narudžba')
    )
    seller_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='seller_sub_orders',
        verbose_name=_('Prodavač (OPG)')
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Financije
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, verbose_name=_('Provizija %'))
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    seller_payout = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Isplata prodavaču'))

    # Pickup
    pickup_address = models.CharField(max_length=300, blank=True, verbose_name=_('Adresa preuzimanja'))
    pickup_time_window = models.CharField(max_length=50, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Preuzeo')
    )

    # Veza na otkupni blok
    purchase_document = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='seller_suborders',
        verbose_name=_('Otkupni dokument')
    )

    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Sub-narudžba prodavača')
        verbose_name_plural = _('Sub-narudžbe prodavača')
        unique_together = ['marketplace_order', 'seller_company']

    def __str__(self):
        return f"SubOrder {self.seller_company.name} — {self.marketplace_order.order_number}"

    def recalculate(self):
        items = MarketplaceOrderItem.objects.filter(
            order=self.marketplace_order,
            seller_company=self.seller_company
        )
        self.subtotal = sum((i.total for i in items), Decimal("0"))
        self.commission_amount = self.subtotal * Decimal(str(self.commission_percent)) / Decimal("100")
        self.seller_payout = self.subtotal - self.commission_amount
        self.save(update_fields=['subtotal', 'commission_amount', 'seller_payout'])


# ── Discount / Rebate System ─────────────────────────────────────────

class PartnerDiscount(models.Model):
    """Tier-based discount between seller and buyer companies."""
    TIER_CHOICES = [
        ('standard', _('Standard (0%)')),
        ('bronze', _('Bronze (10%)')),
        ('silver', _('Silver (15%)')),
        ('gold', _('Gold (20%)')),
        ('platinum', _('Platinum (25%)')),
        ('custom', _('Custom')),
    ]

    seller_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='partner_discounts_given',
        verbose_name=_('Prodavac'),
    )
    buyer_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='partner_discounts_received',
        verbose_name=_('Kupac'),
    )
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='standard',
                            verbose_name=_('Partnerski tier'))
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name=_('Rabat %'),
        help_text=_('Za tier!=custom, koristi se automatski postotak tiera.'),
    )
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Partnerski rabat')
        verbose_name_plural = _('Partnerski rabati')
        unique_together = ['seller_company', 'buyer_company']

    def __str__(self):
        return f"{self.seller_company.name} -> {self.buyer_company.name}: {self.tier}"


class CategoryDiscount(models.Model):
    """Discount per category, optionally targeted to specific buyer."""
    seller_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='category_discounts_given',
    )
    buyer_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='category_discounts_received',
        help_text=_('Prazno = vrijedi za sve kupce.'),
    )
    category = models.ForeignKey(
        MarketplaceCategory, on_delete=models.CASCADE,
        verbose_name=_('Kategorija'),
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name=_('Rabat %'),
    )
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Rabat po kategoriji')
        verbose_name_plural = _('Rabati po kategorijama')

    def __str__(self):
        buyer = self.buyer_company.name if self.buyer_company else 'SVE'
        return f"{self.seller_company.name} -> {buyer}: {self.category.name} -{self.discount_percent}%"


class VolumeDiscount(models.Model):
    """Quantity-break discount. Stacks on top of partner/category discount."""
    seller_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='volume_discounts',
    )
    product = models.ForeignKey(
        MarketplaceProduct, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='volume_discounts',
        help_text=_('Prazno = svi artikli.'),
    )
    category = models.ForeignKey(
        MarketplaceCategory, on_delete=models.CASCADE,
        null=True, blank=True,
        help_text=_('Prazno = sve kategorije.'),
    )
    min_quantity = models.DecimalField(max_digits=10, decimal_places=2,
                                       verbose_name=_('Min. kolicina'))
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name=_('Rabat %'),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Kolicinski rabat')
        verbose_name_plural = _('Kolicinski rabati')
        ordering = ['seller_company', 'min_quantity']

    def __str__(self):
        target = self.product.name if self.product else (self.category.name if self.category else 'SVE')
        return f"{self.seller_company.name}: {self.min_quantity}+ {target} -> -{self.discount_percent}%"


# ── Futures / Pre-Harvest Reservation System ──────────────────────────

class FuturesListing(models.Model):
    """Ponuda za buducu berbu/proizvodnju. OPG objavljuje sto ce imati dostupno."""
    STATUS_CHOICES = [
        ('draft', _('Nacrt')),
        ('open', _('Otvoreno za rezervacije')),
        ('fully_booked', _('Potpuno rezervirano')),
        ('harvesting', _('U berbi / pripremi')),
        ('delivering', _('Isporuka u tijeku')),
        ('completed', _('Zavrseno')),
        ('cancelled', _('Otkazano')),
    ]

    seller_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='futures_listings', verbose_name=_('Prodavac (OPG)'),
    )
    product = models.ForeignKey(
        MarketplaceProduct, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='futures_listings',
        verbose_name=_('Povezani proizvod'),
    )
    category = models.ForeignKey(
        MarketplaceCategory, on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    name = models.CharField(max_length=200, verbose_name=_('Naziv'))
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=20, default='kg')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Garantirana cijena'))
    total_capacity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Ukupni kapacitet'))
    reserved_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Rezervirano'))
    min_order_qty = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name=_('Min. narudzba'))

    available_from = models.DateField(verbose_name=_('Dostupno od'))
    available_until = models.DateField(verbose_name=_('Dostupno do'))
    booking_deadline = models.DateField(verbose_name=_('Rok za rezervaciju'))

    deposit_percent = models.DecimalField(max_digits=5, decimal_places=2, default=20, verbose_name=_('Avans %'))
    origin_region = models.CharField(max_length=100, blank=True, verbose_name=_('Regija'))
    is_organic = models.BooleanField(default=False)
    requires_cold_chain = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    image = models.ImageField(upload_to='marketplace/futures/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Futures ponuda')
        verbose_name_plural = _('Futures ponude')
        ordering = ['available_from', '-created_at']

    def __str__(self):
        return f"{self.name} ({self.seller_company.name}) — {self.available_from}"

    @property
    def available_qty(self):
        return self.total_capacity - self.reserved_qty

    @property
    def percent_reserved(self):
        if self.total_capacity == 0:
            return 0
        return int(self.reserved_qty / self.total_capacity * 100)

    @property
    def is_bookable(self):
        from django.utils import timezone
        today = timezone.now().date()
        return (
            self.status == 'open'
            and today <= self.booking_deadline
            and self.available_qty > 0
        )


class FuturesReservation(models.Model):
    """Rezervacija buduce robe od strane kupca."""
    STATUS_CHOICES = [
        ('pending', _('Ceka potvrdu')),
        ('confirmed', _('Potvrdeno')),
        ('deposit_paid', _('Avans placen')),
        ('ready', _('Roba spremna')),
        ('partially_delivered', _('Djelomicno isporuceno')),
        ('delivered', _('Isporuceno')),
        ('completed', _('Zavrseno')),
        ('cancelled', _('Otkazano')),
    ]
    DELIVERY_CHOICES = [
        ('delivery', _('Dostava')),
        ('pickup', _('Osobno preuzimanje')),
        ('bus', _('Bus linija')),
        ('courier', _('Kurir')),
    ]

    listing = models.ForeignKey(
        FuturesListing, on_delete=models.CASCADE, related_name='reservations',
    )
    buyer_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, related_name='futures_reservations',
    )
    buyer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )

    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Kolicina'))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Garantirana cijena'))
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Avans'))
    deposit_paid = models.BooleanField(default=False, verbose_name=_('Avans placen'))
    deposit_paid_at = models.DateTimeField(null=True, blank=True)

    delivery_preference = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default='delivery')
    delivery_address = models.CharField(max_length=300, blank=True)
    delivery_notes = models.TextField(blank=True)
    recurring_weekly = models.BooleanField(default=False, verbose_name=_('Tjedna isporuka'))

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name=_('Rabat %'))

    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Futures rezervacija')
        verbose_name_plural = _('Futures rezervacije')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.buyer_company.name}: {self.quantity} {self.listing.unit} {self.listing.name}"

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price * (1 - self.discount_percent / Decimal('100'))
        self.deposit_amount = self.total_price * self.listing.deposit_percent / Decimal('100')
        super().save(*args, **kwargs)

    @property
    def remaining_qty(self):
        return self.quantity - self.delivered_qty


class FuturesDeliverySlot(models.Model):
    """Tjedni slot isporuke za recurring futures rezervacije."""
    STATUS_CHOICES = [
        ('scheduled', _('Planirano')),
        ('ready', _('Spremno')),
        ('shipped', _('Poslano')),
        ('delivered', _('Isporuceno')),
        ('skipped', _('Preskoceno')),
    ]

    reservation = models.ForeignKey(
        FuturesReservation, on_delete=models.CASCADE, related_name='delivery_slots',
    )
    scheduled_date = models.DateField(verbose_name=_('Planirani datum'))
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    delivered_at = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = _('Futures isporuka')
        verbose_name_plural = _('Futures isporuke')
        ordering = ['scheduled_date']

    def __str__(self):
        return f"{self.scheduled_date} — {self.quantity} {self.reservation.listing.unit}"


# ── Reklamacija / Complaint ─────────────────────────────────
class OrderComplaint(models.Model):
    """QR-based complaint — buyer scans QR on invoice, files a complaint."""
    REASON_CHOICES = [
        ('damaged', _('Osteceno')),
        ('wrong_item', _('Krivi artikl')),
        ('wrong_qty', _('Kriva kolicina')),
        ('expired', _('Istekao rok')),
        ('temp_breach', _('Prekid hladnog lanca')),
        ('quality', _('Losa kvaliteta')),
        ('other', _('Ostalo')),
    ]
    STATUS_CHOICES = [
        ('open', _('Otvorena')),
        ('acknowledged', _('Primljena')),
        ('replacement_sent', _('Zamjena poslana')),
        ('refunded', _('Povrat novca')),
        ('rejected', _('Odbijena')),
        ('closed', _('Zatvorena')),
    ]

    order = models.ForeignKey(
        MarketplaceOrder, on_delete=models.CASCADE,
        related_name='complaints', verbose_name=_('Narudzba')
    )
    item = models.ForeignKey(
        MarketplaceOrderItem, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='complaints',
        verbose_name=_('Stavka')
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, verbose_name=_('Razlog'))
    description = models.TextField(blank=True, verbose_name=_('Opis problema'))
    photo = models.ImageField(upload_to='marketplace/complaints/', blank=True, null=True, verbose_name=_('Fotografija'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolution_note = models.TextField(blank=True, verbose_name=_('Biljeska o rjesenju'))

    # Auto-storno
    storno_invoice = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='complaint_stornos',
        verbose_name=_('Storno racun')
    )
    replacement_order = models.ForeignKey(
        MarketplaceOrder, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='replacement_for_complaints',
        verbose_name=_('Zamjenska narudzba')
    )

    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Prijavio')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _('Reklamacija')
        verbose_name_plural = _('Reklamacije')
        ordering = ['-created_at']

    def __str__(self):
        return f"Reklamacija #{self.pk} — {self.order.order_number} ({self.get_reason_display()})"


# ── WhatsApp Concierge: Cart Snapshot ──────────────────────
class CartSnapshot(models.Model):
    """
    Frozen cart state for WhatsApp/SMS share links.
    Security: token expires in 60min, cart_hash prevents race conditions.
    Scenario 2.1: Token expiration (403 after TTL).
    Scenario 2.2: cart_hash mismatch blocks stale payments.
    """
    token = models.CharField(max_length=64, unique=True, db_index=True)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='cart_snapshots', verbose_name=_('Tvrtka kupca')
    )
    cart_data = models.JSONField(verbose_name=_('Snapshot kosrice'))
    cart_hash = models.CharField(max_length=64, verbose_name=_('SHA-256 hash stanja'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Security
    expires_at = models.DateTimeField(verbose_name=_('Istice'))
    is_used = models.BooleanField(default=False, verbose_name=_('Iskoristen'))

    # Delivery
    delivery_address = models.CharField(max_length=300, blank=True)
    delivery_method = models.CharField(max_length=20, default='standard')
    notes = models.TextField(blank=True)

    # Result
    order = models.ForeignKey(
        MarketplaceOrder, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='from_snapshot',
        verbose_name=_('Kreirana narudzba')
    )

    # WA delivery status
    wa_message_id = models.CharField(max_length=100, blank=True)
    wa_sent = models.BooleanField(default=False)
    wa_fallback_used = models.CharField(max_length=20, blank=True)  # sms, email, none

    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Kreirao (dispeeer)')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Cart Snapshot')
        verbose_name_plural = _('Cart Snapshots')
        ordering = ['-created_at']

    def __str__(self):
        return f"Snapshot {self.token[:8]}... -> {self.company.name}"

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_expired and not self.is_used

    @staticmethod
    def generate_token():
        import secrets
        return secrets.token_urlsafe(32)

    @staticmethod
    def compute_hash(cart_data):
        import hashlib, json
        raw = json.dumps(cart_data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()


# ── Auction System (Golublja aukcija) ────────────────────────────────

class AuctionBid(models.Model):
    """Licitacija na aukciji — golubovi i drugi collectible itemi."""
    product = models.ForeignKey(
        MarketplaceProduct, on_delete=models.CASCADE,
        related_name='bids', verbose_name=_('Proizvod'),
    )
    bidder_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='auction_bids', verbose_name=_('Licitant'),
    )
    bidder_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Korisnik'),
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name=_('Iznos (EUR)'),
    )
    is_winning = models.BooleanField(default=False, verbose_name=_('Pobjednička'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Aukcijska ponuda')
        verbose_name_plural = _('Aukcijske ponude')
        ordering = ['-amount', '-created_at']
        indexes = [
            models.Index(fields=['product', '-amount']),
        ]

    def __str__(self):
        return f"{self.bidder_company.name}: {self.amount} EUR -> {self.product.name}"

    @property
    def is_highest(self):
        top = self.product.bids.order_by('-amount').first()
        return top and top.pk == self.pk
