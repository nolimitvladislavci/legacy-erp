import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from .models import WaitlistEntry

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def waitlist_signup(request):
    """memio.world waitlist API — prima JSON {name, email, interest}."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    email = (data.get('email') or '').strip().lower()
    name = (data.get('name') or '').strip()
    interest = (data.get('interest') or 'general').strip()

    if not email or '@' not in email:
        return JsonResponse({'error': 'Email obavezan'}, status=400)

    entry, created = WaitlistEntry.objects.using('memio_world').get_or_create(
        email=email,
        defaults={
            'name': name,
            'interest': interest,
            'source': 'memio.world',
            'ip': request.META.get('HTTP_X_REAL_IP', request.META.get('REMOTE_ADDR')),
        },
    )

    if created:
        logger.info(f'memio.world waitlist: {email} ({interest})')
        return JsonResponse({'ok': True, 'message': 'Uspješno prijavljeni!'}, status=201)
    else:
        return JsonResponse({'ok': True, 'message': 'Već ste prijavljeni.'}, status=200)


@require_GET
def waitlist_count(request):
    """Javni endpoint — koliko ljudi čeka na memio.world."""
    count = WaitlistEntry.objects.using('memio_world').count()
    return JsonResponse({'count': count})
