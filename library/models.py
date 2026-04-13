"""
LIMIT e-Knjiznica — Kompletni knjiznicni sustav.

Fizicka posudba + digitalni katalog + ISBN auto-fill + QR clanarine
+ Import Wizard + AI preporuke + buduci CDL framework.

"Jedan covjek na enteru — AI radi ostalo."
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager

User = get_user_model()


# ══════════════════════════════════════════════════════════
# KATALOG
# ══════════════════════════════════════════════════════════


class Author(models.Model):
    """Autor knjige."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="lib_authors",
    )
    first_name = models.CharField(max_length=100, verbose_name=_("Ime"))
    last_name = models.CharField(max_length=100, verbose_name=_("Prezime"))
    bio = models.TextField(blank=True, verbose_name=_("Biografija"))
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    death_year = models.PositiveSmallIntegerField(null=True, blank=True)
    openlibrary_id = models.CharField(max_length=50, blank=True, db_index=True)

    objects = CompanyManager()

    class Meta:
        app_label = "library"
        ordering = ["last_name", "first_name"]
        verbose_name = _("Autor")
        verbose_name_plural = _("Autori")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_public_domain(self):
        """Djelo u javnoj domeni ako je autor umro prije 70+ godina."""
        if self.death_year:
            return (timezone.now().year - self.death_year) >= 70
        return False


class Category(models.Model):
    """Kategorija/zanr — hijerarhijska."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="lib_categories",
    )
    name = models.CharField(max_length=100, verbose_name=_("Naziv"))
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Nadkategorija"),
    )
    udk_code = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="UDK",
        help_text=_("Univerzalna decimalna klasifikacija"),
    )
    icon = models.CharField(max_length=30, blank=True, default="bi-book")

    objects = CompanyManager()

    class Meta:
        app_label = "library"
        ordering = ["name"]
        verbose_name = _("Kategorija")
        verbose_name_plural = _("Kategorije")

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name


class Book(models.Model):
    """Knjiga (bibliografski zapis) — NE fizicki primjerak."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="lib_books",
    )
    title = models.CharField(max_length=500, verbose_name=_("Naslov"), db_index=True)
    subtitle = models.CharField(max_length=500, blank=True, verbose_name=_("Podnaslov"))
    authors = models.ManyToManyField(Author, blank=True, related_name="books")
    isbn_13 = models.CharField(
        max_length=13,
        blank=True,
        verbose_name="ISBN-13",
        db_index=True,
    )
    isbn_10 = models.CharField(max_length=10, blank=True, verbose_name="ISBN-10")
    publisher = models.CharField(max_length=200, blank=True, verbose_name=_("Izdavac"))
    publish_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Godina izdanja"),
    )
    language = models.CharField(max_length=5, default="hr", verbose_name=_("Jezik"))
    pages = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_("Stranica"))
    description = models.TextField(blank=True, verbose_name=_("Opis"))

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="books",
        verbose_name=_("Kategorija"),
    )

    # Naslovnica
    cover_url = models.URLField(blank=True, verbose_name=_("URL naslovnice"))
    cover_image = models.ImageField(
        upload_to="library/covers/",
        blank=True,
        verbose_name=_("Naslovnica"),
    )

    # OpenLibrary metadata
    openlibrary_key = models.CharField(max_length=50, blank=True, db_index=True)
    openlibrary_data = models.JSONField(default=dict, blank=True)

    # Statistika
    times_borrowed = models.PositiveIntegerField(default=0, verbose_name=_("Puta posudjena"))
    rating_avg = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name=_("Prosjecna ocjena"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CompanyManager()

    class Meta:
        app_label = "library"
        ordering = ["title"]
        verbose_name = _("Knjiga")
        verbose_name_plural = _("Knjige")

    def __str__(self):
        return self.title

    @property
    def author_display(self):
        authors = self.authors.all()[:3]
        if not authors:
            return _("Nepoznat autor")
        return ", ".join(str(a) for a in authors)

    @property
    def available_copies(self):
        return self.copies.filter(status="available").count()

    @property
    def total_copies(self):
        return self.copies.count()


class BookCopy(models.Model):
    """Fizicki primjerak knjige (svaki ima svoj barcode)."""

    class Status(models.TextChoices):
        AVAILABLE = "available", _("Dostupna")
        BORROWED = "borrowed", _("Posudjena")
        RESERVED = "reserved", _("Rezervirana")
        DAMAGED = "damaged", _("Ostecena")
        LOST = "lost", _("Izgubljena")
        DISCARDED = "discarded", _("Otpisana")
        REFERENCE = "reference", _("Referentna (ne posudjuje se)")

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="copies",
    )
    barcode = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Barcode/Signatura"),
        help_text=_("Jedinstveni identifikator primjerka"),
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    condition = models.CharField(
        max_length=20,
        choices=[
            ("new", _("Nova")),
            ("good", _("Dobro")),
            ("fair", _("Prosjecno")),
            ("worn", _("Istrosena")),
        ],
        default="good",
    )
    location = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Lokacija"),
        help_text=_("Npr. Polica A3, Kat 2"),
    )
    acquisition_date = models.DateField(null=True, blank=True, verbose_name=_("Datum nabave"))
    acquisition_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Cijena nabave"),
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "library"
        ordering = ["barcode"]
        verbose_name = _("Primjerak")
        verbose_name_plural = _("Primjerci")

    def __str__(self):
        return f"{self.book.title} [{self.barcode}]"


