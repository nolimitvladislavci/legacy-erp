"""
data_migration/models.py

Univerzalni modul za migraciju podataka iz bilo kojeg vanjskog programa
u LIMIT Connect ERP bazu.

NAPOMENA: LIMIT Connect NIJE arhivski sustav. Sve uloadane datoteke
se automatski brisu nakon 24 sata (Celery beat task).
"""
import os
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from core.managers import CompanyManager


def _migration_upload_path(instance, filename):
    """
    Sprema u zasticenu mapu izvan MEDIA_URL dosega.
    Format: migrations/<company_pk>/<uuid>/<original_filename>
    """
    return os.path.join(
        "migrations",
        str(instance.project.company_id),
        uuid.uuid4().hex[:12],
        filename,
    )


class MigrationProject(models.Model):
    """
    Jedan projekt migracije = jedan prijelaz korisnika s programa X na LIMIT Connect.
    Korisnik moze imati vise projekata (npr. partneri iz CSV-a, artikli iz Excela).
    """

    STATUS_CHOICES = [
        ("draft",     "Nacrt"),
        ("mapped",    "Polja mapirana"),
        ("preview",   "Pregled podataka"),
        ("importing", "Uvoz u tijeku"),
        ("completed", "Zavrseno"),
        ("failed",    "Neuspjelo"),
    ]

    ENTITY_CHOICES = [
        ("partners",  "Partneri"),
        ("items",     "Artikli"),
        ("ledger",    "Knjizenja"),
        ("mixed",     "Mjesovito"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="migration_projects",
        verbose_name="Tvrtka",
    )
    objects = CompanyManager()

    name = models.CharField(
        max_length=200,
        verbose_name="Naziv projekta",
        help_text="Npr. 'Prijelaz s Luceeda - partneri'",
    )
    source_program = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Izvorni program",
        help_text="Npr. Synesis, Luceed, Pantheon, minimax, nepoznato...",
    )
    entity_type = models.CharField(
        max_length=20,
        choices=ENTITY_CHOICES,
        default="mixed",
        verbose_name="Tip podataka",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        verbose_name="Status",
    )

    # Rezultati importa — azuriraju se inkrementalno tijekom importa
    processed_rows = models.IntegerField(default=0, verbose_name="Obradeno redova")
    total_rows = models.IntegerField(default=0, verbose_name="Ukupno redova")
    records_created = models.IntegerField(default=0, verbose_name="Kreirano")
    records_updated = models.IntegerField(default=0, verbose_name="Azurirano")
    records_skipped = models.IntegerField(default=0, verbose_name="Preskoceno")
    records_failed = models.IntegerField(default=0, verbose_name="Neuspjelo")

    # Field mapping - sprema korisnikovo mapiranje kolona
    # Format: {"csv_column": "erp_field", ...}
    # Npr: {"Naziv firme": "name", "OIB broj": "oib", "Ulica": "address"}
    field_mapping = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Mapiranje polja",
    )

    # Preview podataka (prvih N redova nakon mapiranja)
    preview_data = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Preview podataka",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Kreirao",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Migracijski projekt"
        verbose_name_plural = "Migracijski projekti"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @property
    def total_records(self):
        return (
            self.records_created
            + self.records_updated
            + self.records_skipped
            + self.records_failed
        )

    @property
    def has_errors(self):
        return self.logs.filter(level="error").exists()

    @property
    def progress_percent(self):
        if self.total_rows <= 0:
            return 0
        return min(100, int(self.processed_rows * 100 / self.total_rows))


class MigrationFile(models.Model):
    """
    Uploadana datoteka za migraciju.

    SIGURNOST:
    - Upload path: media/migrations/<company>/<uuid>/<filename>
    - Permissions: chmod 600 (set via post_save signal)
    - Web pristup: ZABRANJEN (nginx deny na /media/migrations/)
    - Retention: max 24h, automatsko brisanje via Celery beat

    LIMIT Connect NIJE arhiva. Korisnik MORA zadrzati vlastite originale.
    """

    FORMAT_CHOICES = [
        ("csv",   "CSV"),
        ("xlsx",  "Excel (XLSX)"),
        ("xls",   "Excel (XLS)"),
        ("json",  "JSON"),
        ("xml",   "XML"),
        ("mdb",   "Access (MDB)"),
        ("other", "Ostalo"),
    ]

    project = models.ForeignKey(
        MigrationProject,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name="Projekt",
    )
    file = models.FileField(
        upload_to=_migration_upload_path,
        verbose_name="Datoteka",
    )
    original_filename = models.CharField(
        max_length=255,
        verbose_name="Originalni naziv",
    )
    file_format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        verbose_name="Format",
    )
    file_size = models.PositiveIntegerField(
        default=0,
        verbose_name="Velicina (bytes)",
    )

    # Adapter koji je detektirao/obradio ovu datoteku
    adapter_used = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Koristeni adapter",
    )

    # Ekstrakcija: sirovi podaci iz datoteke (interni rjecnik)
    extracted_data = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Izvuceni podaci",
    )
    # Broj redova detektiranih u datoteci
    row_count = models.IntegerField(
        default=0,
        verbose_name="Broj redova",
    )

    # Kolone/zaglavlja detektirana u datoteci
    detected_columns = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Detektirane kolone",
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        verbose_name="Istice",
        help_text="Datoteka se automatski brise nakon ovog vremena.",
    )

    class Meta:
        verbose_name = "Migracijska datoteka"
        verbose_name_plural = "Migracijske datoteke"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.original_filename} ({self.get_file_format_display()})"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except (OSError, ValueError):
                pass
        super().save(*args, **kwargs)

    def delete_file_from_disk(self):
        """Fizicki brise datoteku sa diska."""
        if self.file:
            try:
                storage = self.file.storage
                name = self.file.name
                if storage.exists(name):
                    storage.delete(name)
            except Exception:
                pass


class MigrationLog(models.Model):
    """
    Zapisuje svaki warning, error ili info tijekom importa.
    """

    LEVEL_CHOICES = [
        ("info",    "Info"),
        ("warning", "Upozorenje"),
        ("error",   "Greska"),
    ]

    project = models.ForeignKey(
        MigrationProject,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="Projekt",
    )
    level = models.CharField(
        max_length=10,
        choices=LEVEL_CHOICES,
        default="info",
        verbose_name="Razina",
    )
    entity_type = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Tip entiteta",
        help_text="Npr. partner, item, ledger_entry",
    )
    row_number = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Red u datoteci",
    )
    field_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Polje",
    )
    message = models.TextField(verbose_name="Poruka")

    original_value = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Originalna vrijednost",
    )
    resolved_value = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Razrijesena vrijednost",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Migracijski log"
        verbose_name_plural = "Migracijski logovi"
        ordering = ["created_at"]

    def __str__(self):
        prefix = f"Red {self.row_number}: " if self.row_number else ""
        return f"[{self.level.upper()}] {prefix}{self.message[:80]}"
