"""
Eldercare Light -- Dom za starije (bez CEZIH / HZZO / med. podataka).

CRVENE LINIJE -- NE DIRATI:
  - Evidencija lijekova (cl.9 GDPR, posebna kategorija)
  - Medicinski karton
  - CEZIH integracija
  - HZZO fakturiranje

Light moduli:
  Resident -- Korisnik doma
  Relative -- Srodnik / kontakt osoba
  Room -- Sobe
  MonthlyCharge -- Mjesecna naplata
  StaffShift -- Raspored smjena osoblja
  Activity -- Dnevne aktivnosti (NE medicinske)
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

from core.managers import CompanyManager

User = get_user_model()


class Room(models.Model):
    """Soba u domu."""
    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="eldercare_rooms",
    )
    number = models.CharField(max_length=20, verbose_name=_("Broj sobe"))
    floor = models.PositiveSmallIntegerField(default=0, verbose_name=_("Kat"))
    capacity = models.PositiveSmallIntegerField(default=2, verbose_name=_("Kapacitet"))
    room_type = models.CharField(
        max_length=20,
        choices=[
            ("single", _("Jednokrevetna")),
            ("double", _("Dvokrevetna")),
            ("triple", _("Trokrevetna")),
            ("suite", _("Apartman")),
        ],
        default="double",
    )
    monthly_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("800.00"),
        verbose_name=_("Mjesecna cijena (EUR)"),
    )
    is_available = models.BooleanField(default=True)

    objects = CompanyManager()

    class Meta:
        app_label = "eldercare"
        ordering = ["floor", "number"]
        verbose_name = _("Soba")
        verbose_name_plural = _("Sobe")

    def __str__(self):
        return f"Soba {self.number} (kat {self.floor})"

    @property
    def occupant_count(self):
        return self.residents.filter(status="active").count()

    @property
    def is_full(self):
        return self.occupant_count >= self.capacity


class Resident(models.Model):
    """Korisnik doma -- NE sadrzi medicinske podatke."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Aktivan")
        DISCHARGED = "discharged", _("Otpusten")
        DECEASED = "deceased", _("Preminuo")
        WAITLIST = "waitlist", _("Lista cekanja")

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="eldercare_residents",
    )
    first_name = models.CharField(max_length=100, verbose_name=_("Ime"))
    last_name = models.CharField(max_length=100, verbose_name=_("Prezime"))
    date_of_birth = models.DateField(verbose_name=_("Datum rodjenja"))
    oib = models.CharField(max_length=13, blank=True, verbose_name="OIB")
    gender = models.CharField(
        max_length=1, choices=[("M", _("Musko")), ("F", _("Zensko"))], blank=True,
    )

    room = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="residents", verbose_name=_("Soba"),
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ACTIVE,
    )
    admission_date = models.DateField(null=True, blank=True, verbose_name=_("Datum prijema"))
    discharge_date = models.DateField(null=True, blank=True, verbose_name=_("Datum otpusta"))

    emergency_contact_name = models.CharField(
        max_length=200, blank=True, verbose_name=_("Hitni kontakt - ime"),
    )
    emergency_contact_phone = models.CharField(
        max_length=30, blank=True, verbose_name=_("Hitni kontakt - telefon"),
    )

    dietary_requirements = models.TextField(
        blank=True, verbose_name=_("Prehrambeni zahtjevi"),
        help_text=_("Za kuhinju - NE medicinski karton"),
    )
    mobility_notes = models.CharField(
        max_length=200, blank=True, verbose_name=_("Pokretnost"),
        help_text=_("Npr. kolica, hodalica, samostalan"),
    )

    gdpr_consent = models.BooleanField(default=False, verbose_name=_("GDPR pristanak"))
    gdpr_consent_date = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True, verbose_name=_("Biljeske"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CompanyManager()

    class Meta:
        app_label = "eldercare"
        ordering = ["last_name", "first_name"]
        verbose_name = _("Korisnik doma")
        verbose_name_plural = _("Korisnici doma")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        today = timezone.now().date()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


class Relative(models.Model):
    """Srodnik / kontakt osoba korisnika doma."""

    class Relation(models.TextChoices):
        CHILD = "child", _("Sin/Kci")
        SPOUSE = "spouse", _("Suprug/a")
        SIBLING = "sibling", _("Brat/Sestra")
        GRANDCHILD = "grandchild", _("Unuk/a")
        LEGAL_GUARDIAN = "guardian", _("Zakonski skrbnik")
        OTHER = "other", _("Ostalo")

    resident = models.ForeignKey(
        Resident, on_delete=models.CASCADE, related_name="relatives",
    )
    first_name = models.CharField(max_length=100, verbose_name=_("Ime"))
    last_name = models.CharField(max_length=100, verbose_name=_("Prezime"))
    relation = models.CharField(
        max_length=15, choices=Relation.choices, default=Relation.CHILD,
    )
    phone = models.CharField(max_length=30, verbose_name=_("Telefon"))
    phone_secondary = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=300, blank=True)

    is_primary_contact = models.BooleanField(default=False, verbose_name=_("Primarni kontakt"))
    is_billing_contact = models.BooleanField(default=False, verbose_name=_("Prima racune"))
    can_visit = models.BooleanField(default=True, verbose_name=_("Ovlasten za posjete"))

    class Meta:
        app_label = "eldercare"
        ordering = ["-is_primary_contact", "last_name"]
        verbose_name = _("Srodnik")
        verbose_name_plural = _("Srodnici")

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_relation_display()})"


