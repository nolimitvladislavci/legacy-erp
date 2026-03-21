from django.contrib.auth.models import User
from django.db import models
from core.managers import CompanyManager


class ImportBatch(models.Model):
    STATUS = [
        ("pending",    "Ceka obradu"),
        ("processing", "AI obrada u tijeku"),
        ("ready",      "Spremno za pregled"),
        ("confirmed",  "Pretvoreno u Primku"),
        ("error",      "Greska"),
    ]

    company   = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        null=True, blank=True, verbose_name="Tvrtka",
    )
    objects = CompanyManager()

    supplier  = models.ForeignKey(
        "partners.Partner", on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Dobavljac",
    )
    file      = models.FileField(upload_to="smart_import/%Y/%m/", verbose_name="Datoteka")
    file_type = models.CharField(max_length=10, verbose_name="Tip datoteke")  # xml|pdf|image
    status    = models.CharField(max_length=20, choices=STATUS, default="pending", verbose_name="Status")
    raw_json  = models.JSONField(default=list, verbose_name="Izvuceni podaci")
    error_msg = models.TextField(blank=True, verbose_name="Poruka greske")
    status_message = models.CharField(max_length=200, blank=True, default="",
                                       verbose_name="Status poruka")
    original_filename = models.CharField(max_length=255, blank=True, default="",
                                          verbose_name="Originalni naziv datoteke")
    retry_count = models.PositiveIntegerField(default=0, verbose_name="Broj pokusaja")
    processing_started_at = models.DateTimeField(null=True, blank=True,
                                                  verbose_name="Pocetak obrade")

    goods_receipt = models.OneToOneField(
        "inventory.GoodsReceipt", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="import_batch",
        verbose_name="Primka",
    )

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Kreirao",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Uvoz (batch)"
        verbose_name_plural = "Uvozi (batch)"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"ImportBatch #{self.pk} \u2013 {self.get_status_display()}"


class ImportBatchItem(models.Model):
    batch          = models.ForeignKey(
        ImportBatch, on_delete=models.CASCADE,
        related_name="items", verbose_name="Batch",
    )
    row_index      = models.PositiveIntegerField(verbose_name="Redak")
    vendor_name    = models.CharField(max_length=255, verbose_name="Naziv (dobavljac)")
    quantity       = models.DecimalField(max_digits=10, decimal_places=3, default=1,
                                         verbose_name="Kolicina")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                         verbose_name="Nabavna cijena/jed.")

    matched_item    = models.ForeignKey(
        "inventory.InventoryItem", on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Nas artikl",
    )
    match_score     = models.FloatField(default=0, verbose_name="Score podudaranja")
    is_manual       = models.BooleanField(default=False, verbose_name="Rucno spojeno")
    margin_override = models.DecimalField(max_digits=6, decimal_places=2,
                                          null=True, blank=True, verbose_name="Marza override (%)")

    class Meta:
        verbose_name        = "Stavka uvoza"
        verbose_name_plural = "Stavke uvoza"
        ordering            = ["row_index"]

    def __str__(self):
        return f"{self.vendor_name} x {self.quantity}"


class VendorItemMapping(models.Model):
    company          = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        null=True, blank=True, verbose_name="Tvrtka",
    )
    objects = CompanyManager()

    partner          = models.ForeignKey(
        "partners.Partner", on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Dobavljac",
    )
    vendor_item_name = models.CharField(max_length=255, verbose_name="Naziv dobavljaca")
    inventory_item   = models.ForeignKey(
        "inventory.InventoryItem", on_delete=models.CASCADE,
        verbose_name="Nas artikl",
    )

    class Meta:
        verbose_name        = "Mapiranje naziva artikla"
        verbose_name_plural = "Mapiranja naziva artikala"
        unique_together     = [["company", "vendor_item_name", "partner"]]

    def __str__(self):
        return f'"{self.vendor_item_name}" -> {self.inventory_item.name}'


from decimal import Decimal
from django.utils import timezone as _tz


class GeminiUsageLog(models.Model):
    """Log svakog Gemini API poziva — budget kontrola i troškovni pregled."""
    caller        = models.CharField(max_length=100, db_index=True,
                        help_text="Modul koji je pozvao AI (invoice_text, smart_import...)")
    model         = models.CharField(max_length=60, default="gemini-2.0-flash")
    input_tokens  = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    cost_eur      = models.DecimalField(max_digits=10, decimal_places=8, default=0)
    success       = models.BooleanField(default=True)
    input_hash    = models.CharField(max_length=16, blank=True)
    called_at     = models.DateTimeField(default=_tz.now, db_index=True)

    class Meta:
        verbose_name        = "Gemini poziv"
        verbose_name_plural = "Gemini pozivi"
        ordering            = ["-called_at"]

    def __str__(self):
        return f"{self.called_at:%Y-%m-%d %H:%M} | {self.caller} | {self.input_tokens}t | {'OK' if self.success else 'ERR'}"

    @classmethod
    def daily_summary(cls):
        from django.db.models import Sum, Count
        today = _tz.now().date()
        return cls.objects.filter(called_at__date=today).aggregate(
            total_calls=Count("id"),
            ok_calls=Count("id", filter=models.Q(success=True)),
            total_tokens=Sum("input_tokens"),
            total_cost=Sum("cost_eur"),
        )


