"""
Ugovori za korisnike portala — ServiceAgreement model.

Svaki pretplatnik mora imati potpisani ugovor koji definira:
- Tko je pružatelj usluge (Konjik d.o.o. ili Viskovic Bau)
- Tko je korisnik (firma pretplatnika)
- Koji paket/plan
- Uvjeti korištenja, plaćanja, otkazivanja
- GDPR suglasnost
- Digitalni potpis (datum + IP + user)

Dva pravna entiteta:
  HR klijenti → Konjik d.o.o. (OIB: 37590751921, Čepin)
  DE klijenti → Viskovic Bau (StNr: 56447/32919, Herrenberg)
               ILI Konjik d.o.o. ako Viskovic nema Softwarevertrieb
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ServiceProvider(models.Model):
    """Pravni entitet koji pruža uslugu (izdaje ugovor/račun)."""

    slug = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=200)
    legal_form = models.CharField(max_length=50)  # d.o.o., GmbH, etc.
    tax_id = models.CharField(max_length=50)  # OIB or Steuernummer
    vat_id = models.CharField(max_length=30, blank=True)  # HR VAT or USt-IdNr
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2)  # HR, DE
    iban = models.CharField(max_length=34)
    swift = models.CharField(max_length=11, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    represented_by = models.CharField(max_length=200, blank=True, help_text="Zastupnik/Geschäftsführer")

    # Sposobnost — može li izdavati software licence
    can_sell_software = models.BooleanField(default=False, help_text="Ima registriranu djelatnost prodaje softwera")
    gewerbeschein_note = models.TextField(blank=True, help_text="Status Gewerbeschein / Izvod iz sudskog registra")

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "registration_service_provider"
        verbose_name = "Pružatelj usluge"
        verbose_name_plural = "Pružatelji usluge"

    def __str__(self):
        return f"{self.name} ({self.country})"


class ServiceAgreement(models.Model):
    """Ugovor o korištenju LIMIT Connect platforme."""

    class AgreementType(models.TextChoices):
        SUBSCRIPTION = "subscription", "Pretplata (mjesečna/godišnja)"
        TRIAL = "trial", "Probno razdoblje"
        FREE = "free", "Besplatni paket"
        BOOKKEEPING = "bookkeeping", "Vođenje knjigovodstva (Marija)"
        RESELLER = "reseller", "Reseller / distributer"

    class Status(models.TextChoices):
        DRAFT = "draft", "Nacrt"
        SENT = "sent", "Poslan klijentu"
        SIGNED = "signed", "Potpisan"
        ACTIVE = "active", "Aktivan"
        SUSPENDED = "suspended", "Suspendiran"
        CANCELLED = "cancelled", "Otkazan"
        EXPIRED = "expired", "Istekao"

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", "Žiroračun / Überweisung"
        STRIPE = "stripe", "Stripe (kartica)"
        SEPA_DD = "sepa_dd", "SEPA Direct Debit"
        CASH = "cash", "Gotovina"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Strane ugovora
    provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.PROTECT,
        related_name="agreements",
        help_text="Pružatelj usluge (Konjik ili Viskovic Bau)",
    )
    client_company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="service_agreements",
    )
    subscription = models.ForeignKey(
        "registration.CompanySubscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agreements",
    )

    # Tip i status
    agreement_type = models.CharField(max_length=15, choices=AgreementType.choices, default=AgreementType.SUBSCRIPTION)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    agreement_number = models.CharField(max_length=30, unique=True)

    # Razdoblje
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    notice_period_days = models.PositiveIntegerField(default=30, help_text="Otkazni rok u danima")

    # Financije
    monthly_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="EUR")
    payment_method = models.CharField(max_length=15, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER)
    billing_email = models.EmailField(blank=True)

    # Uvjeti
    terms_version = models.CharField(max_length=20, default="2026.1", help_text="Verzija Općih uvjeta korištenja")
    gdpr_consent = models.BooleanField(default=False)
    gdpr_consent_at = models.DateTimeField(null=True, blank=True)

    # Digitalni potpis
    signed_by_name = models.CharField(max_length=200, blank=True)
    signed_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signed_agreements",
    )
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_ip = models.GenericIPAddressField(null=True, blank=True)

    # PDF ugovor
    pdf_file = models.FileField(upload_to="agreements/%Y/%m/", blank=True)

    # Bilješke
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "registration_service_agreement"
        ordering = ["-created_at"]
        verbose_name = "Ugovor o usluzi"
        verbose_name_plural = "Ugovori o usluzi"

    def __str__(self):
        return f"{self.agreement_number} — {self.client_company.name} ({self.get_status_display()})"

    @property
    def is_valid(self):
        today = timezone.now().date()
        if self.valid_until and today > self.valid_until:
            return False
        return self.status in ("signed", "active")


class CompanyDocument(models.Model):
    """Dokumenti firme — Gewerbeschein, Izvod, Rješenje, certifikati."""

    class DocType(models.TextChoices):
        GEWERBESCHEIN = "gewerbeschein", "Gewerbeschein"
        HANDELSREGISTER = "handelsregister", "Handelsregisterauszug"
        IZVOD_SUDSKOG = "izvod_sudskog", "Izvod iz sudskog registra"
        RJESENJE = "rjesenje", "Rješenje o upisu"
        OIB_POTVRDA = "oib_potvrda", "Potvrda o OIB-u"
        FINA_CERT = "fina_cert", "FINA certifikat"
        OTHER = "other", "Ostalo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="company_documents",
    )
    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="company_docs/%Y/%m/")
    issue_date = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "registration_company_document"
        ordering = ["-created_at"]
        verbose_name = "Dokument firme"
        verbose_name_plural = "Dokumenti firme"

    def __str__(self):
        return f"{self.get_doc_type_display()}: {self.title}"
