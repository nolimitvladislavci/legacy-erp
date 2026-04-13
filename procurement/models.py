from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ("draft", _("Nacrt")),
        ("sent", _("Poslano")),
        ("confirmed", _("Potvrdjeno")),
        ("partial", _("Djelomicno isporuceno")),
        ("received", _("Isporuceno")),
        ("invoiced", _("Fakturirano")),
        ("cancelled", _("Otkazano")),
    ]
    PRIORITY_CHOICES = [
        ("low", _("Nizak")),
        ("normal", _("Normalan")),
        ("high", _("Visok")),
        ("urgent", _("Hitno")),
    ]
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, null=True, blank=True)
    objects = CompanyManager()
    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(
        "partners.Partner", on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="normal")
    order_date = models.DateField(default=timezone.now)
    expected_delivery = models.DateField(null=True, blank=True)
    actual_delivery = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default="")
    internal_note = models.TextField(blank=True, default="")
    matched_invoice = models.ForeignKey(
        "invoicing.Invoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="matched_po"
    )
    match_status = models.CharField(
        max_length=20,
        choices=[
            ("unmatched", "Neupareno"),
            ("matched", "Upareno"),
            ("mismatch", "Nepodudaranje"),
            ("approved", "Odobreno"),
        ],
        default="unmatched",
    )
    match_diff_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="po_created")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="po_approved")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Narudzbenica"
        verbose_name_plural = "Narudzbenice"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.po_number} - {self.supplier or 'N/A'}"

    def generate_po_number(self):
        year = timezone.now().year
        last = PurchaseOrder.objects.filter(po_number__startswith=f"PO-{year}-").order_by("-po_number").first()
        seq = 1
        if last:
            try:
                seq = int(last.po_number.split("-")[-1]) + 1
            except Exception:
                pass
        return f"PO-{year}-{seq:04d}"

    def recalculate(self):
        from django.db.models import Sum

        agg = self.items.aggregate(sub=Sum("line_total"), tax=Sum("line_tax"))
        self.subtotal = agg["sub"] or 0
        self.tax_amount = agg["tax"] or 0
        self.total = self.subtotal + self.tax_amount
        self.save(update_fields=["subtotal", "tax_amount", "total", "updated_at"])


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    inventory_item = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=500)
    sku = models.CharField(max_length=50, blank=True, default="")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20, default="kom")
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=25)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    class Meta:
        verbose_name = "Stavka narudzbenice"

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        self.line_tax = self.line_total * (self.tax_rate / __import__("decimal").Decimal("100"))
        super().save(*args, **kwargs)


class SupplierPriceList(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, null=True, blank=True)
    objects = CompanyManager()
    supplier = models.ForeignKey("partners.Partner", on_delete=models.CASCADE, related_name="price_lists")
    inventory_item = models.ForeignKey("inventory.InventoryItem", on_delete=models.CASCADE)
    agreed_price = models.DecimalField(max_digits=12, decimal_places=4)
    valid_from = models.DateField(default=timezone.now)
    valid_until = models.DateField(null=True, blank=True)
    min_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cjenik dobavljaca"
        unique_together = ["supplier", "inventory_item", "valid_from"]
