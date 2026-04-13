"""
W1C — Kamera/AI unos inventara
Korisnik slika artikl (barcode, etiketa, račun) →
Haiku/Vision analizira → vraća strukturirane podatke
Math sanity check: price*qty > 50.000 EUR → odbaci
"""
import logging
import base64
import hashlib
from decimal import Decimal, InvalidOperation
from django.conf import settings

logger = logging.getLogger('inventory.camera')

MATH_SANITY_LIMIT = Decimal('50000.00')  # EUR — sanity check


def parse_camera_input(image_b64: str, company_id=None) -> dict:
    """
    Analiziraj sliku i izvuci podatke o artiklu.

    Args:
        image_b64: Base64 enkodirana slika (JPEG/PNG)
        company_id: Za rate limiting i audit

    Returns:
        {
            'name': str,
            'qty': float,
            'price': float,
            'barcode': str|None,
            'unit': str,
            'confidence': float (0.0-1.0),
            'raw_haiku': str,
            'error': str|None
        }
    """
    if not image_b64:
        return _error('Nema slike')

    try:
        # Dekodiraj i provjeri veličinu
        image_bytes = base64.b64decode(image_b64)
        if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
            return _error('Slika prevelika (max 10MB)')

        # Pozovi Haiku Vision
        result = _call_haiku_vision(image_b64, image_bytes)
        if result.get('error'):
            return result

        # Math sanity check (Dron #4)
        qty = Decimal(str(result.get('qty', 1)))
        price = Decimal(str(result.get('price', 0)))
        total = qty * price

        if total > MATH_SANITY_LIMIT:
            logger.warning(f'Camera input odbijen: {qty}x{price}={total} > {MATH_SANITY_LIMIT}')
            return _error(f'Sanity check: {qty}×{price}={total:.2f} EUR prelazi limit od {MATH_SANITY_LIMIT} EUR. Provjeri unos.')

        result['total_calculated'] = float(total)
        return result

    except (ValueError, TypeError) as e:
        logger.error(f'camera_input greška: {e}')
        return _error(str(e))


def _call_haiku_vision(image_b64: str, image_bytes: bytes) -> dict:
    """Pozovi Claude Haiku Vision za analizu slike."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Odredi media type
        media_type = 'image/jpeg'
        if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            media_type = 'image/png'

        response = client.messages.create(
            model=getattr(settings, 'HAIKU_MODEL', 'claude-haiku-4-5-20251001'),
            max_tokens=300,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': media_type,
                            'data': image_b64,
                        }
                    },
                    {
                        'type': 'text',
                        'text': (
                            'Analiziraj sliku. Izvuci podatke o artiklu.\n'
                            'Odgovori SAMO JSON bez ikakvih dodatnih objašnjenja:\n'
                            '{"name":"naziv artikla","qty":1.0,"price":0.0,"barcode":"brojčanik ili null","unit":"kom","confidence":0.8}\n'
                            'qty i price su decimalni brojevi. confidence je 0.0-1.0.'
                        )
                    }
                ]
            }]
        )

        import json, re
        text = response.content[0].text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return {
                'name': str(data.get('name', ''))[:200],
                'qty': float(data.get('qty', 1.0)),
                'price': float(data.get('price', 0.0)),
                'barcode': data.get('barcode'),
                'unit': str(data.get('unit', 'kom')),
                'confidence': float(data.get('confidence', 0.5)),
                'raw_haiku': text[:200],
                'error': None,
            }
        return _error(f'Haiku nije vratio JSON: {text[:100]}')

    except (json.JSONDecodeError, ValueError) as e:
        return _error(f'Haiku Vision greška: {e}')


def _error(msg: str) -> dict:
    return {
        'name': '', 'qty': 0.0, 'price': 0.0,
        'barcode': None, 'unit': 'kom',
        'confidence': 0.0, 'raw_haiku': '',
        'error': msg
    }
