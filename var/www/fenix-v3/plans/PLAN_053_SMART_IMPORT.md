# PLAN_053 — Smart Import (AI Import Računa — Slika/PDF/XML)

## Cilj
Marija uploaduje gomilu faktura (slika, PDF, XML). Smart Import ih paralelno procesira OCR-om, AI predlaže knjiženje, ona odobrava jednim klikom. Ovo je najvažniji workflow za bookkeeper onboarding. Ušteda: 4 sata/dan → 15 minuta.

## Razlika vs. /arhiva/upload/
- /arhiva/upload/ = jedan po jedan, manual
- /smart-import/ = batch upload, bulk AI obrada, single-approve flow
- Arhiva je storage+archive, Smart Import je workflow+approve

## URL struktura
```
/hr/smart-import/                    → SmartImportView (main)
/hr/smart-import/upload/             → SmartImportUploadView (POST, multipart)
/hr/smart-import/status/<batch_id>/  → SmartImportStatusView (HTMX polling)
/hr/smart-import/approve/<entry_id>/ → SmartImportApproveView (POST)
/hr/smart-import/approve-all/        → SmartImportApproveAllView (POST, bulk)
/hr/smart-import/reject/<entry_id>/  → SmartImportRejectView (POST)
```

## Model: ImportBatch
```python
class ImportBatch(TenantModel):
    """
    Batch upload skup. Svaki upload kreira jedan batch.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="import_batches")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Status(models.TextChoices):
        UPLOADING = "uploading", "Uploadanje"
        PROCESSING = "processing", "AI obrada"
        REVIEW = "review", "Čeka pregled"
        DONE = "done", "Završeno"
        ERROR = "error", "Greška"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADING)
    total_files = models.IntegerField(default=0)
    processed_files = models.IntegerField(default=0)
    approved_files = models.IntegerField(default=0)
    failed_files = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True)

    @property
    def progress_pct(self):
        if self.total_files == 0:
            return 0
        return int((self.processed_files / self.total_files) * 100)

    @property
    def pending_review(self):
        return self.entries.filter(status=ArhivaEntry.AIStatus.DONE, approved=False, rejected=False).count()
```

## ArhivaEntry extended fields za Smart Import
```python
# Dodati u ArhivaEntry model (iz PLAN_025):
import_batch = models.ForeignKey(
    "smart_import.ImportBatch",
    null=True, blank=True,
    on_delete=models.SET_NULL,
    related_name="entries"
)
approved = models.BooleanField(default=False)
approved_by = models.ForeignKey(
    settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
)
approved_at = models.DateTimeField(null=True)
rejected = models.BooleanField(default=False)
rejection_note = models.CharField(max_length=200, blank=True)
```

## Celery task: process_import_batch
```python
@shared_task(bind=True, base=AITask, queue="heavy")
def process_import_batch(self, batch_id: str):
    """
    Za svaki fajl u batchu:
    1. OCR (FenixScan) — iz PLAN_027
    2. AI booking suggestion
    3. Update ArhivaEntry fields
    4. Update batch progress
    """
    batch = ImportBatch.objects.get(id=batch_id)
    batch.status = ImportBatch.Status.PROCESSING
    batch.save()

    entries = ArhivaEntry.objects.filter(import_batch=batch)

    for entry in entries:
        try:
            # OCR (reuse iz PLAN_027)
            from arhiva.tasks import ocr_document
            result = FenixScan().scan(entry.file.path)
            
            # Update entry s OCR rezultatima
            entry.vendor_name = result.get("vendor_name", "")
            entry.document_number = result.get("invoice_number", "")
            entry.total_amount = Decimal(str(result.get("total_amount", 0)))
            entry.vat_amount = Decimal(str(result.get("vat_amount", 0)))
            entry.net_amount = entry.total_amount - entry.vat_amount
            entry.document_date = parse_date(result.get("date", ""))
            entry.ai_raw_response = result
            entry.ai_status = ArhivaEntry.AIStatus.DONE

            # AI booking suggestion
            suggestion = ai_suggest_booking_sync(entry)
            entry.ai_suggestion = suggestion
            entry.save()

            batch.processed_files = models.F("processed_files") + 1
            batch.save(update_fields=["processed_files"])

        except Exception as e:
            logger.error(f"Smart import failed for entry {entry.id}: {e}")
            entry.ai_status = ArhivaEntry.AIStatus.ERROR
            entry.ai_error = str(e)
            entry.save()
            batch.failed_files = models.F("failed_files") + 1
            batch.save(update_fields=["failed_files"])

    batch.refresh_from_db()
    batch.status = ImportBatch.Status.REVIEW
    batch.save()
```

