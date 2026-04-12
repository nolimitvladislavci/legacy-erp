from core.models import BookingSignature
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
from django.utils.translation import gettext as _
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
            'oib_valid': __import__('core.oib_validator', fromlist=['validate_oib_hr']).validate_oib_hr(oib) if oib else False,
            'message': 'Firma nije pronađena u Sudskom registru. Unesite podatke ručno.',
        })


# ════════════════════════════════════════════════════════════════
# PIN LOGIN
# ════════════════════════════════════════════════════════════════

@ensure_csrf_cookie
def trikey_login(request):
    """Login s PIN-om (Ključ 1) + opcionalno Passkey (Ključ 2)."""
    if request.user.is_authenticated:
        # Ako ima workspace → tamo, inače arhiva
        from companies.models import Workspace
        if Workspace.get_for_user(request.user).exists():
            return redirect('companies:workspace_home')
        return redirect('documents:arhiva_list')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        pin = request.POST.get('pin', '').strip()

        if not email or not pin:
            messages.error(request, _('Email i PIN su obavezni.'))
            return render(request, 'accounts/trikey_login.html')

        # Find user by email
        from django.contrib.auth.models import User
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, _('Neispravan email ili PIN.'))
            return render(request, 'accounts/trikey_login.html')

        # Get or create TriKey profile
        trikey, _created = TriKeyProfile.objects.get_or_create(user=user)

        # Verify PIN
        try:
            if trikey.verify_pin(pin):
                login(request, user, backend='core.auth_backends.EmailOrUsernameBackend')
                trikey.calculate_auth_level({'pin'})
                logger.info(f'TriKey login: {email} via PIN')
                try:
                    BookingSignature.log(request, "login", target_model="User", target_id=str(user.pk), target_repr=f"PIN login: {user.username}", pin_verified=True)
                except Exception:
                    pass
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
    trikey, _created = TriKeyProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        pin = request.POST.get('pin', '').strip()
        pin_confirm = request.POST.get('pin_confirm', '').strip()

        if pin != pin_confirm:
            messages.error(request, _('PIN-ovi se ne podudaraju.'))
        elif len(pin) != 6 or not pin.isdigit():
            messages.error(request, _('PIN mora biti točno 6 znamenki.'))
        else:
            try:
                trikey.set_pin(pin)
                messages.success(request, _('PIN uspješno postavljen! 🔑'))
                return redirect('accounts:trikey_status')
            except ValueError as e:
                messages.error(request, str(e))

    suggested_pin = generate_pin()

    # Dohvati ljubimca za VAU widget
    pet_photo = None
    pet_name = 'tvoj ljubimac'
    try:
        from memio_pet.models import AnimalProfile
        animal = AnimalProfile.objects.using('memio_pets').filter(
            breeder__email=request.user.email
        ).order_by('-created_at').first()
        if animal and animal.photo:
            pet_photo = animal.photo.url
            pet_name = animal.name or 'tvoj ljubimac'
        elif animal:
            pet_name = animal.name or 'tvoj ljubimac'
    except Exception:
        pass

    return render(request, 'accounts/pin_setup.html', {
        'trikey': trikey,
        'suggested_pin': suggested_pin,
        'pet_photo': pet_photo,
        'pet_name': pet_name,
    })


# ════════════════════════════════════════════════════════════════
# PASSKEY (WebAuthn) REGISTRATION
# ════════════════════════════════════════════════════════════════

@login_required
def passkey_register_options(request):
    """WebAuthn: Generate registration options (challenge)."""
    trikey, _created = TriKeyProfile.objects.get_or_create(user=request.user)

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
    trikey, _created = TriKeyProfile.objects.get_or_create(user=request.user)

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
    trikey, _created = TriKeyProfile.objects.get_or_create(user=request.user)

    fina_cert = request.FILES.get('fina_cert')
    api_key = request.POST.get('eposrednik_api_key', '').strip()

    registered = []

    if fina_cert:
        try:
            cert_bytes = fina_cert.read()
            fingerprint = trikey.register_fina_cert(cert_bytes)
            registered.append(f'FINA cert (fingerprint: {fingerprint[:12]}...)')
        except Exception as e:
            messages.error(request, _('Problem s FINA certifikatom. Provjerite certifikat i pokušajte ponovo.'))

    if api_key:
        trikey.register_eposrednik_key(api_key)
        registered.append('ePosrednik API ključ')

    if registered:
        messages.success(request, f'Registrirano: {", ".join(registered)} 🔑')
    else:
        messages.warning(request, _('Niste unijeli niti certifikat niti API ključ.'))

    return redirect('accounts:trikey_status')