class CompanyMailbox(models.Model):
    """
    Per-company email konfiguracija za Email Rampu.
    Svaki mailbox pripada jednoj firmi — IMAP se koristi za primanje računa.
    """
    PROTOCOL_CHOICES = [
        ("imap", "IMAP"),
        ("webhook", "Webhook (Push)"),
    ]

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="mailboxes", verbose_name="Tvrtka",
    )
    email_address = models.EmailField(verbose_name="Email adresa", unique=True)
    protocol = models.CharField(
        max_length=10, choices=PROTOCOL_CHOICES, default="imap",
        verbose_name="Protokol",
    )

    # IMAP settings
    imap_server = models.CharField(max_length=255, default="imap.gmail.com", blank=True,
                                   verbose_name="IMAP server")
    imap_port = models.PositiveIntegerField(default=993, verbose_name="IMAP port")
    imap_password = models.CharField(max_length=255, blank=True, verbose_name="App Password")
    imap_folder = models.CharField(max_length=100, default="INBOX", verbose_name="Folder")
    imap_use_ssl = models.BooleanField(default=True, verbose_name="SSL")

    # Status
    is_active = models.BooleanField(default=True, verbose_name="Aktivan")
    last_check = models.DateTimeField(null=True, blank=True, verbose_name="Zadnja provjera")
    last_error = models.TextField(blank=True, verbose_name="Zadnja greška")
    total_imported = models.PositiveIntegerField(default=0, verbose_name="Ukupno uvezeno")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Email sandučić"
        verbose_name_plural = "Email sandučići"
        ordering = ["company__name", "email_address"]

    def __str__(self):
        return f"{self.email_address} → {self.company.name}"



class FailedImport(models.Model):
    """Log neuspjelih uvoza - privici koji su preskoceni zbog greske."""
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, null=True, blank=True)
    email_subject = models.CharField(max_length=500, blank=True)
    email_sender = models.CharField(max_length=255, blank=True)
    filename = models.CharField(max_length=255)
    error_message = models.TextField()
    mailbox_user = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Neuspjeli uvoz"
        verbose_name_plural = "Neuspjeli uvozi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} - {self.error_message[:50]}"

class ProblemReport(models.Model):
    """Korisnicka prijava problema s uvozom."""
    batch = models.ForeignKey(
        ImportBatch, on_delete=models.CASCADE,
        related_name="problem_reports", verbose_name="Batch",
    )
    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        null=True, blank=True, verbose_name="Tvrtka",
    )
    reported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Prijavio",
    )
    description = models.TextField(verbose_name="Opis problema")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False, verbose_name="Rijeseno")

    class Meta:
        verbose_name = "Prijava problema"
        verbose_name_plural = "Prijave problema"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Problem #{self.pk} - Batch #{self.batch_id}"


# ── Predarhiva: StagingBatch za bulk OCR ──────────────────────────────

class StagingBatch(models.Model):
    """
    Predkomora — skup slika/fajlova koji čekaju AI obradu.
    Marija učita 1000 slika, vidi ih u pregledu, klikne "Pokreni".
    Gemini ih obrađuje redom, s rate limitom, s live progressom.
    """
    STATUS_CHOICES = [
        ('pending', 'Čeka pokretanje'),
        ('queued', 'U redu za obradu'),
        ('processing', 'AI obrađuje'),
        ('paused', 'Pauzirano'),
        ('done', 'Završeno'),
        ('done_with_errors', 'Završeno s greškama'),
    ]
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='staging_batches',
    )
    objects = CompanyManager()
    title = models.CharField(max_length=200, blank=True, default='',
        help_text='Npr. "Računi veljača 2026"')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_files = models.IntegerField(default=0)
    processed_files = models.IntegerField(default=0)
    failed_files = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_message = models.CharField(max_length=500, blank=True, default='',
        help_text='Zadnja AI poruka — razmišljanje na glas')

    class Meta:
        verbose_name = 'Staging batch'
        verbose_name_plural = 'Staging batchevi'
        ordering = ['-created_at']

    def __str__(self):
        return f'Staging #{self.pk} — {self.title or "Bez naziva"} ({self.get_status_display()})'

    @property
    def progress_pct(self):
        if self.total_files == 0:
            return 0
        return int((self.processed_files / self.total_files) * 100)

    @property
    def estimated_minutes_remaining(self):
        remaining = self.total_files - self.processed_files
        return max(0, int(remaining / 8))  # 8 req/min


class StagingFile(models.Model):
    """Jedan fajl unutar StagingBatcha."""
    STATUS_CHOICES = [
        ('pending', 'Čeka'),
        ('processing', 'AI čita'),
        ('done', 'Obrađeno'),
        ('error', 'Greška'),
        ('skipped', 'Preskočeno'),
    ]
    staging_batch = models.ForeignKey(
        StagingBatch, on_delete=models.CASCADE, related_name='files',
    )
    file = models.FileField(upload_to='staging/%Y/%m/')
    original_filename = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_batch = models.ForeignKey(
        ImportBatch, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='staging_source',
    )
    ai_message = models.CharField(max_length=500, blank=True,
        help_text='Što je AI rekao za ovaj fajl')
    error_msg = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Staging fajl'
        verbose_name_plural = 'Staging fajlovi'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.original_filename} ({self.get_status_display()})'