## SmartImportView (main)
```python
class SmartImportView(TenantView):
    template_name = "smart_import/main.html"
    permission_required = Permission.UPLOAD_DOCUMENTS

    def get(self, request):
        active_batches = ImportBatch.objects.filter(
            company=request.company,
            status__in=[ImportBatch.Status.UPLOADING, ImportBatch.Status.PROCESSING,
                       ImportBatch.Status.REVIEW],
        ).prefetch_related("entries").order_by("-created_at")[:5]

        pending_entries = ArhivaEntry.objects.filter(
            company=request.company,
            import_batch__isnull=False,
            approved=False,
            rejected=False,
            ai_status=ArhivaEntry.AIStatus.DONE,
        ).select_related("import_batch").order_by("-created_at")

        return render(request, self.template_name, {
            "active_batches": active_batches,
            "pending_entries": pending_entries,
            "pending_count": pending_entries.count(),
        })
```

## SmartImportUploadView
```python
class SmartImportUploadView(TenantView):
    permission_required = Permission.UPLOAD_DOCUMENTS

    def post(self, request):
        files = request.FILES.getlist("files")
        if not files:
            return JsonResponse({"ok": False, "error": "Nisu odabrani fajlovi."}, status=400)
        if len(files) > 50:
            return JsonResponse({"ok": False, "error": "Max 50 fajlova po uploadu."}, status=400)

        batch = ImportBatch.objects.create(
            company=request.company,
            created_by=request.user,
            total_files=len(files),
            status=ImportBatch.Status.UPLOADING,
        )

        for f in files:
            if f.size > 20 * 1024 * 1024:  # 20MB
                continue
            if not f.content_type.startswith(("image/", "application/pdf")):
                continue
            entry = ArhivaEntry.objects.create(
                company=request.company,
                import_batch=batch,
                doc_type="ulazni_racun",  # default — AI može promijeniti
                ai_status=ArhivaEntry.AIStatus.PENDING,
                created_by=request.user,
            )
            entry.file.save(f.name, f, save=True)

        batch.status = ImportBatch.Status.PROCESSING
        batch.save()
        process_import_batch.delay(str(batch.id))

        return JsonResponse({
            "ok": True,
            "batch_id": str(batch.id),
            "total_files": batch.total_files,
        })
```

## SmartImportStatusView (HTMX polling)
```python
class SmartImportStatusView(TenantView):
    def get(self, request, batch_id):
        batch = get_object_or_404(ImportBatch, id=batch_id, company=request.company)
        
        if request.headers.get("HX-Request"):
            # Vraća partial template za progress bar
            return render(request, "smart_import/partials/batch_progress.html", {
                "batch": batch,
                "refresh": batch.status in [ImportBatch.Status.PROCESSING, ImportBatch.Status.UPLOADING],
            })
        
        return JsonResponse({
            "status": batch.status,
            "progress": batch.progress_pct,
            "processed": batch.processed_files,
            "total": batch.total_files,
            "pending_review": batch.pending_review,
        })
```

