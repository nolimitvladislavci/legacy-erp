"""
rental/ocr.py — OCR MRZ extraction via Haiku Vision

Svaki dokument ima MRZ (Machine Readable Zone) — strojno čitljivi dio na dnu.
Haiku Vision čita sliku i vraća strukturirane podatke.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)


def extract_mrz_with_haiku(image_path: str) -> dict:
    """
    Haiku Vision čita MRZ iz slike dokumenta.

    Returns: {
        'first_name': 'IVAN',
        'last_name': 'BRTAN',
        'date_of_birth': '1991-01-01',
        'document_number': 'AB123456',
        'nationality': 'HRV',
        'sex': 'M',
        'expiry_date': '2026-01-01',
        'document_type': 'passport',
        'confidence': 0.95,
    }
    """
    import base64

    with open(image_path, 'rb') as f:
        data = f.read()

    mime = 'image/jpeg'
    if data[:4] == bytes([0x89, 0x50, 0x4e, 0x47]):
        mime = 'image/png'

    try:
        import anthropic
        client = anthropic.Anthropic()

        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=400,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': mime,
                            'data': base64.b64encode(data).decode(),
                        },
                    },
                    {
                        'type': 'text',
                        'text': (
                            'Pročitaj MRZ (Machine Readable Zone) s ovog dokumenta.\n'
                            'MRZ su redovi s velikim slovima, brojevima i "<" na dnu dokumenta.\n\n'
                            'Vrati SAMO JSON bez komentara:\n'
                            '{\n'
                            '  "document_type": "passport|id_card|driving_license|unknown",\n'
                            '  "first_name": "",\n'
                            '  "last_name": "",\n'
                            '  "date_of_birth": "YYYY-MM-DD ili null",\n'
                            '  "document_number": "",\n'
                            '  "nationality": "3-slovna ISO šifra npr HRV DEU AUT",\n'
                            '  "sex": "M|F|X",\n'
                            '  "expiry_date": "YYYY-MM-DD ili null",\n'
                            '  "issuing_country": "3-slovna ISO šifra",\n'
                            '  "confidence": 0.95\n'
                            '}\n\n'
                            'Ako ne možeš pročitati MRZ, postavi confidence=0.0.'
                        ),
                    },
                ],
            }],
        )

        text = msg.content[0].text.strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            result = json.loads(match.group())
            # Normalize HRC → HRV
            if result.get('nationality') == 'HRC':
                result['nationality'] = 'HRV'
            return result

    except ImportError:
        logger.warning('anthropic SDK not installed — OCR disabled')
    except (json.JSONDecodeError, ValueError) as e:
        logger.error('OCR MRZ extraction failed: %s', e)

    return {'confidence': 0.0, 'document_type': 'unknown'}


def apply_ocr_to_guest(guest_document_pk: int) -> dict:
    """Celery-friendly: OCR → popuni Guest polja."""
    from rental.models import GuestDocument

    doc = GuestDocument.objects.get(pk=guest_document_pk)
    result = extract_mrz_with_haiku(doc.image.path)

    doc.ocr_raw = result
    doc.ocr_confidence = result.get('confidence', 0)
    doc.ocr_processed = True
    doc.save()

    if result.get('confidence', 0) > 0.5:
        guest = doc.guest
        if result.get('first_name') and not guest.first_name:
            guest.first_name = result['first_name'].title()
        if result.get('last_name') and not guest.last_name:
            guest.last_name = result['last_name'].title()
        if result.get('date_of_birth'):
            from datetime import date
            try:
                guest.date_of_birth = date.fromisoformat(result['date_of_birth'])
            except (ValueError, TypeError):
                pass
        if result.get('document_number'):
            guest.document_number = result['document_number']
        if result.get('nationality'):
            guest.nationality = result['nationality']
        if result.get('sex'):
            guest.sex = result['sex']
        if result.get('document_type'):
            guest.document_type = result['document_type']
        if result.get('document_country') or result.get('issuing_country'):
            guest.document_country = result.get('document_country') or result.get('issuing_country', '')
        guest.save()

    return result