# ══════════════════════════════════════════════════════════
# CLANOVI
# ══════════════════════════════════════════════════════════


class MembershipType(models.Model):
    """Tip clanarine (djeca, odrasli, umirovljenici, studenti)."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="lib_membership_types",
    )
    name = models.CharField(max_length=100, verbose_name=_("Naziv"))
    max_books = models.PositiveSmallIntegerField(
        default=5,
        verbose_name=_("Max knjiga istovremeno"),
    )
    loan_days = models.PositiveSmallIntegerField(
        default=21,
        verbose_name=_("Rok posudbe (dana)"),
    )
    annual_fee = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name=_("Godisnja clanarina (EUR)"),
    )
    daily_late_fee = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("0.10"),
        verbose_name=_("Kazna po danu kasnjenja (EUR)"),
    )
    can_reserve = models.BooleanField(default=True, verbose_name=_("Moze rezervirati"))

    objects = CompanyManager()

    class Meta:
        app_label = "library"
        verbose_name = _("Tip clanarine")
        verbose_name_plural = _("Tipovi clanarine")

    def __str__(self):
        return self.name


class LibraryMember(models.Model):
    """Clan knjiznice s QR iskaznicom."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Aktivan")
        EXPIRED = "expired", _("Istekla clanarina")
        SUSPENDED = "suspended", _("Suspendiran")
        BLOCKED = "blocked", _("Blokiran (dugovanje)")

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="lib_members",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lib_memberships",
    )
    membership_type = models.ForeignKey(
        MembershipType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )

    first_name = models.CharField(max_length=100, verbose_name=_("Ime"))
    last_name = models.CharField(max_length=100, verbose_name=_("Prezime"))
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    oib = models.CharField(max_length=13, blank=True, verbose_name="OIB")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name=_("Datum rodjenja"))
    address = models.CharField(max_length=300, blank=True)

    # Clanski broj + QR
    member_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_("Clanski broj"),
    )
    qr_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text=_("UUID za QR iskaznicu — skenira se na posudbi"),
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    membership_start = models.DateField(verbose_name=_("Pocetak clanarine"))
    membership_end = models.DateField(null=True, blank=True, verbose_name=_("Kraj clanarine"))

    # Statistika
    total_borrowed = models.PositiveIntegerField(default=0)
    total_fines = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    fines_paid = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyManager()

    class Meta:
        app_label = "library"
        ordering = ["last_name", "first_name"]
        verbose_name = _("Clan knjiznice")
        verbose_name_plural = _("Clanovi knjiznice")

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.member_number})"

    @property
    def outstanding_fines(self):
        return self.total_fines - self.fines_paid

    @property
    def active_loans_count(self):
        return self.loans.filter(returned_date__isnull=True).count()

    @property
    def can_borrow(self):
        if self.status != "active":
            return False
        if self.outstanding_fines > Decimal("5.00"):
            return False
        if self.membership_type and self.active_loans_count >= self.membership_type.max_books:
            return False
        return True


# ══════════════════════════════════════════════════════════
# POSUDBA
# ══════════════════════════════════════════════════════════