class MonthlyCharge(models.Model):
    """Mjesecna naplata boravka."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Nacrt")
        SENT = "sent", _("Poslano")
        PAID = "paid", _("Placeno")
        OVERDUE = "overdue", _("Dospjelo")

    resident = models.ForeignKey(
        Resident, on_delete=models.CASCADE, related_name="charges",
    )
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()

    base_amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Osnovni iznos"),
    )
    extras = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_("Dodaci (pranje, frizerka...)"),
    )
    deductions = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_("Odbitci (odsutnost)"),
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Ukupno"),
    )

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT,
    )
    due_date = models.DateField(null=True, blank=True, verbose_name=_("Rok placanja"))
    paid_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=30, blank=True)

    invoice = models.ForeignKey(
        "invoicing.Invoice", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="eldercare_charges",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "eldercare"
        unique_together = ["resident", "year", "month"]
        ordering = ["-year", "-month"]
        verbose_name = _("Mjesecna naplata")
        verbose_name_plural = _("Mjesecne naplate")

    def __str__(self):
        return f"{self.resident} - {self.month}/{self.year} - {self.total_amount} EUR"

    def calculate(self):
        if self.resident.room:
            self.base_amount = self.resident.room.monthly_price
        self.total_amount = self.base_amount + self.extras - self.deductions


class StaffShift(models.Model):
    """Raspored smjena osoblja."""

    class ShiftType(models.TextChoices):
        MORNING = "morning", _("Jutarnja (06-14)")
        AFTERNOON = "afternoon", _("Popodnevna (14-22)")
        NIGHT = "night", _("Nocna (22-06)")
        DAY = "day", _("Dnevna (07-19)")

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="eldercare_shifts",
    )
    staff_member = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="eldercare_shifts",
    )
    date = models.DateField(verbose_name=_("Datum"))
    shift_type = models.CharField(
        max_length=10, choices=ShiftType.choices, default=ShiftType.MORNING,
    )
    notes = models.CharField(max_length=200, blank=True)

    objects = CompanyManager()

    class Meta:
        app_label = "eldercare"
        unique_together = ["staff_member", "date"]
        ordering = ["-date", "shift_type"]
        verbose_name = _("Smjena")
        verbose_name_plural = _("Smjene")

    def __str__(self):
        return f"{self.staff_member.get_full_name()} - {self.date} - {self.get_shift_type_display()}"


class Activity(models.Model):
    """Dnevna aktivnost korisnika -- NE medicinska."""

    class Category(models.TextChoices):
        SOCIAL = "social", _("Drustvena")
        PHYSICAL = "physical", _("Tjelesna")
        CREATIVE = "creative", _("Kreativna")
        OUTING = "outing", _("Izlet")
        SPIRITUAL = "spiritual", _("Duhovna")
        OTHER = "other", _("Ostalo")

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="eldercare_activities",
    )
    title = models.CharField(max_length=200, verbose_name=_("Naziv"))
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=12, choices=Category.choices, default=Category.SOCIAL,
    )
    date = models.DateField(verbose_name=_("Datum"))
    time_from = models.TimeField(null=True, blank=True, verbose_name=_("Od"))
    time_to = models.TimeField(null=True, blank=True, verbose_name=_("Do"))

    participants = models.ManyToManyField(
        Resident, blank=True, related_name="activities",
        verbose_name=_("Sudionici"),
    )
    organizer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Organizator"),
    )

    objects = CompanyManager()

    class Meta:
        app_label = "eldercare"
        ordering = ["-date", "time_from"]
        verbose_name = _("Aktivnost")
        verbose_name_plural = _("Aktivnosti")

    def __str__(self):
        return f"{self.title} - {self.date}"
