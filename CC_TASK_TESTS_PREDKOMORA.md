# CC_TASK_TESTS_PREDKOMORA

## Cilj
Napisati Django testove za sve što je implementirano danas (21.03.2026):
1. StagingFileHeader + auto_match_partner()
2. extract_invoice_header() mock
3. process_staging_batch Celery task (header integration)
4. review_approve Zamka 2 (matematika) + Zamka 3 (concurrent conflict)
5. Predkomora review dashboard view
6. Duplikat detekcija (isti OIB + invoice_number + total)

## Fajl za pisanje
`smart_import/tests_predkomora.py` — NOVI fajl, ne dira existing tests.py

## Precizna uputa

### Test 1: StagingFileHeader.auto_match_partner() — OIB match
```
- Kreiraj Company, Partner s oib='12345678901'
- Kreiraj StagingBatch, StagingFile, StagingFileHeader(supplier_oib='12345678901')
- Pozovi header.auto_match_partner()
- Assert: header.matched_partner == partner
- Assert: vraća partner objekt
```

### Test 2: auto_match_partner() — OIB ne postoji
```
- StagingFileHeader(supplier_oib='99999999999') bez odgovarajućeg Partnera
- auto_match_partner() → vraća None
- header.matched_partner ostaje None
```

### Test 3: auto_match_partner() — prazan OIB
```
- StagingFileHeader(supplier_oib='')
- auto_match_partner() → vraća None odmah (bez DB query-ja)
```

### Test 4: extract_invoice_header() mock — uspješan poziv
```
- Mock Gemini response koji vraća JSON:
  '{"supplier_name":"Lidl d.o.o.","supplier_oib":"12345678901","invoice_number":"R-2026/001","invoice_date":"2026-03-21","total_amount":124.99,"vat_amount":20.83,"base_amount":104.16,"currency":"EUR","confidence":0.95}'
- Pozovi extract_invoice_header('/tmp/fake.jpg') s patched _genai.Client
- Assert: vraća dict s točnim ključevima
- Assert: supplier_oib == '12345678901'
- Assert: total_amount == 124.99
- Assert: confidence == 0.95
```

### Test 5: extract_invoice_header() — Gemini puca
```
- Mock Gemini da baci Exception
- Assert: vraća {} (ne crashes)
```

### Test 6: extract_invoice_header() — nevažeći JSON u odgovoru
```
- Mock Gemini response: 'Evo vam nešto' (nije JSON)
- Assert: vraća {} (ne crashes)
```

### Test 7: process_staging_batch — header se kreira
```
- Kreiraj StagingBatch, StagingFile s realnom slikom (1px PNG)
- Mock parse_image() → vraća [{'vendor_name':'Lidl','quantity':1,'purchase_price':10}]
- Mock extract_invoice_header() → vraća {'supplier_name':'Lidl','supplier_oib':'12345678901','total_amount':10,'confidence':0.9,...}
- Pozovi process_staging_batch(staging_batch.pk) direktno (ne async)
- Assert: StagingFileHeader.objects.filter(staging_file=sf).exists() == True
- Assert: header.supplier_name == 'Lidl'
- Assert: header.confidence == 0.9
```

### Test 8: process_staging_batch — header greška ne ruši task
```
- Mock parse_image() → vraća stavke OK
- Mock extract_invoice_header() → baci Exception
- Assert: StagingFile.status == 'done' (task završio OK)
- Assert: ImportBatch kreiran
- Assert: StagingFileHeader NE postoji (greška uhvaćena)
```

### Test 9: process_staging_batch — auto-match partner
```
- Partner(oib='12345678901') postoji u bazi
- Mock extract_invoice_header() → {'supplier_oib':'12345678901','supplier_name':'X',...}
- Assert: batch.supplier == partner
- Assert: header.matched_partner == partner
```

### Test 10: Duplikat detekcija
```
- Kreiraj 2 StagingFile-a u istom batchu
- Oba imaju isti OIB + invoice_number + total_amount
- Nakon procesa prvog: header.needs_review = False (normalno)
- Nakon procesa drugog: header.needs_review = True (duplikat!)
- Assert: drugi header.needs_review == True
- U ai_message: 'DUPLIKAT?'
```

### Test 11: review_approve — Zamka 2 (matematika)
```
- POST /smart-import/review/approve/ s:
  base_amount=100.00, vat_amount=25.00, total_amount=200.00 (razlika > 0.02)
- Assert: HTTP 400
- Assert: response['code'] == 'MATH_MISMATCH'
- Assert: header.needs_review ostaje True
```

### Test 12: review_approve — Zamka 2 prolazi (ispravna matematika)
```
- base=100, vat=25, total=125 (točno, diff=0)
- Assert: HTTP 200, ok=True
- Assert: header.needs_review == False
```

### Test 13: review_approve — Zamka 3 (concurrent conflict)
```
- header.needs_review = False (već proknjiženo)
- POST review_approve s header_id
- Assert: HTTP 409
- Assert: response['code'] == 'CONFLICT'
```

### Test 14: review_approve — OIB korekcija + re-match
```
- Header inicijalno: supplier_oib='00000000000', matched_partner=None
- Partner postoji za OIB '12345678901'
- POST review_approve s supplier_oib='12345678901', ispravna matematika
- Assert: header.matched_partner == partner
- Assert: HTTP 200
```

### Test 15: Predkomora view — samo needs_review headers
```
- Kreiraj 3 headerа: 2 needs_review=True, 1 needs_review=False
- GET /smart-import/predkomora/
- Assert: HTTP 200
- Assert: 2 headera u contextu, ne 1
```

## Model setup helpers (copy-paste)

```python
def _make_staging_batch(company, user):
    from smart_import.models import StagingBatch
    return StagingBatch.objects.create(
        company=company, created_by=user,
        status='pending', total_files=1,
    )

def _make_staging_file(batch, filename='test.jpg'):
    from django.core.files.base import ContentFile
    from smart_import.models import StagingFile
    import struct, zlib
    # Minimalni 1px PNG
    def _1px_png():
        sig = b'\x89PNG\r\n\x1a\n'
        def chunk(t, d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
        ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
        idat = chunk(b'IDAT', zlib.compress(b'\x00\xff\xff\xff'))
        iend = chunk(b'IEND', b'')
        return sig+ihdr+idat+iend
    sf = StagingFile(staging_batch=batch, original_filename=filename, status='pending')
    sf.file.save(filename, ContentFile(_1px_png()), save=True)
    return sf

def _make_header(sf, oib='12345678901', invoice_number='R-001', total='100.00'):
    from smart_import.models import StagingFileHeader
    from decimal import Decimal
    return StagingFileHeader.objects.create(
        staging_file=sf,
        supplier_name='Test d.o.o.',
        supplier_oib=oib,
        invoice_number=invoice_number,
        total_amount=Decimal(total),
        vat_amount=Decimal('16.67'),
        base_amount=Decimal('83.33'),
        confidence=0.85,
        needs_review=True,
    )
```

## Gdje pokrenuti

```bash
cd /var/www/fina-connect
source venv/bin/activate
python manage.py test smart_import.tests_predkomora --verbosity=2
```

## Napomena za CC Code
- Koristi `@patch('smart_import.services._genai')` za Gemini mock
- Celery task pozivaj direktno: `process_staging_batch(batch.pk)` (bez .delay())
- `TransactionTestCase` za Zamku 3 (select_for_update ne radi u TestCase)
- Čitaj STVARNA polja iz smart_import/models.py — NE pretpostavljaj nazive