# ════════════════════════════════════════════════════════════════
# TRIKEY STATUS DASHBOARD
# ════════════════════════════════════════════════════════════════

@login_required
def trikey_status(request):
    """Pregled stanja 3 ključa — koji su aktivni, koji nedostaju."""
    trikey, _created = TriKeyProfile.objects.get_or_create(user=request.user)

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
        messages.error(request, _('Email nije pronađen.'))
        return render(request, 'accounts/pin_recovery.html')

    trikey = TriKeyProfile.objects.filter(user=user).first()
    if not trikey:
        messages.error(request, _('TriKey profil ne postoji.'))
        return render(request, 'accounts/pin_recovery.html')

    # Verify business key
    if not trikey.verify_business_key(api_key=api_key):
        messages.error(request, _('Neispravan Business Key.'))
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

    messages.success(request, _('Novi PIN poslan na email. Provjerite inbox.'))
    return redirect('accounts:trikey_login')


# ════════════════════════════════════════════════════════════════
# QUICK LOGIN — Odaberi ime + PIN (za prezentacije i brzi pristup)
# ════════════════════════════════════════════════════════════════

@ensure_csrf_cookie
def quick_login(request):
    """Brzi login: odaberi ime iz liste → unesu PIN → ulogirani."""
    if request.user.is_authenticated:
        # Ako ima workspace → tamo, inače arhiva
        from companies.models import Workspace
        if Workspace.get_for_user(request.user).exists():
            return redirect('companies:workspace_home')
        return redirect('documents:arhiva_list')

    # Dohvati firmu iz URL parametra ili default Konjik
    from companies.models import Company
    company_id = request.GET.get('company', '')
    if company_id:
        company = Company.objects.filter(pk=company_id).first()
    else:
        company = Company.objects.filter(name__icontains='konjik').first()

    users = []
    if company:
        from accounts.models import CompanyMembership
        memberships = CompanyMembership.objects.filter(
            company=company, is_active=True, user__is_active=True,
        ).select_related('user').order_by('user__first_name')
        for m in memberships:
            u = m.user
            name = u.get_full_name() or u.username
            if name.strip() and not u.is_superuser:
                users.append({'id': u.pk, 'name': name, 'email': u.email})

    if request.method == 'POST':
        import json
        user_id = request.POST.get('user_id', '')
        pin = request.POST.get('pin', '').strip()

        if not user_id or not pin:
            messages.error(request, _('Odaberite ime i unesite PIN.'))
            return render(request, 'accounts/quick_login.html', {
                'users': users, 'company': company,
            })

        from django.contrib.auth.models import User
        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, _('Korisnik nije pronađen.'))
            return render(request, 'accounts/quick_login.html', {
                'users': users, 'company': company,
            })

        trikey, _created = TriKeyProfile.objects.get_or_create(user=user)
        try:
            if trikey.verify_pin(pin):
                login(request, user, backend='core.auth_backends.EmailOrUsernameBackend')
                logger.info('Quick login: %s via PIN', user.username)
                return redirect('/hr/documents/arhiva/')
            else:
                remaining = 5 - trikey.pin_attempts
                messages.error(request, f'Neispravan PIN. Preostalo: {remaining}')
        except PermissionError as e:
            messages.error(request, str(e))

        return render(request, 'accounts/quick_login.html', {
            'users': users, 'company': company, 'selected_id': int(user_id),
        })

    return render(request, 'accounts/quick_login.html', {
        'users': users, 'company': company,
    })
