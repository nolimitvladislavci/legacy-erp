# CC Task — WhatsApp: dodaj send_document funkciju

## Problem
core/whatsapp.py ima send_text ali nema send_document.
Udruge task treba slati PDF dokumente direktno na WhatsApp.

## KORAK 1 — Pročitaj
```bash
cat /var/www/fina-connect/core/whatsapp.py
grep -r "WAHA" /var/www/fina-connect/core/settings.py | head -10
```

## KORAK 2 — Dodaj send_document u core/whatsapp.py

WAHA endpoint za slanje fajla: POST /api/sendFile
```python
def send_document(phone: str, file_path: str, caption: str = '', company_id: str = None) -> dict:
    """
    Pošalji PDF/dokument via WAHA gateway.
    file_path: apsolutna putanja do lokalnog fajla
    Vraća {'ok': True} ili {'error': '...'}
    """
    # 1. normalize_phone (već postoji)
    # 2. rate_check (već postoji)
    # 3. WAHA: POST /api/sendFile
    #    multipart: file=open(file_path,'rb'), chatId=f'{phone}@c.us', caption=caption
    # 4. Fallback: ako WAHA ne podržava sendFile, pošalji send_text s putanjom
    pass
```

## KORAK 3 — Test
```python
# /tmp/test_send_doc.py
from core.whatsapp import send_document
result = send_document('385991908089', '/tmp/test.pdf', 'Test dokument')
print(result)
```

## KORAK 4 — Javi
Napiši /tmp/send_document_done.txt s "OK" i WAHA response kodom.

## Definicija DONE
- [ ] send_document postoji u core/whatsapp.py
- [ ] Nema sintaksnih grešaka (python -c "from core.whatsapp import send_document")
- [ ] Test prolazi ili vraća jasnu grešku
