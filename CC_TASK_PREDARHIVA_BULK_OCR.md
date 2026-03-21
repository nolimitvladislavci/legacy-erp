# CC_TASK_PREDARHIVA_BULK_OCR
# Izvršava: CC Code
# Koordinira: Sonnet
# Prioritet: VISOK — gorući problem Marije Brtan (Konjik d.o.o.)
# Datum: 2026-03-21
#
# KONTEKST (obavezno pročitati):
# Marija ima stotine/tisuće papirnatih računa (mobitel + skener + email).
# Gorući problem: nema načina učitati 1000 slika odjednom i prepustiti AI da radi.
# Trenutni smart_import prima fajlove ali šalje odmah na Gemini — nema "predkomore".
# Plan: Staging area → Gemini queue s rate limitom → live progress → spajanje → arhiva.
#
# PROČITAJ PRVO:
# 1. smart_import/models.py — ImportBatch, GeminiUsageLog
# 2. smart_import/tasks.py — process_import_batch, _process_multipage
# 3. smart_import/services.py — parse_image, _encode_image, _gemini_vision_extract
# 4. smart_import/views.py — upload_view, stage_view

---

## ŠTO GRADIŠ — 4 KOMPONENTE

---

### KOMPONENTA 1: StagingBatch model

Novi model u smart_import/models.py:

```python
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
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    objects = CompanyManager()
    title = models.CharField(max_length=200, blank=True, default='',
        help_text='Npr. "Računi veljača 2026" — za lakše snalaženje')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_files = models.IntegerField(default=0)
    processed_files = models.IntegerField(default=0)
    failed_files = models.IntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_message = models.CharField(max_length=500, blank=True, default='',
        help_text='Zadnja poruka od AI — "Razmišljanje na glas"')

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
        ('skipped', 'Preskočeno — duplikat'),
    ]
    staging_batch = models.ForeignKey(StagingBatch, on_delete=models.CASCADE,
        related_name='files')
    file = models.FileField(upload_to='staging/%Y/%m/')
    original_filename = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    # Rezultat AI obrade
    result_batch = models.ForeignKey('ImportBatch', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='staging_source')
    ai_message = models.CharField(max_length=500, blank=True,
        help_text='Što je AI rekao za ovaj fajl — za live prikaz')
    error_msg = models.TextField(blank=True)
    # Detekcija multi-page
    page_group = models.CharField(max_length=50, blank=True,
        help_text='Ako je isti račun na više slika — isti group_id')
    position_in_group = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
```

### KOMPONENTA 2: Bulk upload view

Nova view: `staging_upload_view` u smart_import/views.py

```python
@login_required
def staging_upload(request):
    """
    Bulk upload — Marija učita 1000 slika odjednom.
    Fajlovi idu u StagingBatch, AI NIJE pokrenut još.
    Korisnik vidi sve fajlove u pregledu, može ih pregledati,
    pa klikne "Pokreni AI obradu".
    """
```

- Podržava multiple file upload (input multiple)
- Drag & drop zona (HTML5 API)
- Prikazuje thumbnail svake slike odmah (browser FileReader API)
- Prikazuje ukupan broj fajlova i procijenjeno vrijeme
- Gumb "Pokreni obradu" → POST → pokreće Celery task
- Prikazuje duplikat upozorenje ako isti filename već postoji u arhivi

**URL:** `/smart-import/staging/`
**Template:** `smart_import/staging.html`

### KOMPONENTA 3: Rate-limited Celery task

Nova task funkcija: `process_staging_batch` u smart_import/tasks.py

