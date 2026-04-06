"""
fenix_input/views.py — API endpointi za sve ulazne kanale

1. /api/fenix-input/voice/     — POST transkripciju s frontenda
2. /api/fenix-input/sms/       — POST SMS webhook (od gateway-a ili mobitela)
3. /api/fenix-input/confirm/   — POST potvrdi AI parsiranu poruku
4. /api/fenix-input/history/   — GET povijest poruka
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from fenix_input.models import InputMessage, SMSDevice
from fenix_input.interpreter import interpret_message, parse_sms_by_pattern

logger = logging.getLogger('fenix_input')


@csrf_exempt
@require_POST
def voice_input(request):
    """
    Prima transkripciju od Web Speech API (browser).
    Šalje AI-ju za interpretaciju, vraća parsirane podatke.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    raw_text = (data.get('text') or '').strip()
    if not raw_text:
        return JsonResponse({'error': 'Nema teksta'}, status=400)

    # Dohvati kontekst
    user = request.user if request.user.is_authenticated else None
    company = None
    if user:
        from core.company_utils import get_user_company
        company = get_user_company(request)

    # Spremi raw poruku
    msg = InputMessage.objects.create(
        channel='voice',
        raw_text=raw_text,
        user=user,
        company=company,
        sender=f'browser:{request.META.get("HTTP_USER_AGENT", "")[:100]}',
        metadata={'lang': data.get('lang', 'hr-HR')},
    )

    # AI interpretacija
    parsed = interpret_message(raw_text, channel='voice', user=user, company=company)

    msg.ai_parsed = parsed
    msg.ai_confidence = parsed.get('confidence', 0)
    msg.target_module = parsed.get('target_module', '')
    msg.target_action = parsed.get('target_action', '')
    msg.status = 'parsed' if msg.ai_confidence >= 0.3 else 'error'
    msg.processed_at = timezone.now()
    msg.save(update_fields=[
        'ai_parsed', 'ai_confidence', 'target_module',
        'target_action', 'status', 'processed_at',
    ])

    return JsonResponse({
        'id': msg.pk,
        'status': msg.status,
        'parsed': parsed,
        'raw_text': raw_text,
    })


@csrf_exempt
@require_POST
def sms_webhook(request):
    """
    Prima SMS od gateway-a ili mobilne app-e.
    Format: {from: "+385...", body: "W:12.3kg T:21C", timestamp: "..."}

    Pero-ova vaga šalje SMS 3x dnevno → ovaj endpoint to prima,
    parsira i sprema kao InputMessage.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    sender = (data.get('from') or data.get('sender') or '').strip()
    body = (data.get('body') or data.get('text') or '').strip()

    if not body:
        return JsonResponse({'error': 'Nema sadržaja'}, status=400)

    # Pronađi registrirani uređaj
    device = None
    company = None
    if sender:
        device = SMSDevice.objects.filter(phone_number=sender, is_active=True).first()
        if device:
            company = device.company
            device.last_message_at = timezone.now()
            device.save(update_fields=['last_message_at'])

    msg = InputMessage.objects.create(
        channel='sms',
        raw_text=body,
        sender=sender,
        company=company,
        metadata={
            'device_id': str(device.pk) if device else None,
            'device_type': device.device_type if device else None,
            'timestamp': data.get('timestamp', ''),
        },
    )

    # Prvo pokušaj regex pattern uređaja (brzo, besplatno)
    parsed = None
    if device and device.parse_pattern:
        regex_result = parse_sms_by_pattern(body, device.parse_pattern)
        if regex_result:
            parsed = {
                'intent': 'sensor_reading',
                'target_module': device.target_module,
                'target_action': 'log_sensor_data',
                'fields': regex_result,
                'confidence': 0.95,
                'method': 'regex',
            }

    # Fallback na AI ako regex nije uspio
    if not parsed:
        parsed = interpret_message(body, channel='sms', company=company)

    msg.ai_parsed = parsed
    msg.ai_confidence = parsed.get('confidence', 0)
    msg.target_module = parsed.get('target_module', '')
    msg.target_action = parsed.get('target_action', '')
    msg.status = 'parsed' if msg.ai_confidence >= 0.5 else 'raw'
    msg.processed_at = timezone.now()
    msg.save(update_fields=[
        'ai_parsed', 'ai_confidence', 'target_module',
        'target_action', 'status', 'processed_at',
    ])

    logger.info(f'SMS from {sender}: {body[:50]}... → {msg.status}')

    return JsonResponse({
        'id': msg.pk,
        'status': msg.status,
        'parsed': parsed,
    })


@csrf_exempt
@require_POST
def confirm_message(request, message_id):
    """
    Korisnik potvrđuje AI-parsiranu poruku.
    Opcionalno može korigirati polja prije potvrde.
    """
    try:
        msg = InputMessage.objects.get(pk=message_id)
    except InputMessage.DoesNotExist:
        return JsonResponse({'error': 'Poruka ne postoji'}, status=404)

    if msg.status not in ('parsed', 'raw'):
        return JsonResponse({'error': f'Poruka već {msg.status}'}, status=400)

    try:
        corrections = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        corrections = {}

    # Primijeni korekcije
    if corrections.get('fields'):
        msg.ai_parsed['fields'] = {**msg.ai_parsed.get('fields', {}), **corrections['fields']}
    if corrections.get('target_module'):
        msg.target_module = corrections['target_module']
    if corrections.get('target_action'):
        msg.target_action = corrections['target_action']

    msg.status = 'confirmed'
    msg.confirmed_at = timezone.now()
    msg.save()

    # TODO: apply_to_module(msg) — spremi u ciljni modul
    # Ovo je faza 2 — za sad samo označavamo kao confirmed

    return JsonResponse({
        'id': msg.pk,
        'status': 'confirmed',
        'parsed': msg.ai_parsed,
    })


@login_required
@require_GET
def message_history(request):
    """Povijest ulaznih poruka za korisnika/firmu."""
    from core.company_utils import get_user_company
    company = get_user_company(request)

    qs = InputMessage.objects.filter(company=company).order_by('-created_at')[:50]
    messages_list = [{
        'id': m.pk,
        'channel': m.channel,
        'raw_text': m.raw_text[:100],
        'status': m.status,
        'target_module': m.target_module,
        'target_action': m.target_action,
        'confidence': m.ai_confidence,
        'created_at': m.created_at.isoformat(),
    } for m in qs]

    return JsonResponse({'messages': messages_list})


@require_GET
def bluetooth_config(request):
    """
    Vraća konfiguraciju za Web Bluetooth API.
    Frontend koristi ovo za spajanje na čip čitač.
    """
    return JsonResponse({
        'supported_devices': [
            {
                'name': 'ISO 11784/11785 RFID Reader',
                'service_uuid': '0000fff0-0000-1000-8000-00805f9b34fb',
                'characteristic_uuid': '0000fff1-0000-1000-8000-00805f9b34fb',
                'description': 'Standard mikročip čitač za životinje',
            },
            {
                'name': 'Gallagher HR5',
                'service_uuid': '6e400001-b5a3-f393-e0a9-e50e24dcca9e',
                'characteristic_uuid': '6e400003-b5a3-f393-e0a9-e50e24dcca9e',
                'description': 'Gallagher livestock RFID čitač',
            },
        ],
        'chip_format': {
            'type': 'numeric',
            'length': 15,
            'description': 'ISO 11784 — 15 znamenki',
        },
    })