## SmartImportApproveView
```python
class SmartImportApproveView(TenantView):
    permission_required = Permission.APPROVE_DOCUMENTS

    def post(self, request, entry_id):
        entry = get_object_or_404(
            ArhivaEntry,
            id=entry_id,
            company=request.company,
            approved=False,
        )
        # Korisnik može editovati AI prijedlog
        data = json.loads(request.body)
        entry.vendor_name = data.get("vendor_name", entry.vendor_name)
        entry.document_number = data.get("document_number", entry.document_number)
        entry.total_amount = Decimal(str(data.get("total_amount", entry.total_amount)))
        entry.document_date = data.get("document_date", entry.document_date)
        entry.doc_type = data.get("doc_type", entry.doc_type)
        entry.approved = True
        entry.approved_by = request.user
        entry.approved_at = timezone.now()
        entry.save()

        # Update batch counter
        if entry.import_batch:
            ImportBatch.objects.filter(id=entry.import_batch_id).update(
                approved_files=models.F("approved_files") + 1
            )

        return JsonResponse({"ok": True, "entry_id": str(entry.id)})
```

## SmartImportApproveAllView (bulk approve)
```python
class SmartImportApproveAllView(TenantView):
    permission_required = Permission.APPROVE_DOCUMENTS

    def post(self, request):
        batch_id = request.POST.get("batch_id")
        qs = ArhivaEntry.objects.filter(
            company=request.company,
            approved=False,
            rejected=False,
            ai_status=ArhivaEntry.AIStatus.DONE,
        )
        if batch_id:
            qs = qs.filter(import_batch_id=batch_id)

        count = qs.count()
        qs.update(approved=True, approved_by=request.user, approved_at=timezone.now())

        messages.success(request, f"{count} dokumenata odobreno.")
        return redirect("smart_import:main")
```

## Template: smart_import/main.html
Alpine.js `smartImport()`:

```html
<div x-data="smartImport()">
  <!-- Upload zona -->
  <div class="card mb-6">
    <h2 class="text-lg font-semibold mb-3">Upload faktura</h2>
    
    <!-- Drag & Drop zona -->
    <div
      @dragover.prevent="dragOver = true"
      @dragleave="dragOver = false"
      @drop.prevent="handleDrop($event)"
      :class="dragOver ? 'border-fenix-500 bg-fenix-50' : 'border-gray-300'"
      class="border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors"
      @click="$refs.fileInput.click()"
    >
      <input type="file" x-ref="fileInput" multiple accept="image/*,.pdf"
             @change="handleFiles($event.target.files)" class="hidden">
      
      <div class="text-4xl mb-3">📁</div>
      <p class="text-gray-600">Prevucite fakture ovdje ili kliknite za odabir</p>
      <p class="text-sm text-gray-400 mt-1">PDF, JPG, PNG — max 50 fajlova, 20MB/fajl</p>
      
      <!-- File list preview -->
      <div x-show="selectedFiles.length > 0" class="mt-4 text-left">
        <template x-for="file in selectedFiles" :key="file.name">
          <div class="flex items-center gap-2 py-1">
            <span class="text-green-500">✓</span>
            <span class="text-sm" x-text="file.name"></span>
            <span class="text-xs text-gray-400" x-text="formatSize(file.size)"></span>
          </div>
        </template>
      </div>
    </div>

    <button @click="upload()" :disabled="selectedFiles.length === 0 || uploading"
            class="btn-primary mt-4" :class="uploading ? 'opacity-50' : ''">
      <span x-show="!uploading">Pokrenuti AI Import</span>
      <span x-show="uploading" class="flex items-center gap-2">
        <span class="spinner"></span> Uploadanje...
      </span>
    </button>
  </div>

  <!-- Active batches (HTMX polling) -->
  <template x-for="batch in activeBatches" :key="batch.id">
    <div class="card mb-4"
         hx-get="/hr/smart-import/status/:batch_id/"
         hx-trigger="every 3s [batch.status === 'processing']"
         hx-swap="outerHTML">
      <!-- batch_progress.html partial -->
    </div>
  </template>

  <!-- Pending review -->
  <div x-show="pendingCount > 0" class="card">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold">
        Čeka pregled
        <span class="badge-warning ml-2" x-text="pendingCount"></span>
      </h2>
      <button @click="approveAll()" class="btn-primary">
        Odobri sve (jednim klikom)
      </button>
    </div>

    <!-- Entry cards -->
    <template x-for="entry in pendingEntries" :key="entry.id">
      <div class="border rounded-lg p-4 mb-3 flex gap-4">
        <!-- Thumbnail -->
        <img :src="entry.thumbnail_url" class="w-16 h-16 object-cover rounded border">
        
        <!-- AI extracted data (editable) -->
        <div class="flex-1 grid grid-cols-2 gap-3">
          <div>
            <label class="label text-xs">Dobavljač</label>
            <input type="text" x-model="entry.vendor_name" class="input input-sm">
          </div>
          <div>
            <label class="label text-xs">Broj računa</label>
            <input type="text" x-model="entry.document_number" class="input input-sm">
          </div>
          <div>
            <label class="label text-xs">Iznos (EUR)</label>
            <input type="number" step="0.01" x-model="entry.total_amount" class="input input-sm">
          </div>
          <div>
            <label class="label text-xs">Datum</label>
            <input type="date" x-model="entry.document_date" class="input input-sm">
          </div>
        </div>

        <!-- AI confidence badge -->
        <div class="flex flex-col items-center justify-center w-20">
          <div class="text-2xl font-bold"
               :class="entry.ai_confidence > 0.8 ? 'text-green-600' : 'text-yellow-600'"
               x-text="Math.round(entry.ai_confidence * 100) + '%'">
          </div>
          <div class="text-xs text-gray-400">AI točnost</div>
        </div>

        <!-- Actions -->
        <div class="flex flex-col gap-2">
          <button @click="approve(entry)" class="btn-primary btn-sm">✓ Odobri</button>
          <button @click="reject(entry)" class="btn-danger btn-sm">✗ Odbaci</button>
          <button @click="preview(entry)" class="btn-secondary btn-sm">👁 Pregled</button>
        </div>
      </div>
    </template>
  </div>
</div>
```

