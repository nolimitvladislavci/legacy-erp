# GEMINI_TASK_ARHIVA_F2 — Rate-Limited AI Pipeline + Multi-page Grouper
## Agent: Gemini | Prioritet: P0 | Danas
## Preduvjet: CC_TASK_ARHIVA_F1 mora biti u tijeku (ne mora biti DONE)

**Čitaj:** ARHIVA_MASTER_PLAN.md, documents/conversion_service.py, documents/tasks.py  
**Nikad ne pretpostavljaj modele — cat models.py prije pisanja koda.**

---

## MISIJA

Tvoj zadatak je mozak arhivskog pipeline-a:
1. Rate-limitiran Celery pipeline za Gemini (10 req/min)
2. Haiku multi-page grouper (koji račun spada na koje stranice)
3. Celery chord orchestracija (grupe od 10, pauza između)

---

## ZADATAK 1: Rate-Limited Gemini Pipeline

### Problem koji riješavaš

Postojeći `process_scan_batch` task u `documents/tasks.py` nema rate limiting.  
Za 100 slika → Gemini 2.5-Flash → probija free tier limit (10 req/min).

### Rješenje: Celery chord s grupama

```python
# documents/tasks.py — dodaj ove taskove

from celery import chord, group
import time

GEMINI_RATE_LIMIT = 10    # max poziva po minuti
GEMINI_BATCH_SIZE = 10    # slika po grupi
GEMINI_PAUSE_SEC  = 62    # pauza između grupa (malo više od minute)


@shared_task(bind=True, soft_time_limit=120, name='documents.gemini_extract_single')
def gemini_extract_single(self, image_id: int, batch_id: int) -> dict:
    """
    Procesira JEDNU sliku kroz Gemini 2.5-Flash.
    Vraća extracted_data ili error dict.
    
    Rate: koristi se samo unutar gemini_extract_batch grupe (max 10/min)
    """
    from documents.models import ScanBatchImage
    from documents.conversion_service import extract_invoice_data_gemini
    import time
    
    try:
        img = ScanBatchImage.objects.get(pk=image_id)
        
        with open(img.image.path, 'rb') as f:
            file_bytes = f.read()
        
        data = extract_invoice_data_gemini(file_bytes, img.original_filename or 'image.jpg')
        
        img.extracted_data = data
        img.ai_confidence = data.get('confidence', 0.9)
        img.save(update_fields=['extracted_data', 'ai_confidence'])
        
        return {'ok': True, 'image_id': image_id, 'invoice_number': data.get('invoice_number', '?')}
        
    except Exception as e:
        logger.error('gemini_extract_single failed img %s: %s', image_id, e)
        return {'ok': False, 'image_id': image_id, 'error': str(e)[:200]}


@shared_task(bind=True, soft_time_limit=90, name='documents.gemini_batch_group_pause')
def gemini_batch_group_pause(self, results: list, batch_id: int, group_index: int, total_groups: int) -> dict:
    """
    Callback koji se poziva NAKON svake grupe od 10 slika.
    Dodaje pauzu ako ima još grupa — poštuje rate limit.
    Ažurira progress.
    """
    from documents.models import ScanBatch
    
    try:
        batch = ScanBatch.objects.get(pk=batch_id)
        processed = (group_index + 1) * GEMINI_BATCH_SIZE
        batch.error_message = f'AI obradio {min(processed, batch.total_images)}/{batch.total_images} slika...'
        batch.save(update_fields=['error_message', 'updated_at'])
    except Exception:
        pass
    
    # Pauza ako ima još grupa
    if group_index < total_groups - 1:
        logger.info('Rate limit pause %ds nakon grupe %d/%d', GEMINI_PAUSE_SEC, group_index+1, total_groups)
        time.sleep(GEMINI_PAUSE_SEC)
    
    return {'group_done': group_index, 'results': results}


@shared_task(bind=True, soft_time_limit=3600, name='documents.process_scan_batch_v2')
def process_scan_batch_v2(self, batch_id: int) -> dict:
    """
    NOVA verzija process_scan_batch — s rate limitingom i Haiku grupiranjem.
    
    Pipeline:
    1. Haiku klasifikacija (brzo, svaka slika) 
    2. Gemini ekstrakcija u grupama od 10 (rate limited)
    3. Haiku multi-page grouping
    4. Batch status → ready
    """
    from documents.models import ScanBatch, ScanBatchImage
    
    try:
        batch = ScanBatch.objects.get(pk=batch_id)
    except ScanBatch.DoesNotExist:
        return {'error': 'batch_not_found'}
    
    images = list(batch.images.all().order_by('order'))
    if not images:
        batch.status = 'error'
        batch.error_message = 'Nema slika'
        batch.save(update_fields=['status', 'error_message'])
        return {'error': 'no_images'}
    
    batch.status = 'processing'
    batch.error_message = f'Priprema {len(images)} slika za AI...'
    batch.save(update_fields=['status', 'error_message', 'updated_at'])
    
    # ── FAZA 1: Haiku klasifikacija (brzo, sinhrono) ──────────────────
    for img in images:
        try:
            result = haiku_classify_image_sync(img.image.path)
            img.extracted_text = result.get('page_type', 'unknown')
            # Pohrani hint za grouper
            if not img.extracted_data:
                img.extracted_data = {}
            img.extracted_data['haiku_hint'] = result
            img.save(update_fields=['extracted_text', 'extracted_data'])
        except Exception as e:
            logger.warning('Haiku classification failed img %s: %s', img.pk, e)
    
    # ── FAZA 2: Gemini ekstrakcija u grupama ─────────────────────────
    image_groups = [images[i:i+GEMINI_BATCH_SIZE] for i in range(0, len(images), GEMINI_BATCH_SIZE)]
    total_groups = len(image_groups)
    
    batch.status = 'processing'
    batch.error_message = f'AI analizira slike (0/{len(images)})...'
    batch.save(update_fields=['status', 'error_message', 'updated_at'])
    
    # Sinhrona obrada grupa s pauzom između (izbjegavamo Celery chord kompleksnost)
    for group_idx, img_group in enumerate(image_groups):
        # Obradi grupu od 10
        for img in img_group:
            try:
                result = gemini_extract_single_sync(img.image.path, img.original_filename)
                img.extracted_data = {**(img.extracted_data or {}), **result}
                img.ai_confidence = result.get('confidence', 0.85)
                img.save(update_fields=['extracted_data', 'ai_confidence'])
            except Exception as e:
                logger.error('Gemini extract failed img %s: %s', img.pk, e)
        
        # Progress update
        processed = (group_idx + 1) * GEMINI_BATCH_SIZE
        batch.error_message = f'AI analizira slike ({min(processed, len(images))}/{len(images)})...'
        batch.save(update_fields=['error_message', 'updated_at'])
        
        # Pauza između grupa (rate limit)
        if group_idx < total_groups - 1:
            logger.info('Rate limit pauza %ds (grupa %d/%d)', GEMINI_PAUSE_SEC, group_idx+1, total_groups)
            time.sleep(GEMINI_PAUSE_SEC)
    
    # ── FAZA 3: Haiku multi-page grouping ────────────────────────────
    batch.status = 'grouping'
    batch.error_message = 'Spajam stranice višestraničnih računa...'
    batch.save(update_fields=['status', 'error_message', 'updated_at'])
    
    # Osvježi images iz baze (imaju extracted_data)
    images = list(batch.images.all().order_by('order'))
    grouping = haiku_group_multipage(images)
    
    for img, group_num in zip(images, grouping):
        pages_in_group = grouping.count(group_num)
        page_in_group = [i for i, g in enumerate(grouping) if g == group_num].index(grouping.index(group_num)) + 1
        img.document_group = group_num
        img.page_in_group = page_in_group
        img.save(update_fields=['document_group', 'page_in_group'])
    
    # Završi
    unique_groups = len(set(grouping))
    batch.status = 'ready'
    batch.total_documents = unique_groups
    batch.error_message = f'Gotovo! Pronađeno {unique_groups} dokumenata iz {len(images)} slika.'
    batch.save(update_fields=['status', 'total_documents', 'error_message', 'updated_at'])
    
    return {'ok': True, 'images': len(images), 'documents': unique_groups}
```

