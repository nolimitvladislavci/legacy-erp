import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from companies.models import Company
from core.managers import CompanyManager
from partners.models import Partner


class Document(models.Model):
    TYPE_CHOICES = [
        ('invoice', _('Izlazni Račun')),
        ('offer', _('Ponuda')),
        ('bill', _('Ulazni Račun')),
        ('contract', _('Ugovor')),
        ('receipt', _('Potvrda')),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name=_("Tvrtka"))
    objects = CompanyManager()
    partner = models.ForeignKey(Partner, on_delete=models.SET_NULL, null=True, related_name='documents', verbose_name=_("Partner"))

    doc_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name=_("Tip dokumenta"))
    doc_number = models.CharField(max_length=50, verbose_name=_("Broj dokumenta"))

    date_issued = models.DateField(verbose_name=_("Datum izdavanja"))
    date_due = models.DateField(null=True, blank=True, verbose_name=_("Datum dospijeća"))

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Iznos"))

    file = models.FileField(upload_to='documents/%Y/%m/', verbose_name=_("Datoteka"))

    # Status plaćanja - kontrolira ga Finance modul
    is_paid = models.BooleanField(default=False, verbose_name=_("Plaćeno"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Dokument")
        verbose_name_plural = _("Dokumenti")

    def __str__(self):
        return f"{self.doc_number} - {self.get_doc_type_display()}"


# ════════════════════════════════════════════════════════════
# Universal Process Documents (Otpremnica, Primka, Otkupni, CMR)
# ════════════════════════════════════════════════════════════

class GrossmarktDocument(models.Model):
    """Bazni model za procesne dokumente."""
    STATUS_CHOICES = [
        ('draft', _('Nacrt')),
        ('confirmed', _('Potvrđeno')),
        ('cancelled', _('Stornirano')),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name=_('Tvrtka'))
    objects = CompanyManager()
    partner = models.ForeignKey(Partner, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Partner'))
    doc_number = models.CharField(max_length=255, db_index=True, verbose_name=_('Broj dokumenta'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    date_issued = models.DateField(verbose_name=_('Datum izdavanja'))
    date_confirmed = models.DateTimeField(null=True, blank=True, verbose_name=_('Datum potvrde'))
    notes = models.TextField(blank=True, verbose_name=_('Napomena'))
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created', verbose_name=_('Kreirao'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def confirm(self):
        from django.utils import timezone as tz
        self.status = 'confirmed'
        self.date_confirmed = tz.now()
        self.save(update_fields=['status', 'date_confirmed', 'updated_at'])

    def cancel(self):
        self.status = 'cancelled'
        self.save(update_fields=['status', 'updated_at'])

    @property
    def total(self):
        return sum(i.line_total for i in self.items.all())

    @property
    def total_vat(self):
        return sum(i.vat_amount for i in self.items.all())

    @property
    def total_with_vat(self):
        return self.total + self.total_vat


class GrossmarktDocItem(models.Model):
    """Bazna stavka za procesne dokumente."""
    product_name = models.CharField(max_length=200, verbose_name=_('Naziv'))
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Količina'))
    unit = models.CharField(max_length=20, default='kg', verbose_name=_('Jed. mjere'))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Jed. cijena'))
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=25, verbose_name=_('PDV %'))
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name=_('Popust %'))

    class Meta:
        abstract = True

    @property
    def line_total(self):
        base = float(self.quantity * self.unit_price)
        if self.discount_pct:
            base -= base * float(self.discount_pct) / 100
        return round(base, 2)

    @property
    def vat_amount(self):
        return round(self.line_total * float(self.vat_rate) / 100, 2)

    @property
    def line_total_with_vat(self):
        return round(self.line_total + self.vat_amount, 2)

    def __str__(self):
        return f"{self.product_name} x {self.quantity} {self.unit}"


class Otpremnica(GrossmarktDocument):
    delivery_address = models.TextField(blank=True, verbose_name=_('Adresa dostave'))
    vehicle_plate = models.CharField(max_length=20, blank=True, verbose_name=_('Reg. oznaka'))
    driver_name = models.CharField(max_length=100, blank=True, verbose_name=_('Vozač'))

    class Meta(GrossmarktDocument.Meta):
        verbose_name = _('Otpremnica')
        verbose_name_plural = _('Otpremnice')
    def __str__(self):
        return f"OTP-{self.doc_number}"

class OtpremnicaItem(GrossmarktDocItem):
    document = models.ForeignKey(Otpremnica, on_delete=models.CASCADE, related_name='items')
    batch_number = models.CharField(
        max_length=50, blank=True,
        verbose_name=_('LOT / Šarža'),
        help_text='Npr. LOT-20261015 — iz kojeg prešanja/berbe je roba',
    )
    expiry_batch = models.ForeignKey(
        'pos.ExpiryBatch', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='otpremnica_items',
        verbose_name=_('Veza na LOT (ExpiryBatch)'),
    )
    class Meta:
        verbose_name = _('Stavka otpremnice')
        verbose_name_plural = _('Stavke otpremnice')


# Primka removed (Fix 4) -- use inventory.GoodsReceipt instead


class OtkupniBlok(GrossmarktDocument):
    farmer_name = models.CharField(max_length=200, verbose_name=_('Poljoprivrednik'))
    farmer_oib = models.CharField(max_length=11, blank=True, verbose_name=_('OIB'))
    farmer_address = models.TextField(blank=True, verbose_name=_('Adresa'))
    farmer_iban = models.CharField(max_length=34, blank=True, verbose_name=_('IBAN'))
    payment_method = models.CharField(max_length=20, default='virman', choices=[('virman', _('Virman')), ('gotovina', _('Gotovina'))], verbose_name=_('Način plaćanja'))

    class Meta(GrossmarktDocument.Meta):
        verbose_name = _('Otkupni blok')
        verbose_name_plural = _('Otkupni blokovi')
    def __str__(self):
        return f"OTK-{self.doc_number}"

class OtkupniBlokItem(GrossmarktDocItem):
    document = models.ForeignKey(OtkupniBlok, on_delete=models.CASCADE, related_name='items')
    origin_country = models.CharField(max_length=5, default='HR', verbose_name=_('Porijeklo'))
    quality_class = models.CharField(max_length=5, blank=True, choices=[('I', 'I'), ('II', 'II'), ('III', 'III')], verbose_name=_('Klasa'))
    class Meta:
        verbose_name = _('Stavka otkupnog bloka')
        verbose_name_plural = _('Stavke otkupnog bloka')


class CMR(GrossmarktDocument):
    sender_name = models.CharField(max_length=200, blank=True, verbose_name=_('Pošiljatelj'))
    sender_address = models.TextField(blank=True)
    receiver_name = models.CharField(max_length=200, blank=True, verbose_name=_('Primatelj'))
    receiver_address = models.TextField(blank=True)
    carrier_name = models.CharField(max_length=200, blank=True, verbose_name=_('Prijevoznik'))
    vehicle_plate = models.CharField(max_length=30, blank=True, verbose_name=_('Reg. oznaka'))
    place_of_loading = models.CharField(max_length=200, blank=True, verbose_name=_('Mjesto utovara'))
    place_of_delivery = models.CharField(max_length=200, blank=True, verbose_name=_('Mjesto istovara'))
    temp_regime = models.CharField(max_length=30, blank=True, verbose_name=_('Temp. režim'))
    customs_status = models.CharField(max_length=10, blank=True, default='', choices=[('', '-'), ('T1', 'T1'), ('T2', 'T2'), ('TIR', 'TIR')], verbose_name=_('Carinski status'))

    class Meta(GrossmarktDocument.Meta):
        verbose_name = _('CMR teretni list')
        verbose_name_plural = _('CMR teretni listovi')
    def __str__(self):
        return f"CMR-{self.doc_number}"

class CMRItem(GrossmarktDocItem):
    document = models.ForeignKey(CMR, on_delete=models.CASCADE, related_name='items')
    packaging = models.CharField(max_length=50, blank=True, verbose_name=_('Pakiranje'))
    gross_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=_('Bruto kg'))
    volume_m3 = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name=_('m³'))
    class Meta:
        verbose_name = _('CMR stavka')
        verbose_name_plural = _('CMR stavke')


# ════════════════════════════════════════════════════════════
# ArhivaEntry — Centralizirana arhiva svih dokumenata
# ════════════════════════════════════════════════════════════

class ArhivaEntry(models.Model):
    """Centralni registar svih dokumenata u sustavu — denormalizirani metapodaci za brzu pretragu."""
    SOURCE_TYPES = [
        ('invoice_out',   _('Izlazni račun')),
        ('invoice_in',    _('Ulazni račun (smart import)')),
        ('eracun',        _('e-Račun (FINA/XML)')),
        ('document',      _('Dokument (ručni upload)')),
        ('fiscal_cert',   _('FINA certifikat')),
        ('otpremnica',    _('Otpremnica')),
        ('primka',        _('Primka')),
        ('otkupni_blok',  _('Otkupni blok')),
        ('cmr',           _('CMR')),
        ('pos_receipt',   _('POS račun')),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name=_('Tvrtka'))
    objects = CompanyManager()

    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES, verbose_name=_('Tip izvora'))
    source_id = models.CharField(max_length=255, verbose_name=_('ID izvornog objekta'))
    archive_number = models.CharField(max_length=50, unique=True, blank=True, default='', db_index=True, verbose_name=_('Evidencijski broj'))

    # Denormalizirani metapodaci za pretragu
    doc_number = models.CharField(max_length=255, db_index=True, verbose_name=_('Broj dokumenta'))
    partner_name = models.CharField(max_length=200, blank=True, verbose_name=_('Partner'))
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name=_('Iznos'))
    currency = models.CharField(max_length=3, default='EUR', verbose_name=_('Valuta'))
    doc_date = models.DateField(verbose_name=_('Datum dokumenta'))

    # Fiskalni podaci (ako postoje)
    zki = models.CharField(max_length=64, blank=True, verbose_name=_('ZKI'))
    jir = models.CharField(max_length=64, blank=True, verbose_name=_('JIR'))

    # File reference
    file_path = models.CharField(max_length=500, blank=True, verbose_name=_('Putanja datoteke'))
    has_xml = models.BooleanField(default=False, verbose_name=_('Ima XML'))
    has_pdf = models.BooleanField(default=False, verbose_name=_('Ima PDF'))
    has_image = models.BooleanField(default=False, verbose_name=_('Ima sliku'))

    # Audit
    archived_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Arhivirao'))
    archived_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Datum arhiviranja'))
    session_key = models.CharField(max_length=64, blank=True, db_index=True, verbose_name=_('Ključ sesije'))

    # Integritet i zaštita
    integrity_hash = models.CharField(max_length=64, blank=True, db_index=True, verbose_name=_('Integritet hash'))
    deletion_protected_until = models.DateField(null=True, blank=True, verbose_name=_('Zaštićeno do'))

    # AI Bookkeeper
    is_booked = models.BooleanField(default=False, verbose_name=_("Proknjiženo"))
    ai_proposal = models.JSONField(null=True, blank=True, verbose_name=_("AI prijedlog knjiženja"))

    # Barcode
    barcode = models.CharField(max_length=64, blank=True, db_index=True,
                               verbose_name=_('Barcode'),
                               help_text='Interni barcode za fizičko mapiranje dokumenta')

    class Meta:
        verbose_name = _('Arhivski zapis')
        verbose_name_plural = _('Arhivski zapisi')
        ordering = ['-archived_at']
        constraints = []  # Deep duplicate check handled in save()
        indexes = [
            models.Index(fields=['company', 'source_type'], name='arhiva_co_src_idx'),
            models.Index(fields=['company', 'doc_date'], name='arhiva_co_date_idx'),
        ]

    def __str__(self):
        return f"{self.get_source_type_display()} — {self.doc_number}"

    def compute_integrity_hash(self):
        """Deterministicki SHA-256 od 6 kljucnih polja."""
        import hashlib
        data = '|'.join([
            str(self.source_type or ''),
            str(self.source_id or ''),
            str(self.doc_number or ''),
            str(self.amount or 0),
            str(self.doc_date or ''),
            str(self.company_id or ''),
        ])
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def set_deletion_protection(self):
        """11 godina od doc_date - HR zakonski rok cuvanja."""
        from datetime import timedelta, date as _date
        if self.doc_date:
            # Ensure doc_date is a date object, not string
            if isinstance(self.doc_date, str):
                self.doc_date = _date.fromisoformat(self.doc_date)
            self.deletion_protected_until = self.doc_date + timedelta(days=11 * 365)

    def save(self, *args, **kwargs):
        # Deep duplicate check — ALL criteria must match
        if not self.pk and self.doc_number:
            qs = ArhivaEntry.objects.unscoped().filter(
                company_id=self.company_id,
                doc_number=self.doc_number,
                source_type=self.source_type,
            )
            # Add amount check (within 0.01 tolerance)
            if self.amount:
                from decimal import Decimal
                if not isinstance(self.amount, Decimal):
                    self.amount = Decimal(str(self.amount or 0))
                tolerance = Decimal('0.01')
                qs = qs.filter(
                    amount__gte=self.amount - tolerance,
                    amount__lte=self.amount + tolerance,
                )
            # Add date check
            if self.doc_date:
                qs = qs.filter(doc_date=self.doc_date)
            # Add partner check (first 20 chars, case-insensitive)
            if self.partner_name:
                qs = qs.filter(partner_name__istartswith=self.partner_name[:20])
            if qs.exists():
                return  # Skip true duplicate — original already archived
        if not self.archive_number:
            self._assign_archive_number()
        # Always recompute hash — detects tampering on update (audit fix 2026-03-19)
        self.integrity_hash = self.compute_integrity_hash()
        if not self.deletion_protected_until:
            self.set_deletion_protection()
        if not self.barcode:
            self._generate_barcode()
        # Retry on archive_number collision — each attempt in its own SAVEPOINT
        # to avoid PostgreSQL broken transaction state inside @atomic blocks
        from django.db import IntegrityError, transaction
        for attempt in range(5):
            try:
                sid = transaction.savepoint()
                super().save(*args, **kwargs)
                transaction.savepoint_commit(sid)
                return
            except IntegrityError as e:
                transaction.savepoint_rollback(sid)
                err_str = str(e)
                if 'arhiva_unique_doc_per_company' in err_str or 'duplicate' in err_str.lower():
                    return  # Duplicate entry — skip silently
                elif 'archnum_uniq' in err_str or 'archive_number' in err_str:
                    self.archive_number = ''
                    self._assign_archive_number()
                else:
                    raise
        # Final attempt without catching
        super().save(*args, **kwargs)

    def _generate_barcode(self):
        import random
        import string as _string
        from datetime import date
        prefix = (self.company.name[:4].upper().replace(' ', '') if self.company_id else 'LCNK')
        rand = ''.join(random.choices(_string.digits, k=6))
        self.barcode = f"LC-{date.today().strftime('%Y%m%d')}-{prefix}-{rand}"

    def _assign_archive_number(self):
        from datetime import date as _d
        yr = _d.today().year
        pfx = 'ARH-%d/' % yr
        last_nums = []
        for an in ArhivaEntry.objects.filter(
            archive_number__startswith=pfx
        ).values_list('archive_number', flat=True):
            try:
                last_nums.append(int(an.split('/')[-1]))
            except (ValueError, IndexError):
                pass
        seq = (max(last_nums) + 1) if last_nums else 1
        self.archive_number = '%s%05d' % (pfx, seq)

    @property
    def is_deletion_protected(self):
        from django.utils import timezone
        if not self.deletion_protected_until:
            return False
        return timezone.now().date() < self.deletion_protected_until