## AI Confidence Score
FenixScan._parse_response() treba vratiti `confidence` (0.0–1.0):
```python
def _calculate_confidence(self, extracted: dict) -> float:
    score = 0.0
    if extracted.get("vendor_name"): score += 0.2
    if extracted.get("invoice_number"): score += 0.2
    if extracted.get("total_amount") and float(extracted["total_amount"]) > 0: score += 0.3
    if extracted.get("date"): score += 0.2
    if extracted.get("vat_amount"): score += 0.1
    return round(score, 2)
```

## XML import (UBL / e-Račun)
```python
def handle_xml_upload(entry: ArhivaEntry) -> dict:
    """
    Ako je fajl XML → parse UBL 2.1 direktno bez OCR.
    Mnogo brže i točnije od OCR-a.
    """
    tree = ET.parse(entry.file.path)
    root = tree.getroot()
    ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
          "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"}
    
    return {
        "invoice_number": root.findtext(".//cbc:ID", namespaces=ns),
        "date": root.findtext(".//cbc:IssueDate", namespaces=ns),
        "vendor_name": root.findtext(".//cac:AccountingSupplierParty//cbc:Name", namespaces=ns),
        "total_amount": root.findtext(".//cbc:PayableAmount", namespaces=ns),
        "confidence": 0.99,  # XML je gotovo uvijek točan
        "source": "xml_parse",
    }
```

## Testovi
```python
def test_smart_import_batch_created_on_upload(auth_client, company):
    files = [SimpleUploadedFile("inv1.pdf", b"...", content_type="application/pdf")]
    resp = auth_client.post("/hr/smart-import/upload/", {"files": files})
    assert resp.status_code == 200
    assert ImportBatch.objects.filter(company=company).count() == 1

def test_approve_all_marks_entries(auth_client, company):
    batch = ImportBatch.objects.create(company=company, ...)
    entries = [ArhivaEntryFactory(company=company, import_batch=batch, ai_status="done") for _ in range(5)]
    resp = auth_client.post("/hr/smart-import/approve-all/", {"batch_id": str(batch.id)})
    assert ArhivaEntry.objects.filter(import_batch=batch, approved=True).count() == 5

def test_xml_parsed_without_ocr(company):
    xml_content = open("tests/fixtures/sample_ubl.xml").read()
    result = handle_xml_upload(mock_entry_with_xml(xml_content))
    assert result["confidence"] == 0.99
    assert result["vendor_name"] is not None
```
