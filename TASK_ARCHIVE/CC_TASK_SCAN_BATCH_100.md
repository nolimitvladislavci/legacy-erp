# CC_TASK — SCAN BATCH 100 + UI 2 TIPKE
# Agent: Claude Code
# Prioritet: VISOK — Faza 1 BORG FENIX
# Datum: 2026-03-23

## KONTEKST
Gradimo "asimilator računa" — korisnik slika do 100 računa, AI ih obrađuje grupno.
Ovo je jedinstven feature na DE tržištu. Konkurencija obrađuje 1 po 1.

## ZADACI

### 1. Django model — ScanBatch
```python
# U arhiva/ app-u (gdje je OCR infrastruktura)
# Model koji drži batch sesiju
class ScanBatch(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('collecting', 'Prikupljanje'),
        ('processing', 'Procesiranje'),
        ('grouping', 'Grupiranje stranica'),
        ('ready', 'Spreman za knjiženje'),
        ('done', 'Proknjiženo'),
    ], default='collecting')
    total_images = models.PositiveIntegerField(default=0)
    total_size_kb = models.PositiveIntegerField(default=0)
    
class ScanBatchImage(models.Model):
    batch = models.ForeignKey(ScanBatch, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='scan_batches/%Y/%m/')
    order = models.PositiveIntegerField()
    # AI će postaviti ovo:
    document_group = models.PositiveIntegerField(null=True, blank=True)  # koji dokument
    page_in_group = models.PositiveIntegerField(null=True, blank=True)   # koja stranica
    ai_confidence = models.FloatField(null=True, blank=True)
    # OCR rezultat:
    extracted_data = models.JSONField(null=True, blank=True)
```

### 2. View — batch_upload_view
- POST prima slike (multipart, do 100)
- Na klijentskoj strani: Canvas API kompresija u WebP, max 800px širina, quality 0.75
- Server: prima, sprema, pokreće Celery task
- Return: JSON sa batch_id

### 3. Celery task — process_scan_batch
- Koristi postojeći OCR (FenixCamera/arhiva OCR pipeline)
- Za svaku sliku: OCR → extracted_data
- Haiku API call za grupiranje (pogledaj GROUPING TASK ispod)
- Update batch.status u svakom koraku

### 4. UI — 2 TIPKE FILOZOFIJA
Template: arhiva/scan_batch.html

FAZA 1 (prazan):
- Drag & drop zona
- Tipka 1: "📷 Snimi" (kamera, mobile)
- Tipka 2: "📁 Učitaj"
- Progress: "0 od 100 slika"

FAZA 2 (slike dodane):
- Mini grid previewa (5 po redu, thumbnail)
- Tipka 1: "✓ Proknjižit sve" (primary, info boja)  
- Tipka 2: "📷 Dodaj još" (secondary)
- Sekundarne (pojavljuju se, nisu sive): "⚙ Spoji stranice" | "🗑 Očisti"

FAZA 3 (AI gotov):
- Lista prepoznatih dokumenata
- Tipka 1: "✓ Spremi u arhivu" (primary, success boja)
- Tipka 2: "Pregledaj" (secondary)

JAVASCRIPT:
- Kompresija na klijentskoj strani PRIJE uploada (Canvas.toBlob WebP)
- Real-time progress bar (polling /api/batch/{id}/status/)
- Auto-detect višestraničnih (badge "2str" na thumbnail)

### 5. URL-ovi
```
/hr/arhiva/scan/batch/new/     — nova batch sesija
/hr/arhiva/scan/batch/<id>/    — pregled sesije
/api/arhiva/batch/<id>/status/ — JSON status za polling
/api/arhiva/batch/<id>/upload/ — upload chunk
```

## PROVJERI PRIJE PISANJA KODA
1. Čitaj: arhiva/models.py (postojeći modeli — ne dupliciraj)
2. Čitaj: arhiva/views.py (OCR pipeline — iskoristi)
3. Čitaj: arhiva/tasks.py (Celery taskovi — poveži)
4. Provjeri je li WebP upload podržan u ImageField

## DONE KRITERIJ
- [ ] Batch od 23 slike se uploada za <5 sekundi
- [ ] AI grupira višestranične u iste dokumente
- [ ] UI ima max 2 vidljive tipke u svakom trenutku
- [ ] Proknjiženi dokumenti idu u arhiva/Document model
- [ ] Test: scan_tests.py min 10 testova