---

## ZADATAK 2: haiku_group_multipage funkcija

```python
def haiku_group_multipage(images: list) -> list:
    """
    Haiku analizira niz slika i vraća listu grupa.
    
    Input: [ScanBatchImage, ...]
    Output: [0, 0, 1, 2, 2, 2, 3] — svaki broj = koji dokument
    
    Logika:
    - Isti dobavljač + kontinuitet stranica = isti dokument
    - "Stranica 1/3", "Seite 2 von 3" = višestranični
    - Drugačiji OIB dobavljača = novi dokument
    """
    import anthropic
    client = anthropic.Anthropic()
    
    if not images:
        return []
    
    # Pripremi sažetak svakog dokumenta za Haiku
    image_summaries = []
    for i, img in enumerate(images):
        data = img.extracted_data or {}
        hint = data.get('haiku_hint', {})
        image_summaries.append({
            'index': i,
            'page_type': hint.get('page_type', 'unknown'),
            'needs_grouping': hint.get('needs_grouping_with_previous', False),
            'vendor_name': data.get('seller', {}).get('name', ''),
            'vendor_oib': data.get('seller', {}).get('oib', ''),
            'invoice_number': data.get('invoice_number', ''),
            'ocr_text_start': (img.extracted_text or '')[:200],
        })
    
    prompt = f"""
Analiziraj ove slike skeniranih računa i grupiraj ih u dokumente.

Slike (ukupno {len(images)}):
{__import__('json').dumps(image_summaries, ensure_ascii=False, indent=2)}

Pravila grupiranja:
1. Isti dobavljač (ime ili OIB) + stranica 2 od N → isti dokument
2. Tekst "Stranica X/Y", "Seite X von Y", "Page X of Y" → višestranični
3. "Fortsetzung", "Nastavak", "continued" → nastavak prethodnog
4. Različit OIB dobavljača → novi dokument (čak ako ista stranica)
5. Ako nisi siguran → novi dokument (bolje previše nego premalo)

Vrati SAMO JSON array s grupnim brojevima (0-indexed), bez objašnjenja:
[0, 0, 1, 2, 2, 2, 3, 4, 4]

Za {len(images)} slika vrati točno {len(images)} brojeva.
"""
    
    try:
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = msg.content[0].text.strip()
        
        # Parse JSON array
        import re, json
        match = re.search(r'\[[\d,\s]+\]', text)
        if match:
            groups = json.loads(match.group())
            if len(groups) == len(images):
                return groups
    except Exception as e:
        logger.warning('haiku_group_multipage failed: %s', e)
    
    # Fallback: svaka slika = zaseban dokument
    return list(range(len(images)))
```

