"""
accounts/trikey_views.py — TriKey autentifikacija views

Registracija: OIB → auto-fill → email → PIN setup → opcionalno Passkey + FINA
Login: PIN + Passkey (dual-key) ili PIN + BusinessKey
Sensitive: sva 3 ključa
Recovery: BusinessKey + email → reset PIN
"""

import json
import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .trikey import TriKeyProfile, oib_lookup, generate_pin

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# OIB AUTO-FILL API
# ════════════════════════════════════════════════════════════════

def api_oib_lookup(request):
    """AJAX: OIB unos → Sudski registar → auto-fill firma podaci."""
    oib = request.GET.get('oib', '').strip()
    if not oib:
        return JsonResponse({'error': 'OIB obavezan'}, status=400)

    result = oib_lookup(oib)
    if result:
        return JsonResponse({
            'found': True,
            'name': result.get('name', ''),
            'address': result.get('address', ''),
            'city': result.get('city', ''),
            'mbs': result.get('mbs', ''),
            'activities': result.get('activities', []),
            'source': result.get('source', ''),
        })
    else:
        # OIB valid ali firma nije u registru
        return JsonResponse({
            'found': False,
            'oib_valid': len(oib) == 11 and oib.isdigit(),
            'message': 'Firma nije pronađena u Sudskom registru. Unesite podatke ručno.',
        })


# ════════════════════════════════════════════════════════════════
# PIN LOGIN
# ════════════════════════════════════════════════════════════════

