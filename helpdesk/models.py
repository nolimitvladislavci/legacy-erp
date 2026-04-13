import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


class Ticket(models.Model):
    CATEGORY_CHOICES = [
        ("delivery", _("Dostava")),
        ("quality", _("Kvaliteta robe")),
        ("invoice", _("Racun")),
        ("pos", _("POS/Blagajna")),
        ("technical", _("Tehnicki problem")),
        ("complaint", _("Reklamacija")),
        ("feature", _("Zahtjev")),
        ("other", _("Ostalo")),
    ]
    PRIORITY_CHOICES = [
        ("low", _("Nizak")),
        ("normal", _("Normalan")),
        ("high", _("Visok")),
        ("urgent", _("Hitno")),
        ("critical", _("Kriticno")),
    ]
    STATUS_CHOICES = [
        ("open", _("Otvoren")),
        ("in_progress", _("U obradi")),
        ("waiting_client", _("Ceka klijenta")),
        ("waiting_internal", _("Ceka interni tim")),
        ("resolved", _("Rijesen")),
        ("closed", _("Zatvoren")),
    ]
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, null=True, blank=True)
    objects = CompanyManager()
    ticket_number = models.CharField(max_length=20, unique=True)
    subject = models.CharField(max_length=300)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="normal")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    source = models.CharField(
        max_length=20,
        choices=[
            ("portal", "Portal"),
            ("email", "Email"),
            ("phone", "Telefon"),
            ("whatsapp", "WhatsApp"),
            ("internal", "Interni"),
        ],
        default="internal",
    )
    client = models.ForeignKey(
        "partners.Partner", on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets"
    )
    contact_name = models.CharField(max_length=200, blank=True, default="")
    contact_email = models.CharField(max_length=254, blank=True, default="")
    contact_phone = models.CharField(max_length=50, blank=True, default="")
    related_invoice = models.ForeignKey(
        "invoicing.Invoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets"
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets"
    )
    sla_deadline = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    satisfaction_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    satisfaction_comment = models.TextField(blank=True, default="")
    portal_token = models.UUIDField(default=uuid.uuid4, unique=True)
    tags = models.CharField(max_length=500, blank=True, default="")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tiket"
        verbose_name_plural = "Tiketi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.ticket_number} - {self.subject}"

    def generate_ticket_number(self):
        year = timezone.now().year
        last = Ticket.objects.filter(ticket_number__startswith=f"TK-{year}-").order_by("-ticket_number").first()
        seq = 1
        if last:
            try:
                seq = int(last.ticket_number.split("-")[-1]) + 1
            except Exception:
                pass
        return f"TK-{year}-{seq:04d}"

    @property
    def is_overdue(self):
        if self.sla_deadline and self.status not in ("resolved", "closed"):
            return timezone.now() > self.sla_deadline
        return False

    def set_sla(self):
        hours_map = {"critical": 2, "urgent": 4, "high": 8, "normal": 24, "low": 72}
        hours = hours_map.get(self.priority, 24)
        self.sla_deadline = timezone.now() + timezone.timedelta(hours=hours)


class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    sender_name = models.CharField(max_length=200, blank=True, default="")
    is_internal = models.BooleanField(default=False)
    is_from_client = models.BooleanField(default=False)
    body = models.TextField()
    attachment = models.FileField(upload_to="helpdesk/attachments/%Y/%m/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class TicketTemplate(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, null=True, blank=True)
    objects = CompanyManager()
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=Ticket.CATEGORY_CHOICES, default="other")
    body = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class VIPContact(models.Model):
    """WhatsApp VIP kontakti — automatski prioritet i routing za helpdesk tikete."""

    PRIORITY_CHOICES = Ticket.PRIORITY_CHOICES

    phone = models.CharField(max_length=50, unique=True, help_text="Bez + i razmaka, npr. 385976091655")
    name = models.CharField(max_length=200)
    note = models.CharField(max_length=500, blank=True, default="")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="critical")
    auto_assign_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, help_text="Automatski dodijeli tiket ovom korisniku"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "VIP kontakt"
        verbose_name_plural = "VIP kontakti"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (+{self.phone}) — {self.get_priority_display()}"