---

## ZADATAK 3: haiku_classify_image_sync

```python
def haiku_classify_image_sync(image_path: str) -> dict:
    """
    Brza Haiku klasifikacija jedne slike.
    Vraća: is_invoice, page_type, needs_grouping, vendor_hint, amount_hint
    """
    import anthropic, base64
    client = anthropic.Anthropic()
    
    with open(image_path, 'rb') as f:
        data = f.read()
    
    # Detect MIME
    mime = 'image/jpeg'
    if data[:4] == bytes([0x89, 0x50, 0x4e, 0x47]):
        mime = 'image/png'
    elif data[:4] == b'RIFF':
        mime = 'image/webp'
    
    b64 = base64.b64encode(data).decode()
    
    try:
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=200,
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': mime, 'data': b64}},
                    {'type': 'text', 'text': '''Analiziraj ovu sliku. Vrati SAMO JSON bez objašnjenja:
{
  "is_invoice": true/false,
  "page_type": "first"|"continuation"|"summary"|"unknown",
  "needs_grouping_with_previous": true/false,
  "vendor_hint": "naziv dobavljača ili prazan string",
  "amount_hint": "ukupni iznos kao string ili prazan",
  "currency": "EUR"|"USD"|"HRK"|"prazan"
}'''}
                ]
            }]
        )
        import json, re
        text = msg.content[0].text.strip()
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.warning('haiku_classify_image_sync: %s', e)
    
    return {'is_invoice': True, 'page_type': 'first', 'needs_grouping_with_previous': False}
```

---

## ZADATAK 4: gemini_extract_single_sync

Omotač oko postojeće `extract_invoice_data_gemini` funkcije:

```python
def gemini_extract_single_sync(image_path: str, filename: str = '') -> dict:
    """Sinkroni wrapper za Gemini ekstrakciju."""
    from documents.conversion_service import extract_invoice_data_gemini
    
    with open(image_path, 'rb') as f:
        data = f.read()
    
    return extract_invoice_data_gemini(data, filename or 'image.jpg')
```

---

## DONE kriterij

```python
# Test u Django shellu
from documents.tasks import process_scan_batch_v2
# Provjeri da je task registriran
from celery import current_app
assert 'documents.process_scan_batch_v2' in current_app.tasks
print('✅ Gemini F2 DONE')
```