@ensure_csrf_cookie
def trikey_login(request):
    """Login s PIN-om (Ključ 1) + opcionalno Passkey (Ključ 2)."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        pin = request.POST.get('pin', '').strip()

        if not email or not pin:
            messages.error(request, 'Email i PIN su obavezni.')
            return render(request, 'accounts/trikey_login.html')

        # Find user by email
        from django.contrib.auth.models import User
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'Neispravan email ili PIN.')
            return render(request, 'accounts/trikey_login.html')

        # Get or create TriKey profile
        trikey, _ = TriKeyProfile.objects.get_or_create(user=user)

        # Verify PIN
        try:
            if trikey.verify_pin(pin):
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                trikey.calculate_auth_level({'pin'})
                logger.info(f'TriKey login: {email} via PIN')
                next_url = request.POST.get('next', request.GET.get('next', '/'))
                return redirect(next_url or 'dashboard')
            else:
                remaining = 5 - trikey.pin_attempts
                messages.error(request, f'Neispravan PIN. Preostalo pokušaja: {remaining}')
        except PermissionError as e:
            messages.error(request, str(e))

        return render(request, 'accounts/trikey_login.html', {'email': email})

    return render(request, 'accounts/trikey_login.html')


# ════════════════════════════════════════════════════════════════
# PIN SETUP
# ════════════════════════════════════════════════════════════════

@login_required
def pin_setup(request):
    """Postavi ili promijeni PIN."""
    trikey, _ = TriKeyProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        pin = request.POST.get('pin', '').strip()
        pin_confirm = request.POST.get('pin_confirm', '').strip()

        if pin != pin_confirm:
            messages.error(request, 'PIN-ovi se ne podudaraju.')
        elif len(pin) != 6 or not pin.isdigit():
            messages.error(request, 'PIN mora biti točno 6 znamenki.')
        else:
            try:
                trikey.set_pin(pin)
                messages.success(request, 'PIN uspješno postavljen! 🔑')
                return redirect('accounts:trikey_status')
            except ValueError as e:
                messages.error(request, str(e))

    suggested_pin = generate_pin()
    return render(request, 'accounts/pin_setup.html', {
        'trikey': trikey,
        'suggested_pin': suggested_pin,
    })


# ════════════════════════════════════════════════════════════════
# PASSKEY (WebAuthn) REGISTRATION
# ════════════════════════════════════════════════════════════════

@login_required
def passkey_register_options(request):
    """WebAuthn: Generate registration options (challenge)."""
    trikey, _ = TriKeyProfile.objects.get_or_create(user=request.user)

    # Generate challenge
    import secrets, base64
    challenge = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

    request.session['webauthn_challenge'] = challenge

    options = {
        'challenge': challenge,
        'rp': {
            'name': 'LIMIT Connect',
            'id': 'limit-connect.com',
        },
        'user': {
            'id': base64.urlsafe_b64encode(str(request.user.pk).encode()).decode(),
            'name': request.user.email or request.user.username,
            'displayName': request.user.get_full_name() or request.user.username,
        },
        'pubKeyCredParams': [
            {'alg': -7, 'type': 'public-key'},   # ES256
            {'alg': -257, 'type': 'public-key'},  # RS256
        ],
        'timeout': 60000,
        'authenticatorSelection': {
            'authenticatorAttachment': 'platform',
            'userVerification': 'preferred',
            'residentKey': 'preferred',
        },
        'attestation': 'none',
    }
    return JsonResponse(options)


@login_required
@require_POST
def passkey_register_complete(request):
    """WebAuthn: Complete registration — store credential."""
    trikey, _ = TriKeyProfile.objects.get_or_create(user=request.user)

    try:
        data = json.loads(request.body)
        credential_id = data.get('id', '')
        public_key = data.get('response', {}).get('publicKey', '')
        device_name = data.get('deviceName', request.META.get('HTTP_USER_AGENT', '')[:100])

        if not credential_id:
            return JsonResponse({'error': 'Missing credential ID'}, status=400)

        trikey.register_passkey(credential_id, json.dumps(public_key), device_name)
        logger.info(f'Passkey registered for {request.user.username}: {device_name}')

        return JsonResponse({'ok': True, 'message': 'Passkey registriran! 🔑'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ════════════════════════════════════════════════════════════════
# BUSINESS KEY REGISTRATION
# ════════════════════════════════════════════════════════════════

@login_required
@require_POST
def business_key_register(request):
    """Registriraj FINA cert i/ili ePosrednik API key."""
    trikey, _ = TriKeyProfile.objects.get_or_create(user=request.user)

    fina_cert = request.FILES.get('fina_cert')
    api_key = request.POST.get('eposrednik_api_key', '').strip()

    registered = []

    if fina_cert:
        try:
            cert_bytes = fina_cert.read()
            fingerprint = trikey.register_fina_cert(cert_bytes)
            registered.append(f'FINA cert (fingerprint: {fingerprint[:12]}...)')
        except Exception as e:
            messages.error(request, f'Greška s FINA certifikatom: {e}')

    if api_key:
        trikey.register_eposrednik_key(api_key)
        registered.append('ePosrednik API ključ')

    if registered:
        messages.success(request, f'Registrirano: {", ".join(registered)} 🔑')
    else:
        messages.warning(request, 'Niste unijeli niti certifikat niti API ključ.')

    return redirect('accounts:trikey_status')


# ════════════════════════════════════════════════════════════════
# TRIKEY STATUS DASHBOARD
# ════════════════════════════════════════════════════════════════

@login_required
def trikey_status(request):
    """Pregled stanja 3 ključa — koji su aktivni, koji nedostaju."""
    trikey, _ = TriKeyProfile.objects.get_or_create(user=request.user)

    return render(request, 'accounts/trikey_status.html', {
        'trikey': trikey,
        'keys': trikey.available_keys,
        'key_count': trikey.key_count,
        'is_fully_armed': trikey.is_fully_armed,
    })


# ════════════════════════════════════════════════════════════════
# PIN RECOVERY (BusinessKey + Email)
# ════════════════════════════════════════════════════════════════

@require_POST
def pin_recovery(request):
    """Resetiraj PIN koristeći Business Key + email verifikaciju."""
    email = request.POST.get('email', '').strip().lower()
    api_key = request.POST.get('eposrednik_api_key', '').strip()

    from django.contrib.auth.models import User
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        messages.error(request, 'Email nije pronađen.')
        return render(request, 'accounts/pin_recovery.html')

    trikey = TriKeyProfile.objects.filter(user=user).first()
    if not trikey:
        messages.error(request, 'TriKey profil ne postoji.')
        return render(request, 'accounts/pin_recovery.html')

    # Verify business key
    if not trikey.verify_business_key(api_key=api_key):
        messages.error(request, 'Neispravan Business Key.')
        return render(request, 'accounts/pin_recovery.html')

    # Generate new PIN and send via email
    new_pin = generate_pin()
    trikey.set_pin(new_pin)

    from django.core.mail import send_mail
    send_mail(
        subject='LIMIT Connect — Novi PIN',
        message=f'Vaš novi PIN: {new_pin}\n\nPromijenite ga nakon prve prijave.',
        from_email=None,
        recipient_list=[email],
        fail_silently=True,
    )

    messages.success(request, 'Novi PIN poslan na email. Provjerite inbox.')
    return redirect('accounts:trikey_login')