# ════════════════════════════════════════════════════════════
# DocumentBlob — Binary storage u PostgreSQL
# ════════════════════════════════════════════════════════════

class DocumentBlob(models.Model):
    """Sprema datoteke direktno u bazu (bytea). Max 500KB po fajlu."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name=_('Tvrtka'))
    filename = models.CharField(max_length=255, verbose_name=_('Naziv datoteke'))
    content_type = models.CharField(max_length=100, verbose_name=_('MIME tip'))
    file_data = models.BinaryField(verbose_name=_('Podaci'))
    file_size = models.IntegerField(verbose_name=_('Velicina (bytes)'))
    file_hash = models.CharField(max_length=64, db_index=True, verbose_name=_('SHA-256'))
    source_type = models.CharField(max_length=30, blank=True, verbose_name=_('Tip izvora'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Document Blob')
        verbose_name_plural = _('Document Blobs')

    def __str__(self):
        return f"{self.filename} ({self.file_size // 1024}KB)"


# ════════════════════════════════════════════════════════════
# StorageConfig — Per-company storage konfiguracija
# ════════════════════════════════════════════════════════════

class StorageConfig(models.Model):
    """Konfiguracija storage backenda per-company."""
    BACKEND_CHOICES = [
        ('local', _('Lokalni disk')),
        ('cloud', _('Cloud (B2/S3)')),
        ('database', _('Baza podataka')),
    ]
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='storage_config', verbose_name=_('Tvrtka'))
    backend = models.CharField(max_length=20, choices=BACKEND_CHOICES, default='local', verbose_name=_('Storage backend'))
    max_file_size_mb = models.IntegerField(default=10, verbose_name=_('Max velicina datoteke (MB)'))
    auto_compress_images = models.BooleanField(default=True, verbose_name=_('Auto kompresija slika'))
    cloud_bucket = models.CharField(max_length=100, blank=True, verbose_name=_('Cloud bucket'))
    cloud_prefix = models.CharField(max_length=100, blank=True, verbose_name=_('Cloud prefix'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Storage Konfiguracija')
        verbose_name_plural = _('Storage Konfiguracije')

    def __str__(self):
        return f"{self.company} — {self.get_backend_display()}"


# ════════════════════════════════════════════════════════════
# ArhivaBookmark — Korisničke oznake na arhivskim zapisima
# ════════════════════════════════════════════════════════════

from django.conf import settings as _settings

class ArhivaBookmark(models.Model):
    user = models.ForeignKey(_settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    entry = models.ForeignKey('ArhivaEntry', on_delete=models.CASCADE, related_name='bookmarks')
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'entry')
        verbose_name = _('Arhivska oznaka')
        verbose_name_plural = _('Arhivske oznake')

    def __str__(self):
        return f"Bookmark: {self.user} → {self.entry}"


# ════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════
# ConversionRecord — Dokaz o konverziji slike u XML
# Za regulatornu uskladenost (kazna 5000 EUR za izgubljeni racun)
# ════════════════════════════════════════════════════════════

class ConversionRecord(models.Model):
    """
    Audit trail za konverziju: Slika ulaznog racuna -> strukturirani XML.
    Svaki zapis dokazuje da je XML vjerna reprodukcija originala.
    """
    STATUS_CHOICES = [
        ('pending', _('Na cekanju')),
        ('extracted', _('Ekstrahirano')),
        ('xml_generated', _('XML generiran')),
        ('validated', _('Validirano')),
        ('failed', _('Neuspjelo')),
    ]
    CONFIDENCE_CHOICES = [
        ('high', _('Visoko (>90%)')),
        ('medium', _('Srednje (70-90%)')),
        ('low', _('Nisko (<70%)')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name=_('Tvrtka'))
    arhiva_entry = models.ForeignKey('ArhivaEntry', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='conversions', verbose_name=_('Arhivski zapis'))

    # Originalna datoteka
    original_filename = models.CharField(max_length=255, verbose_name=_('Originalni naziv'))
    original_size = models.IntegerField(verbose_name=_('Originalna velicina (bytes)'))
    original_hash = models.CharField(max_length=128, verbose_name=_('SHA-256 originala'))
    original_content_type = models.CharField(max_length=100, verbose_name=_('MIME tip originala'))
    original_path = models.CharField(max_length=500, blank=True, verbose_name=_('Putanja originala'))

    # AI ekstrakcija
    ai_model = models.CharField(max_length=200, default='gemini-2.5-flash', verbose_name=_('AI model'),
                                  help_text='Override via settings.CONVERSION_AI_MODEL')
    ai_prompt_version = models.CharField(max_length=50, default='v1.0', verbose_name=_('Verzija prompta'))
    ai_confidence = models.CharField(max_length=30, choices=CONFIDENCE_CHOICES, default='medium',
                                      verbose_name=_('Pouzdanost AI'))
    ai_confidence_score = models.FloatField(default=0.0, verbose_name=_('Tocnost (0-1)'))
    ai_response_tokens = models.IntegerField(default=0, verbose_name=_('Tokeni odgovora'))
    ai_cost_eur = models.DecimalField(max_digits=6, decimal_places=4, default=0, verbose_name=_('Cijena (EUR)'))

    # Ekstrahirani podaci (JSON snapshot)
    extracted_data = models.JSONField(default=dict, verbose_name=_('Ekstrahirani podaci'))

    # Generirani XML
    xml_content = models.TextField(blank=True, verbose_name=_('Generirani XML'))
    xml_hash = models.CharField(max_length=128, blank=True, verbose_name=_('SHA-256 XML-a'))
    xml_size = models.IntegerField(default=0, verbose_name=_('Velicina XML (bytes)'))
    xml_path = models.CharField(max_length=500, blank=True, verbose_name=_('Putanja XML-a'))

    # Validacija
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name=_('Status'))
    validation_errors = models.JSONField(default=list, verbose_name=_('Greske validacije'))
    is_valid = models.BooleanField(default=False, verbose_name=_('Validirano'))

    # Usporedba: dokaz vjernosti
    size_reduction_pct = models.FloatField(default=0, verbose_name=_('Smanjenje velicine (%)'))
    fields_extracted = models.IntegerField(default=0, verbose_name=_('Broj ekstrahiranih polja'))
    items_extracted = models.IntegerField(default=0, verbose_name=_('Broj stavki'))

    # Audit
    created_by = models.ForeignKey(_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name=_('Kreirao'))
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _('Konverzijski zapis')
        verbose_name_plural = _('Konverzijski zapisi')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status'], name='conv_co_status_idx'),
            models.Index(fields=['original_hash'], name='conv_orig_hash_idx'),
        ]

    def __str__(self):
        return f"Konverzija: {self.original_filename} ({self.get_status_display()})"

    @property
    def savings_display(self):
        if self.original_size and self.xml_size:
            return f"{self.original_size // 1024}KB -> {self.xml_size // 1024}KB ({self.size_reduction_pct:.0f}%)"
        return "-"


# ═══════════════════════════════════════════════════════
#  SCAN BATCH — BORG FENIX Asimilator računa
# ═══════════════════════════════════════════════════════

class ScanBatch(models.Model):
    """Batch sesija za grupno skeniranje do 100 dokumenata."""

    STATUS_CHOICES = [
        ('collecting', 'Prikupljanje'),
        ('processing', 'OCR obrada'),
        ('grouping', 'AI grupiranje'),
        ('ready', 'Spreman za arhivu'),
        ('done', 'Arhivirano'),
        ('error', 'Greška'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='scan_batches')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='collecting')
    total_images = models.PositiveIntegerField(default=0)
    total_size_kb = models.PositiveIntegerField(default=0)
    total_documents = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Scan Batch'
        verbose_name_plural = 'Scan Batches'
        ordering = ['-created_at']

    def __str__(self):
        return f'Batch #{self.pk} — {self.total_images} slika ({self.get_status_display()})'


class ScanBatchImage(models.Model):
    """Pojedinačna slika unutar batch sesije."""

    batch = models.ForeignKey(ScanBatch, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='scan_batches/%Y/%m/')
    order = models.PositiveIntegerField(default=0)
    original_filename = models.CharField(max_length=255, blank=True, default='')
    file_size_kb = models.PositiveIntegerField(default=0)
    # AI grupiranje
    document_group = models.PositiveIntegerField(null=True, blank=True,
        help_text='Koji dokument (1, 2, 3...)')
    page_in_group = models.PositiveIntegerField(null=True, blank=True,
        help_text='Koja stranica unutar dokumenta')
    ai_confidence = models.FloatField(null=True, blank=True)
    # OCR rezultat
    extracted_text = models.TextField(blank=True, default='')
    extracted_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Scan slika'
        ordering = ['batch', 'order']

    def __str__(self):
        group = f' [dok.{self.document_group}]' if self.document_group else ''
        return f'Slika #{self.order}{group} — batch #{self.batch_id}'