class Loan(models.Model):
    """Posudba knjige."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Aktivna")
        RETURNED = "returned", _("Vracena")
        OVERDUE = "overdue", _("Prekoracena")
        LOST = "lost", _("Izgubljena")

    member = models.ForeignKey(
        LibraryMember,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    copy = models.ForeignKey(
        BookCopy,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    borrowed_date = models.DateTimeField(default=timezone.now, verbose_name=_("Datum posudbe"))
    due_date = models.DateField(verbose_name=_("Rok vracanja"))
    returned_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Datum vracanja"))
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    renewed_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Broj produljenja"),
    )
    fine_amount = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name=_("Iznos kazne"),
    )

    reader_profile = models.ForeignKey(
        "ReaderProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loans",
        verbose_name=_("Djecji profil"),
        help_text=_("Ako posudba za dijete. NULL = za roditelja samog."),
    )
    issued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_loans",
    )

    class Meta:
        app_label = "library"
        ordering = ["-borrowed_date"]
        verbose_name = _("Posudba")
        verbose_name_plural = _("Posudbe")

    def __str__(self):
        return f"{self.member} -> {self.copy.book.title}"

    @property
    def is_overdue(self):
        if self.returned_date:
            return False
        return timezone.now().date() > self.due_date

    @property
    def days_overdue(self):
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days

    def calculate_fine(self):
        if self.is_overdue and self.member.membership_type:
            self.fine_amount = self.member.membership_type.daily_late_fee * self.days_overdue
        return self.fine_amount


class Reservation(models.Model):
    """Rezervacija knjige koja je trenutno posudjena."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Ceka")
        READY = "ready", _("Spremna za preuzimanje")
        FULFILLED = "fulfilled", _("Preuzeta")
        CANCELLED = "cancelled", _("Otkazana")
        EXPIRED = "expired", _("Istekla")

    member = models.ForeignKey(
        LibraryMember,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    reserved_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    notified_date = models.DateTimeField(null=True, blank=True)
    pickup_deadline = models.DateField(null=True, blank=True)

    class Meta:
        app_label = "library"
        ordering = ["reserved_date"]
        verbose_name = _("Rezervacija")
        verbose_name_plural = _("Rezervacije")

    def __str__(self):
        return f"{self.member} rezervirao {self.book.title}"


# ══════════════════════════════════════════════════════════
# IMPORT
# ══════════════════════════════════════════════════════════


class ImportBatch(models.Model):
    """Batch import fonda iz Excel/CSV — 3-step wizard."""

    class Status(models.TextChoices):
        UPLOADED = "uploaded", _("Ucitano")
        MAPPED = "mapped", _("Mapirano")
        VALIDATED = "validated", _("Validirano")
        IMPORTED = "imported", _("Uvezeno")
        FAILED = "failed", _("Neuspjelo")

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="lib_imports",
    )
    file_name = models.CharField(max_length=200)
    uploaded_file = models.FileField(upload_to="library/imports/")
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="lib_import_batches"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.UPLOADED,
    )

    # Mapping
    column_mapping = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Excel kolona -> polje u sustavu"),
    )

    # Rezultati validacije
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    error_rows = models.PositiveIntegerField(default=0)
    warning_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    validation_log = models.JSONField(default=list, blank=True)

    # Rezultati importa
    books_created = models.PositiveIntegerField(default=0)
    books_updated = models.PositiveIntegerField(default=0)
    copies_created = models.PositiveIntegerField(default=0)

    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "library"
        ordering = ["-uploaded_at"]
        verbose_name = _("Import fonda")
        verbose_name_plural = _("Importi fonda")

    def __str__(self):
        return f"{self.file_name} ({self.get_status_display()})"


# ══════════════════════════════════════════════════════════
# DIGITALNA POSUDBA (CDL framework — Faza 3)
# ══════════════════════════════════════════════════════════


class DigitalAsset(models.Model):
    """Digitalni sadrzaj vezan za knjigu (EPUB, PDF) — SAMO od nakladnika."""

    class Format(models.TextChoices):
        EPUB = "epub", "EPUB"
        PDF = "pdf", "PDF"

    class Source(models.TextChoices):
        PUBLISHER = "publisher", _("Od nakladnika (legalno)")
        PUBLIC_DOMAIN = "public_domain", _("Javna domena (70+ god)")

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="digital_assets")
    format = models.CharField(max_length=5, choices=Format.choices)
    source = models.CharField(max_length=15, choices=Source.choices)
    file = models.FileField(upload_to="library/digital/", blank=True)

    publisher_license = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Licenca nakladnika"),
    )
    max_concurrent_loans = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_("Max istovremenih posudbi"),
    )
    license_expires = models.DateField(null=True, blank=True)
    total_loans_allowed = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Ukupan broj posudbi prije isteka licence"),
    )
    loans_used = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "library"
        verbose_name = _("Digitalni sadrzaj")
        verbose_name_plural = _("Digitalni sadrzaji")

    def __str__(self):
        return f"{self.book.title} ({self.format})"

    @property
    def can_lend(self):
        if not self.is_active:
            return False
        if self.license_expires and self.license_expires < timezone.now().date():
            return False
        if self.total_loans_allowed and self.loans_used >= self.total_loans_allowed:
            return False
        active = DigitalLoan.objects.filter(
            asset=self,
            returned_date__isnull=True,
        ).count()
        return active < self.max_concurrent_loans


