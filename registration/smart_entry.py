"""
registration/smart_entry.py
Jedina ulazna točka — /pocni/
Email detect → pravi flow, nema dead enda.
"""
import json

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, dumps, loads
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST


def pocni(request):
    """
    GET  → prikazuje stranicu s email poljem
    Parametri: ?ref=REF-MARIJA-2026, ?pet=Vučko, ?plan=professional
    """
    if request.user.is_authenticated:
        return redirect('/hr/portal/' if hasattr(request, 'white_label') and request.white_label else '/hr/dashboard/')

    ref = request.GET.get('ref', '')
    if ref:
        request.session['agent_ref'] = ref

    return render(request, 'registration/smart_entry.html', {
        'pet': request.GET.get('pet', ''),
        'plan': request.GET.get('plan', ''),
        'ref': ref,
        'page_title': 'Počnite s LIMIT Connect',
    })


@require_POST
def api_detect_email(request):
    """
    POST /pocni/provjeri/
    Body: {"email": "ivan@firma.hr"}
    Returns: {"status": "new|existing|rate_limit", ...}
    """
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
    except Exception:
        return JsonResponse({'status': 'error', 'msg': 'Neispravan zahtjev'}, status=400)

    if not email or '@' not in email:
        return JsonResponse({'status': 'error', 'msg': 'Unesite valjanu email adresu'})

    # Rate limit: 10 pokušaja / 10 min po IP
    rate_key = f'smart_entry_rate:{request.META.get("REMOTE_ADDR", "")}'
    attempts = cache.get(rate_key, 0)
    if attempts > 10:
        return JsonResponse({
            'status': 'rate_limit',
            'msg': 'Previše pokušaja. Pričekajte 10 minuta.',
            'wait_seconds': 600,
        })
    cache.set(rate_key, attempts + 1, timeout=600)

    user = User.objects.filter(email=email).first()
    if user:
        _send_magic_link(user, request)
        return JsonResponse({
            'status': 'existing',
            'msg': f'Poslali smo vam link na {email}. Provjerite inbox (i spam).',
        })

    ref = request.session.get('agent_ref', '')
    return JsonResponse({
        'status': 'new',
        'msg': 'Dobrodošli! Kreiramo vaš račun.',
        'redirect': f'/hr/register/?email={email}&ref={ref}',
    })


def _send_magic_link(user, request):
    token = dumps({'user_id': user.pk}, key=settings.SECRET_KEY, salt='magic-login')
    link = request.build_absolute_uri(f'/pocni/magic/{token}/')
    send_mail(
        subject='Vaš pristup — LIMIT Connect',
        message=f'Kliknite link za ulaz u portal:\n{link}\n\nLink je valjan 24 sata.',
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@limit-connect.com'),
        recipient_list=[user.email],
        fail_silently=True,
    )


def magic_login(request, token):
    """One-click login via signed token (24h TTL)."""
    try:
        data = loads(token, key=settings.SECRET_KEY, salt='magic-login', max_age=86400)
        user = User.objects.get(pk=data['user_id'])
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('/hr/dashboard/')
    except (BadSignature, SignatureExpired, User.DoesNotExist):
        return render(request, 'registration/smart_entry.html', {
            'error': 'Link je istekao ili neispravan. Unesite email ponovo.',
        })
