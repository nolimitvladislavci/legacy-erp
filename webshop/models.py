from django.db import models
from core.managers import CompanyManager


class Product(models.Model):
    """
    Polymorphic Product — single model for ALL domains.
    FOOD: HACCP expiry, packaging enforcement, kalo
    OPTICS: medical attributes (SPH, CYL), no HACCP
    EQUIPMENT: standard stock, no special rules
    SERVICE: no stock tracking
    """
    CATEGORY_CHOICES = [
        ('FOOD', 'Hrana / Grosmarkt'),
        ('OPTICS', 'Optika / Medicinski'),
        ('EQUIPMENT', 'Oprema / Alat'),
        ('SERVICE', 'Usluga'),
        ('OTHER', 'Ostalo'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='webshop_products',
        verbose_name='Tvrtka',
    )
    sku = models.CharField(max_length=100, unique=True, verbose_name='SKU')
    name = models.CharField(max_length=300, verbose_name='Naziv')
    description = models.TextField(blank=True, verbose_name='Opis')
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='OTHER',
        verbose_name='Domenski tip',
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Cijena')
    stock = models.IntegerField(default=0, verbose_name='Zaliha (legacy)')
    available_qty = models.IntegerField(default=0, verbose_name='Dostupna kolicina')
    is_rental = models.BooleanField(default=False, verbose_name='Za iznajmljivanje')
    is_active = models.BooleanField(default=True, verbose_name='Aktivno')
    image = models.ImageField(upload_to='products/', blank=True, verbose_name='Slika')
    inventory_item = models.OneToOneField(
        'inventory.InventoryItem',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='webshop_product',
        verbose_name='Artikl iz zalihe',
    )

    # Domain-specific JSONB attributes
    # FOOD: {"kalo_percent": 2.0}
    # OPTICS: {"requires_sph": true, "requires_cyl": false, "requires_ax": false}
    domain_attrs = models.JSONField(default=dict, blank=True, verbose_name='Domenski atributi')

    # FOOD-specific
    expiry_date = models.DateField(null=True, blank=True, verbose_name='Rok trajanja')
    packaging_unit = models.CharField(max_length=50, blank=True, verbose_name='Ambalaza')
    packaging_capacity_kg = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Kapacitet ambalaze (kg)',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        db_table = 'webshop_product'
        verbose_name = 'Proizvod'
        verbose_name_plural = 'Proizvodi'
        ordering = ['name']

    def __str__(self):
        return f"[{self.category}] {self.name} ({self.sku})"

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        from datetime import date
        return self.expiry_date < date.today()

    @property
    def is_food(self):
        return self.category == 'FOOD'

    @property
    def is_optics(self):
        return self.category == 'OPTICS'


class CartItem(models.Model):
    """Cart item with hard-lock stock reservation via select_for_update."""
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True,
    )
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.IntegerField(default=1)
    item_attributes = models.JSONField(default=dict, blank=True,
        verbose_name='Atributi stavke (SPH, CYL, itd.)')
    locked_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = 'Stavka kosrice'
        verbose_name_plural = 'Stavke kosrice'

    def __str__(self):
        return f"{self.user.username}: {self.product.name} x{self.quantity}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Na cekanju'),
        ('confirmed', 'Potvrdjeno'),
        ('processing', 'U obradi'),
        ('shipped', 'Poslano'),
        ('delivered', 'Dostavljeno'),
        ('cancelled', 'Otkazano'),
    ]
    SHIPPING_CHOICES = [
        ('osobni_preuzimanje', 'Osobno preuzimanje'),
        ('dostava', 'Dostava'),
        ('dpd', 'DPD'),
        ('hp', 'Hrvatska Posta'),
    ]
    order_number = models.CharField(max_length=50, unique=True, verbose_name='Broj narudzbe')
    customer = models.ForeignKey('partners.Partner', on_delete=models.CASCADE,
                                  related_name='orders', verbose_name='Kupac')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Status')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Ukupni iznos')
    notes = models.TextField(blank=True, verbose_name='Napomene')
    shipping_address = models.TextField(blank=True, verbose_name='Adresa dostave')
    shipping_method = models.CharField(max_length=50, choices=SHIPPING_CHOICES,
                                        default='osobni_preuzimanje', verbose_name='Nacin dostave')
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name='Broj pracenja')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'webshop_order'
        verbose_name = 'Narudzba'
        verbose_name_plural = 'Narudzbe'
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.order_number} - {self.customer.name} ({self.total_amount} EUR)"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Narudzba')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Proizvod')
    quantity = models.IntegerField(default=1, verbose_name='Kolicina')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Jedinicna cijena')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Ukupno')

    class Meta:
        db_table = 'webshop_orderitem'
        verbose_name = 'Stavka narudzbe'
        verbose_name_plural = 'Stavke narudzbe'

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"