```python
@shared_task(bind=True, soft_time_limit=7200, time_limit=7800)  # 2 sata max
def process_staging_batch(self, staging_batch_id):
    """
    Obrađuje StagingBatch s rate limitingom.
    8 req/min prema Gemini (slobodan tier limit).
    Svaki fajl = 1 ImportBatch = 1 Gemini request.
    Live progress updates u StagingBatch.last_message.
    """
    from django.utils import timezone
    import time
    from smart_import.models import StagingBatch, StagingFile, ImportBatch
    from smart_import.services import parse_image, match_items

    RATE_LIMIT_DELAY = 7.5  # sekundi između requestova (8/min = 7.5s interval)
    MAX_CONSECUTIVE_ERRORS = 10  # pauza ako previše grešaka zaredom

    try:
        staging = StagingBatch.objects.get(pk=staging_batch_id)
    except StagingBatch.DoesNotExist:
        return

    staging.status = 'processing'
    staging.started_at = timezone.now()
    staging.save(update_fields=['status', 'started_at'])

    pending_files = staging.files.filter(status='pending').order_by('created_at')
    consecutive_errors = 0

    for idx, sf in enumerate(pending_files):
        # Live message — "razmišljanje na glas"
        staging.last_message = f"Čitam sliku {staging.processed_files + 1}/{staging.total_files}: {sf.original_filename}"
        staging.save(update_fields=['last_message'])

        sf.status = 'processing'
        sf.save(update_fields=['status'])

        try:
            # Koristi postojeći parse_image iz services.py
            rows = parse_image(sf.file.path)

            if not rows:
                # Enhanced retry
                from smart_import.services import parse_image_enhanced
                rows = parse_image_enhanced(sf.file.path)

            if rows:
                # Kreiraj ImportBatch iz rezultata
                batch = ImportBatch.objects.create(
                    company=staging.company,
                    file=sf.file,
                    file_type='image',
                    status='ready',
                    original_filename=sf.original_filename,
                    raw_json=rows,
                    created_by=staging.created_by,
                )
                for i, row in enumerate(rows):
                    from smart_import.models import ImportBatchItem
                    ImportBatchItem.objects.create(
                        batch=batch,
                        row_index=i,
                        vendor_name=row.get('vendor_name', ''),
                        quantity=row.get('quantity', 1),
                        purchase_price=row.get('purchase_price', 0),
                    )
                match_items(batch)

                # Izvuci AI sažetak za prikaz
                supplier_name = rows[0].get('vendor_name', '?') if rows else '?'
                total = sum(float(r.get('purchase_price', 0)) * float(r.get('quantity', 1)) for r in rows)
                sf.ai_message = f"Prepoznato: {len(rows)} stavki, dobavljač: {supplier_name[:30]}, iznos: {total:.2f} EUR"
                sf.result_batch = batch
                sf.status = 'done'
                consecutive_errors = 0

                staging.last_message = f"Slika {staging.processed_files + 1}/{staging.total_files} — {sf.ai_message}"

            else:
                sf.status = 'error'
                sf.error_msg = 'AI nije prepoznao stavke u slici'
                sf.ai_message = 'Nije prepoznato — provjeri ručno'
                staging.failed_files += 1
                consecutive_errors += 1

        except Exception as e:
            sf.status = 'error'
            sf.error_msg = str(e)[:300]
            staging.failed_files += 1
            consecutive_errors += 1

        sf.processed_at = timezone.now()
        sf.save(update_fields=['status', 'ai_message', 'result_batch', 'error_msg', 'processed_at'])

        staging.processed_files += 1
        staging.save(update_fields=['processed_files', 'failed_files', 'last_message'])

        # Rate limit — čekaj između requestova
        if idx < len(pending_files) - 1:
            time.sleep(RATE_LIMIT_DELAY)

        # Pauza ako previše grešaka zaredom (429 ili API down)
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            staging.last_message = f"Previše grešaka ({consecutive_errors}) — pauza 60s..."
            staging.save(update_fields=['last_message'])
            time.sleep(60)
            consecutive_errors = 0

    # Završetak
    staging.status = 'done' if staging.failed_files == 0 else 'done_with_errors'
    staging.finished_at = timezone.now()
    failed = staging.failed_files
    done = staging.processed_files - failed
    staging.last_message = f"Gotovo! {done} računa obrađeno, {failed} nije prepoznato."
    staging.save(update_fields=['status', 'finished_at', 'last_message'])
```

### KOMPONENTA 4: Live progress UI

#### View za progress polling:
```python
@login_required
def staging_progress_api(request, pk):
    """AJAX endpoint — polling svakih 3 sekunde iz JS."""
    staging = get_object_or_404(StagingBatch, pk=pk, company=get_user_company(request))
    recent_files = staging.files.filter(status__in=['done','error']).order_by('-processed_at')[:5]
    return JsonResponse({
        'status': staging.status,
        'progress_pct': staging.progress_pct,
        'processed': staging.processed_files,
        'total': staging.total_files,
        'failed': staging.failed_files,
        'last_message': staging.last_message,
        'estimated_minutes': staging.estimated_minutes_remaining,
        'recent': [
            {
                'filename': f.original_filename,
                'message': f.ai_message,
                'status': f.status,
            } for f in recent_files
        ],
        'is_done': staging.status in ('done', 'done_with_errors'),
    })
```

#### Template staging_progress.html:
```html
<!-- Progress bar + live log -->
<div class="staging-progress">
  <div class="progress-bar">
    <div class="progress-fill" id="progressFill" style="width: 0%"></div>
  </div>
  <p id="progressText">Priprema...</p>
  <p id="timeEstimate"></p>

  <div class="ai-log" id="aiLog">
    <!-- Živi log poruka od AI — "razmišljanje na glas" -->
  </div>

  <div class="recent-files" id="recentFiles">
    <!-- Zadnjih 5 obrađenih fajlova -->
  </div>
</div>

<script>
function pollProgress(stagingId) {
  fetch(`/smart-import/staging/${stagingId}/progress/`)
    .then(r => r.json())
    .then(data => {
      document.getElementById('progressFill').style.width = data.progress_pct + '%';
      document.getElementById('progressText').textContent =
        `${data.processed}/${data.total} računa obrađeno (${data.failed} greška)`;

      if (data.estimated_minutes > 0) {
        document.getElementById('timeEstimate').textContent =
          `Procijenjeno još: ~${data.estimated_minutes} minuta`;
      }

      // AI log poruka
      const log = document.getElementById('aiLog');
      if (data.last_message) {
        const p = document.createElement('p');
        p.className = 'log-entry';
        p.textContent = data.last_message;
        log.insertBefore(p, log.firstChild);
        if (log.children.length > 20) log.lastChild.remove();
      }

      // Recent files
      const recent = document.getElementById('recentFiles');
      recent.innerHTML = data.recent.map(f =>
        `<div class="file-entry ${f.status}">
          <span class="filename">${f.filename}</span>
          <span class="message">${f.message}</span>
        </div>`
      ).join('');

      if (!data.is_done) {
        setTimeout(() => pollProgress(stagingId), 3000);
      } else {
        document.getElementById('progressText').textContent = data.last_message;
        document.getElementById('timeEstimate').textContent = '';
        // Prikaz gumba za pregled rezultata
        document.getElementById('viewResultsBtn').style.display = 'block';
      }
    });
}
// Pokreni polling čim se stranica učita
document.addEventListener('DOMContentLoaded', () => pollProgress(STAGING_ID));
</script>
```