class DigitalLoan(models.Model):
    """Digitalna posudba — CDL model."""

    member = models.ForeignKey(
        LibraryMember,
        on_delete=models.CASCADE,
        related_name="digital_loans",
    )
    asset = models.ForeignKey(
        DigitalAsset,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    borrowed_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    returned_date = models.DateTimeField(null=True, blank=True)

    # Watermark tracking
    watermark_token = models.UUIDField(default=uuid.uuid4, unique=True)

    class Meta:
        app_label = "library"
        ordering = ["-borrowed_date"]
        verbose_name = _("Digitalna posudba")
        verbose_name_plural = _("Digitalne posudbe")

    def __str__(self):
        return f"{self.member} -> {self.asset.book.title} (digital)"


class ReaderProfile(models.Model):
    """
    Djecji citateljski profil -- NEMA login, NEMA email, NEMA lozinku.
    Vezan za roditelja (LibraryMember) koji je jedini User u sustavu.
    GDPR cl.8: Roditelj daje izricitu privolu za obradu podataka djeteta.
    """

    class AgeGroup(models.TextChoices):
        BABY = "0-3", _("Bebe (0-3)")
        PRESCHOOL = "3-6", _("Predskolski (3-6)")
        LOWER_PRIMARY = "6-10", _("Nizi razredi (6-10)")
        UPPER_PRIMARY = "10-14", _("Visi razredi (10-14)")
        TEEN = "14-18", _("Tinejdzeri (14-18)")

    parent = models.ForeignKey(
        LibraryMember,
        on_delete=models.CASCADE,
        related_name="reader_profiles",
        verbose_name=_("Roditelj/Skrbnik"),
    )
    first_name = models.CharField(max_length=100, verbose_name=_("Ime djeteta"))
    last_name = models.CharField(max_length=100, verbose_name=_("Prezime djeteta"))
    date_of_birth = models.DateField(verbose_name=_("Datum rodjenja"))
    age_group = models.CharField(max_length=5, choices=AgeGroup.choices, blank=True)
    nickname = models.CharField(max_length=50, blank=True, verbose_name=_("Nadimak"))

    favorite_genres = models.JSONField(default=list, blank=True)
    reading_level = models.CharField(
        max_length=20,
        choices=[
            ("beginner", _("Pocetnik")),
            ("intermediate", _("Srednji")),
            ("advanced", _("Napredni")),
            ("voracious", _("Prozdrljivac")),
        ],
        default="beginner",
    )

    books_read = models.PositiveIntegerField(default=0)
    reading_streak_days = models.PositiveIntegerField(default=0)
    total_pages_read = models.PositiveIntegerField(default=0)

    xp_points = models.PositiveIntegerField(default=0, verbose_name=_("XP bodovi"))
    badges = models.JSONField(default=list, blank=True)
    current_challenge = models.CharField(max_length=200, blank=True)

    parental_consent = models.BooleanField(default=False, verbose_name=_("GDPR pristanak roditelja"))
    consent_date = models.DateTimeField(null=True, blank=True)
    consent_ip = models.GenericIPAddressField(null=True, blank=True)

    max_books = models.PositiveSmallIntegerField(default=3)
    content_filter = models.BooleanField(default=True)
    avatar_emoji = models.CharField(max_length=5, default="📚")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "library"
        ordering = ["first_name"]
        verbose_name = _("Djecji citateljski profil")
        verbose_name_plural = _("Djecji citateljski profili")

    def __str__(self):
        return f"{self.first_name} ({self.parent})"

    @property
    def age(self):
        today = timezone.now().date()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def auto_age_group(self):
        a = self.age
        if a <= 3:
            return "0-3"
        elif a <= 6:
            return "3-6"
        elif a <= 10:
            return "6-10"
        elif a <= 14:
            return "10-14"
        else:
            return "14-18"

    def check_badges(self):
        badges = list(self.badges)
        if self.books_read >= 1 and "prva_knjiga" not in badges:
            badges.append("prva_knjiga")
        if self.books_read >= 10 and "deset_knjiga" not in badges:
            badges.append("deset_knjiga")
        if self.books_read >= 50 and "pedeset_knjiga" not in badges:
            badges.append("pedeset_knjiga")
        if self.reading_streak_days >= 7 and "streak_7" not in badges:
            badges.append("streak_7")
        if self.reading_streak_days >= 30 and "streak_30" not in badges:
            badges.append("streak_30")
        if self.total_pages_read >= 1000 and "tisucu_stranica" not in badges:
            badges.append("tisucu_stranica")
        self.badges = badges
        self.save(update_fields=["badges"])
