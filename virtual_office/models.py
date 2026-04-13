"""
Virtualni Ured — Klijentski dashboard za skeniranu postu i dokumente.
App: virtual_office/
"""

from django.conf import settings
from django.db import models

from core.managers import CompanyManager


class VirtualMailbox(models.Model):
    """Per-company virtual office konfiguracija."""

    company = models.OneToOneField("companies.Company", on_delete=models.CASCADE, related_name="virtual_mailbox")
    is_active = models.BooleanField(default=True)
    address_line = models.CharField(
        max_length=255, blank=True, help_text="Adresa virtualnog ureda (npr. Kappa centar, Cepin)"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Virtualni pretinac"
        verbose_name_plural = "Virtualni pretinci"

    def __str__(self):
        return f"Pretinac: {self.company.name}"


class IncomingMail(models.Model):
    """Pristigla posta — skenirana i pohranjena."""

    STATUS_CHOICES = [
        ("received", "Zaprimljeno"),
        ("scanned", "Skenirano"),
        ("forwarded", "Proslijedjeno"),
        ("archived", "Arhivirano"),
    ]
    MAIL_TYPE_CHOICES = [
        ("letter", "Pismo"),
        ("invoice", "Racun"),
        ("notice", "Obavijest"),
        ("tax", "Porezna uprava"),
        ("court", "Sud / Odvjetnik"),
        ("bank", "Banka"),
        ("insurance", "Osiguranje"),
        ("package", "Paket"),
        ("other", "Ostalo"),
    ]

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="incoming_mail")
    received_date = models.DateField()
    sender = models.CharField(max_length=255, blank=True, help_text="Posiljatelj (ako je vidljivo na omotnici)")
    mail_type = models.CharField(max_length=20, choices=MAIL_TYPE_CHOICES, default="letter")
    subject = models.CharField(max_length=255, blank=True, help_text="Kratak opis sadrzaja")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="received")

    # Skenirani dokument
    scanned_file = models.FileField(upload_to="virtual_office/scans/%Y/%m/", blank=True)
    scan_pages = models.PositiveIntegerField(default=0)

    # Tko je obradio
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_mail"
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    # Klijent je pregledao?
    client_viewed = models.BooleanField(default=False)
    client_viewed_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        ordering = ["-received_date", "-created_at"]
        verbose_name = "Pristigla posta"
        verbose_name_plural = "Pristigla posta"

    def __str__(self):
        return f"{self.get_mail_type_display()}: {self.sender or 'Nepoznat'} ({self.received_date})"


class MailNotification(models.Model):
    """Obavijest klijentu o novoj posti."""

    mail = models.ForeignKey(IncomingMail, on_delete=models.CASCADE, related_name="notifications")
    sent_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(
        max_length=20,
        choices=[
            ("email", "E-mail"),
            ("sms", "SMS"),
            ("push", "Push obavijest"),
        ],
    )
    sent_to = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Obavijest o posti"
        verbose_name_plural = "Obavijesti o posti"
