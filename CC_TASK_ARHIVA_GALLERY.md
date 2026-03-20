# CC Task — Arhiva: Gallery-first upload + async konverzija

## Filozofija
Spremi odmah → konvertiraj u pozadini → galerija je uvijek točna

```
Korisnik → upload original (bilo koji format, bilo koja veličina)
         ↓ odmah (< 1s)
         ArhivaEntry kreiran, status='processing'
         Prikaže se u galeriji odmah s "⏳ Obrađujem..."
         ↓ Celery async (3-10s)
         Konverzija → JPEG 2048px + thumbnail 400px
         AI analiza → partner, iznos, datum
         status='ready'
         Galerija se automatski updatea
```

## Korak 1 — Migracija (dodaj polja na ArhivaEntry)

Čitaj PRAVO stanje modela:
```bash
grep -n "thumbnail\|processing_status\|thumb_path\|conv_status" \
  /var/www/fina-connect/documents/models.py | head -10
```

Ako NE postoje, dodaj u class ArhivaEntry (documents/models.py):
```python
# Gallery / processing
thumbnail_path = models.CharField(max_length=500, blank=True, default='',
    verbose_name='Thumbnail putanja')
processing_status = models.CharField(max_length=20, default='ready',
    choices=[
        ('processing', 'Obrađujem'),
        ('ready', 'Spremno'),
        ('error', 'Greška'),
    ],
    verbose_name='Status obrade')
processing_error = models.CharField(max_length=200, blank=True, default='')
original_size_kb = models.IntegerField(default=0)
converted_size_kb = models.IntegerField(default=0)
```

Kreiraj i pokreni migraciju:
```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations documents --name arhiva_gallery
venv/bin/python manage.py migrate documents
```

## Korak 2 — Celery task za konverziju

Dodaj u /var/www/fina-connect/documents/tasks.py:

```python
@shared_task(bind=True, max_retries=3)
def process_arhiva_image(self, entry_id):
    """Konverzija originalne slike u JPEG + thumbnail, async."""
    try:
        from documents.models import ArhivaEntry
        from documents.storage import store_document
        import os

        entry = ArhivaEntry.objects.get(pk=entry_id)
        if not entry.has_image or not entry.file_path:
            return 'skip_not_image'

        # Čitaj original
        from django.core.files.storage import default_storage
        try:
            with default_storage.open(entry.file_path, 'rb') as f:
                raw = f.read()
        except Exception:
            # Pokušaj direktno s putanjom
            full = '/var/www/fina-connect/media/' + entry.file_path.lstrip('/')
            if not os.path.exists(full):
                entry.processing_status = 'error'
                entry.processing_error = 'Original ne postoji'
                entry.save(update_fields=['processing_status','processing_error'])
                return 'error_no_file'
            raw = open(full,'rb').read()

        # PIL konverzija
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(raw))
        if img.mode not in ('RGB','L'):
            img = img.convert('RGB')

        # Full: 2048px max, 82% quality
        MAX_W = 2048
        if img.width > MAX_W:
            ratio = MAX_W / img.width
            img = img.resize((MAX_W, int(img.height * ratio)), Image.LANCZOS)
        
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=82, optimize=True)
        jpeg_bytes = buf.getvalue()

        # Spremi konvertiranu verziju
        conv_filename = os.path.splitext(os.path.basename(entry.file_path))[0] + '_conv.jpg'
        conv_result = store_document(
            file_bytes=jpeg_bytes,
            filename=conv_filename,
            company_id=str(entry.company_id),
            source_type='image_converted',
        )

        # Thumbnail: 400px
        thumb_img = img.copy()
        thumb_img.thumbnail((400, 400), Image.LANCZOS)
        thumb_buf = io.BytesIO()
        thumb_img.save(thumb_buf, 'JPEG', quality=75)
        thumb_bytes = thumb_buf.getvalue()

        thumb_filename = os.path.splitext(os.path.basename(entry.file_path))[0] + '_thumb.jpg'
        thumb_result = store_document(
            file_bytes=thumb_bytes,
            filename=thumb_filename,
            company_id=str(entry.company_id),
            source_type='image_thumbnail',
        )

        # Ažuriraj entry
        entry.file_path = conv_result['path']
        entry.thumbnail_path = thumb_result['path']
        entry.converted_size_kb = len(jpeg_bytes) // 1024
        entry.processing_status = 'ready'
        entry.save(update_fields=[
            'file_path','thumbnail_path','converted_size_kb',
            'processing_status','updated_at'
        ])

        logger.info(f'arhiva image processed: entry={entry_id}, '
                    f'{entry.original_size_kb}KB -> {entry.converted_size_kb}KB')
        return 'ok'

    except Exception as exc:
        logger.error(f'process_arhiva_image failed: {exc}')
        try:
            ArhivaEntry.objects.filter(pk=entry_id).update(
                processing_status='error',
                processing_error=str(exc)[:200]
            )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=30)
```

