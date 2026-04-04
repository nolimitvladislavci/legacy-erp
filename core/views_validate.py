"""
core/views_validate.py — CroValidator API
POST /api/v1/validate/ — validacija OIB, IBAN, MBS
"""
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from core.oib_validator import validate_oib_hr, validate_hr_iban, validate_iban, validate_mbs


@csrf_exempt
@require_POST
def api_validate(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    result = {}

    if 'oib' in data:
        oib = str(data['oib']).strip()
        valid = validate_oib_hr(oib)
        result['oib'] = {
            'valid': valid,
            'value': oib,
            'error': None if valid else 'OIB nije valjan (modulo 11)',
        }

    if 'iban' in data:
        iban = str(data['iban']).strip()
        valid = validate_hr_iban(iban) if iban.upper().startswith('HR') else validate_iban(iban)
        result['iban'] = {
            'valid': valid,
            'value': iban,
            'error': None if valid else 'IBAN nije valjan (MOD 97)',
        }

    if 'mbs' in data:
        mbs = str(data['mbs']).strip()
        valid = validate_mbs(mbs)
        result['mbs'] = {
            'valid': valid,
            'value': mbs,
            'error': None if valid else 'MBS mora imati točno 8 znamenki',
        }

    return JsonResponse(result)