---

## MULTI-PAGE DETEKCIJA (bonus feature — ako ima vremena)

Problem: jedna faktura = 3 slike (stranica 1, stranica 2, detalj)

Logika za grupiranje:
- Ako dvije slike imaju isti datum + isti OIB dobavljača iz OCR-a → vjerojatno isti račun
- UI: Marija može ručno "spojiti" više StagingFile-ova u jedan račun
- Gumb "Spoji odabrane" → kreira jedan ImportBatch od više slika

Ovo implementiraj SAMO ako ostane vremena. Nije blocker za MVP.

---

## DE TRŽIŠTE — Gemini prompt za njemačke račune

U smart_import/services.py, dodaj alternativni prompt za DE:

```python
DE_INVOICE_PROMPT = (
    "You are an expert invoice OCR parser for German business documents. "
    "Common German terms: Rechnung=invoice, Lieferschein=delivery note, "
    "Artikel/Bezeichnung=item name, Menge/Anzahl=quantity, "
    "Einzelpreis/Preis=unit price, Betrag/Gesamt=total, "
    "MwSt/USt=VAT, Netto=net, Brutto=gross, "
    "Rechnungsnummer=invoice number, Lieferdatum=delivery date, "
    "Steuernummer/USt-IdNr=tax ID. "
    "Extract ALL line items. "
    "Return ONLY a JSON array: "
    '[{"vendor_name": "<item>", "quantity": <n>, "purchase_price": <unit_price>}]. '
    "If quantity is unclear, use 1. If price not visible, use 0."
)
```

Detekcija jezika: ako `company.country == 'DE'` → koristi DE prompt.

---

## URLS (dodati u smart_import/urls.py)

```python
path('staging/', views.staging_upload, name='staging_upload'),
path('staging/<int:pk>/', views.staging_detail, name='staging_detail'),
path('staging/<int:pk>/start/', views.staging_start, name='staging_start'),
path('staging/<int:pk>/progress/', views.staging_progress_api, name='staging_progress_api'),
path('staging/<int:pk>/results/', views.staging_results, name='staging_results'),
```

---

## MIGRACIJE

```bash
python manage.py makemigrations smart_import --name "add_staging_batch"
python manage.py migrate
```

---

## TESTIRANJE

```bash
python manage.py shell -c "
from smart_import.models import StagingBatch
from companies.models import Company
konjik = Company.objects.filter(name__icontains='Konjik').first()
sb = StagingBatch.objects.create(company=konjik, title='Test batch', total_files=3)
print('StagingBatch kreiran:', sb.pk, sb.status, sb.progress_pct)
"
```

---

## GOTOVO KAD

- [ ] StagingBatch + StagingFile modeli postoje, migracije aplicirane
- [ ] /smart-import/staging/ radi — drag & drop, multiple files
- [ ] "Pokreni obradu" gumb pokreće process_staging_batch Celery task
- [ ] /smart-import/staging/{pk}/progress/ vraća JSON s progressom
- [ ] Live progress stranica osvježava svakih 3s bez page refresh
- [ ] Rate limit funkcionira — ne šalje više od 8 req/min Geminiju
- [ ] DE prompt dodan za kompanije s country='DE'
- [ ] git commit: "Predarhiva: StagingBatch bulk OCR s live progressom"
- [ ] Upiši DONE u FENIX_STATUS.md

---

## NAPOMENA ZA MARIJU

Kad je feature live, Marija dobiva ovaj workflow:
1. Otvori /smart-import/staging/
2. Drag & drop 1000 slika (ili odaberi sve s mobitela)
3. Vidi listu s thumbnailovima — može pregledati
4. Klikne "Pokreni AI obradu"
5. Vidi live log: "Čitam sliku 47/1000 — Horvat d.o.o., 1.240 EUR"
6. Nakon ~2 sata: "Gotovo! 987 računa obrađeno, 13 nije prepoznato"
7. Pregledava neprepoznate ručno, potvrđuje ostale
8. Sve ide u arhivu

Trošak za Mariju: 0.15 EUR po 1000 slika.
Ivan ne radi ništa.