## Korak 3 — Upload view: spremi odmah, triggeri async

U documents/views.py, funkcija arhiva_upload, ZAMIJENI logiku:

Trenutno: spremi → kreiraj ArhivaEntry → trigger AI

Novo:
```python
# Nakon store_document():
original_size_kb = len(file_bytes) // 1024  # file_bytes = uploaded.read()
is_image = result.get('content_type','').startswith('image/') or \
           uploaded.name.lower().endswith(('.jpg','.jpeg','.png','.heic','.heif','.webp'))

new_entry = ArhivaEntry.objects.create(
    company=company,
    source_type=source_type,
    source_id=result.get('hash',''),
    doc_number=request.POST.get('doc_number', uploaded.name),
    partner_name=request.POST.get('partner_name',''),
    amount=Decimal(str(request.POST.get('amount', 0) or 0)),
    currency=request.POST.get('currency','EUR'),
    doc_date=request.POST.get('doc_date') or timezone.now().date(),
    file_path=result['path'],
    has_pdf=uploaded.name.lower().endswith('.pdf'),
    has_xml=uploaded.name.lower().endswith('.xml'),
    has_image=is_image,
    archived_by=request.user,
    session_key=request.session.session_key or '',
    original_size_kb=original_size_kb,
    processing_status='processing' if is_image else 'ready',
)

# Async obrada slike
if is_image:
    from documents.tasks import process_arhiva_image
    process_arhiva_image.apply_async(args=[new_entry.pk], countdown=1)
    messages.success(request,
        f'Slika primljena ({original_size_kb}KB). '
        f'Obrađujem u pozadini...')
else:
    messages.success(request, f'Dokument arhiviran.')

# AI analiza (PDF i slike kad su obrađene)
if new_entry.has_pdf:
    try:
        from documents.tasks import generate_ai_proposal
        generate_ai_proposal.apply_async(args=[new_entry.pk], countdown=3)
    except Exception as e:
        logger.warning('AI trigger failed: %s', e)
```

## Korak 4 — Galerija u arhiva_list.html

Dodaj thumbnail prikaz u listu. Pronađi red gdje se prikazuju dokumenti i dodaj:

```html
{% if entry.thumbnail_path %}
  <img src="{{ entry.thumbnail_path }}" 
       style="width:48px;height:48px;object-fit:cover;border-radius:4px;margin-right:8px;vertical-align:middle"
       loading="lazy">
{% elif entry.processing_status == 'processing' %}
  <span style="font-size:1.2rem">⏳</span>
{% elif entry.has_image %}
  <span style="font-size:1.2rem">🖼️</span>
{% elif entry.has_pdf %}
  <span style="font-size:1.2rem">📄</span>
{% endif %}
```

Za "processing" status — auto-refresh za te redove:
```javascript
// Ako ima processing entryja, provjeri svakih 5s
var processing = document.querySelectorAll('[data-status="processing"]');
if (processing.length > 0) {
  setTimeout(function() { window.location.reload(); }, 5000);
}
```

## Korak 5 — PIL instaliran?
```bash
cd /var/www/fina-connect
venv/bin/python -c "from PIL import Image; print('PIL OK')" 2>&1
# Ako nije:
venv/bin/pip install Pillow --break-system-packages
```

## Provjere
```bash
cd /var/www/fina-connect
venv/bin/python manage.py check 2>&1 | tail -2
venv/bin/python manage.py showmigrations documents 2>&1 | tail -5
systemctl restart gunicorn-fina celery-worker
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/documents/arhiva/upload/
```

## Javi
- Je li migracija aplicirana
- Je li PIL instaliran
- Je li process_arhiva_image u tasks.py
- Django check status
