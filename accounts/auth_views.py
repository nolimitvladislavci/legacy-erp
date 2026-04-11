"""
LIMIT CONNECT Auth Views
- Smart login (prepoznaj rolu → pravi dashboard)
- Magic link (passwordless za investitore/partnere/radnike)
- 2FA (TOTP za admins/superadmin)
- Google/Microsoft SSO
- Forgot password
- Rate limiting
"""
import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from core.email_tasks import send_email_task

from .auth_models import LoginAttempt, MagicToken

logger = logging.getLogger(__name__)


def _check_concurrent_login(user, current_ip, current_ua):
    """
    Detektira concurrent session — isti user, različit IP u zadnjih 30 min.
    Šalje WhatsApp/push alert korisniku: "Netko se prijavio s vašim računom."
    """
    from datetime import timedelta
    from django.utils import timezone

    since = timezone.now() - timedelta(minutes=30)
    recent_logins = LoginAttempt.objects.filter(
        email__in=[user.email, user.username],
        success=True,
        attempted_at__gte=since,
    ).exclude(ip_address=current_ip).values_list('ip_address', flat=True).distinct()

    if not recent_logins:
        return  # Nema concurrent sessiona

    other_ips = list(recent_logins)
    logger.warning(
        '[SECURITY] Concurrent login: user=%s current_ip=%s other_ips=%s',
        user.username, current_ip, other_ips
    )

    # Alert korisniku
    alert_msg = (
        'SIGURNOSNO UPOZORENJE: Netko se upravo prijavio na vaš LIMIT Connect račun '
        's nove lokacije (IP: %s).\n'
        'Ako to niste bili vi, odmah promijenite lozinku!\n'
        'https://limit-connect.com/hr/accounts/change-password/'
    ) % current_ip

    # WhatsApp alert
    try:
        phone = ''
        profile = getattr(user, 'profile', None)
        if profile and profile.phone:
            from core.whatsapp import normalize_phone
            phone = normalize_phone(profile.phone)
        if phone and getattr(settings, 'WAHA_ENABLED', False):
            from core.whatsapp_tasks import send_whatsapp_text_task
            send_whatsapp_text_task.delay(phone, alert_msg)
    except Exception:
        pass

    # Push notification
    try:
        from push_notifications.push import send_push_to_user
        send_push_to_user(user, 'Prijava s nove lokacije!', alert_msg[:100])
    except Exception:
        pass

    # In-app notification
    try:
        from notifications.services import notify
        notify(
            recipient=user, notification_type='system',
            title='Prijava s nove lokacije',
            message='IP: %s | Ako to niste vi, odmah promijenite lozinku.' % current_ip,
            url='/accounts/change-password/',
        )
    except Exception:
        pass

    # Audit log
    try:
        from core.models import SystemAuditLog
        SystemAuditLog.objects.create(
            user=user,
            action='concurrent_login',
            model_name='auth.User',
            object_id=str(user.pk),
            object_repr='Concurrent login: %s + %s' % (current_ip, ', '.join(other_ips)),
            changes={'current_ip': current_ip, 'other_ips': other_ips, 'user_agent': current_ua},
            ip_address=current_ip,
        )
    except Exception:
        pass


def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')


def get_dashboard_url(user):
    """Smart redirect - vrati URL dashboarda prema roli"""
    try:
        profile = user.userprofile
        role = profile.role
        urls = {
            'superadmin':     '/superadmin/',
            'company_admin':  '/hr/pos/',
            'project_manager':'/dashboard/manager/',
            'worker':         '/dashboard/worker/',
            'investor':       '/dashboard/investor/',
            'partner':        '/dashboard/partner/',
        }
        return urls.get(role, '/dashboard/')
    except Exception:
        if user.is_superuser:
            return '/superadmin/'
        return '/dashboard/'


# ── SMART LOGIN PAGE
def smart_login(request):
    """Jedna login stranica za sve role"""
    if request.user.is_authenticated:
        return redirect(get_dashboard_url(request.user))

    if request.method == 'POST':
        email_or_user = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        ip = get_client_ip(request)

        # Rate limiting
        if LoginAttempt.is_blocked(ip, email_or_user):
            messages.error(request, _('Previše neuspješnih pokušaja. Pričekajte 15 minuta.'))
            return render(request, 'accounts/login.html', {'blocked': True})

        # Pronađi korisnika po emailu ili usernameu
        user = None
        try:
            u = User.objects.get(email__iexact=email_or_user)
            user = authenticate(request, username=u.username, password=password)
        except User.DoesNotExist:
            user = authenticate(request, username=email_or_user, password=password)

        if user and user.is_active:
            ua = request.META.get('HTTP_USER_AGENT', '')[:255]

            # Log uspješan
            LoginAttempt.objects.create(
                email=email_or_user, ip_address=ip, success=True,
                method='password', user_agent=ua,
            )

            # Concurrent session detection — alert ako je user već prijavljen s drugog IP-a
            _check_concurrent_login(user, ip, ua)

            # Provjeri 2FA za admins
            try:
                profile = user.userprofile
                if profile.role in ('superadmin', 'company_admin') and profile.totp_enabled:
                    # Spremi user_id u session, preusmjeri na 2FA
                    request.session['pending_2fa_user'] = user.pk
                    request.session['pending_2fa_next'] = get_dashboard_url(user)
                    return redirect('verify_2fa')
            except Exception:
                pass

            login(request, user)
            messages.success(request, _(f'Dobrodošli, {user.first_name or user.username}!'))
            return redirect(get_dashboard_url(user))
        else:
            LoginAttempt.objects.create(
                email=email_or_user, ip_address=ip, success=False,
                method='password', user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
            )
            messages.error(request, _('Pogrešni podaci za prijavu.'))

    return render(request, 'accounts/login.html', {
        'google_enabled': hasattr(settings, 'GOOGLE_CLIENT_ID'),
        'microsoft_enabled': hasattr(settings, 'MICROSOFT_CLIENT_ID'),
    })


# ── MAGIC LINK - SLANJE
def send_magic_link(request):
    """Pošalji magic link na email"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        token_type = request.POST.get('type', 'partner')
        ip = get_client_ip(request)

        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            # Ne otkrivaj postoji li email
            messages.success(request, _('Ako email postoji, link je poslan.'))
            return redirect('login')

        # Rate limiting za magic linkove
        if LoginAttempt.is_blocked(ip, email, max_attempts=3, minutes=10):
            messages.error(request, _('Previše zahtjeva. Pričekajte 10 minuta.'))
            return redirect('login')

        try:
            profile = user.userprofile
            token_type = {
                'investor': 'investor',
                'partner':  'partner',
                'worker':   'worker',
            }.get(profile.role, 'partner')
        except Exception:
            pass

        # Kreiraj token (24h valjanost)
        magic = MagicToken.create_for_user(user, token_type=token_type, hours=24)

        # Generiraj link
        base_url = request.build_absolute_uri('/')[:-1]
        magic_url = f"{base_url}/auth/magic/{magic.token}/"

        # Email predlošci po tipu
        type_labels = {
            'investor': 'pristup projektima',
            'partner':  'pristup fakturama',
            'worker':   'upload slika s terena',
        }
        label = type_labels.get(token_type, 'pristup sustavu')

        subject = f"LIMIT CONNECT – Vaš link za {label}"
        body = f"""Poštovani {user.first_name or user.username},

Zatražili ste link za {label}.

Kliknite ovdje za pristup (valjanost 24 sata):
{magic_url}

Ako niste zatražili ovaj link, ignorirajte ovu poruku.

LIMIT CONNECT | Visković Group
"""
        try:
            send_email_task.delay(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
            logger.info(f"Magic link poslan: {user.email} ({token_type})")
        except Exception as e:
            logger.error(f"Email greška: {e}")

        LoginAttempt.objects.create(
            email=email, ip_address=ip, success=True, method='magic'
        )
        messages.success(request, _(f'Link za pristup poslan na {email}. Vrijedi 24 sata.'))
        return redirect('login')

    return redirect('login')


# ── MAGIC LINK - PROVJERA I LOGIN
def verify_magic_link(request, token):
    """Provjeri magic token i ulogiraj korisnika"""
    ip = get_client_ip(request)

    try:
        magic = MagicToken.objects.select_related('user').get(token=token)
    except MagicToken.DoesNotExist:
        messages.error(request, _('Link nije valjan ili je istekao.'))
        return redirect('login')

    if not magic.is_valid:
        messages.error(request, _('Link je istekao ili je već iskorišten. Zatražite novi.'))
        return redirect('login')

    # Iskoristi token
    magic.mark_used(ip=ip)

    user = magic.user
    if not user.is_active:
        messages.error(request, _('Korisnički račun nije aktivan.'))
        return redirect('login')

    # Login bez lozinke
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)

    LoginAttempt.objects.create(
        email=user.email, ip_address=ip, success=True, method='magic'
    )

    messages.success(request, _(f'Dobrodošli, {user.first_name or user.username}!'))

    # Redirect prema tipu tokena
    type_urls = {
        'investor': '/dashboard/investor/',
        'partner':  '/dashboard/partner/',
        'worker':   '/dashboard/worker/',
        'reset':    '/auth/password-reset-confirm/',
    }
    next_url = type_urls.get(magic.token_type, get_dashboard_url(user))

    # Ako ima context (specifičan projekt ili faktura)
    if magic.context.get('project_id'):
        next_url = f"/projects/{magic.context['project_id']}/"
    elif magic.context.get('invoice_id'):
        next_url = f"/invoicing/{magic.context['invoice_id']}/pdf/"

    return redirect(next_url)


# ── 2FA SETUP (TOTP)
@login_required
def setup_2fa(request):
    """Setup Google Authenticator / TOTP"""
    import base64
    import io

    import pyotp
    import qrcode

    try:
        profile = request.user.userprofile
    except Exception:
        messages.error(request, 'Nema profila')
        return redirect('/')

    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        secret = request.session.get('totp_secret')
        if secret:
            totp = pyotp.TOTP(secret)
            if totp.verify(code):
                profile.totp_secret = secret
                profile.totp_enabled = True
                profile.save()
                del request.session['totp_secret']
                messages.success(request, _('✓ 2FA aktiviran! Koristite Google Authenticator za prijavu.'))
                return redirect(get_dashboard_url(request.user))
            else:
                _ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '')
                LoginAttempt.objects.create(email=f'2fa_setup_{request.user.pk}', ip_address=_ip, success=False, method='2fa')
                messages.error(request, _('Pogrešan kod. Pokušajte ponovo.'))

    # Generiraj novi secret
    import pyotp
    secret = pyotp.random_base32()
    request.session['totp_secret'] = secret

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(
        name=request.user.email,
        issuer_name='LIMIT CONNECT'
    )

    # QR kod
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return render(request, 'accounts/setup_2fa.html', {
        'secret': secret,
        'qr_code': qr_b64,
    })


# ── 2FA VERIFY
def verify_2fa(request):
    """Provjera 2FA koda pri prijavi — rate limited (5/10min)"""
    user_id = request.session.get('pending_2fa_user')
    if not user_id:
        return redirect('login')

    if request.method == 'POST':
        import pyotp
        code = request.POST.get('code', '').replace(' ', '')

        # Rate limit: max 5 pokušaja u 10 min (sprečava brute-force 6-digit koda)
        ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '')
        attempt_key = f'2fa_{user_id}'
        if LoginAttempt.is_blocked(ip, attempt_key, max_attempts=5, minutes=10):
            messages.error(request, _('Previše neuspješnih pokušaja. Pričekajte 10 minuta.'))
            return render(request, 'accounts/verify_2fa.html')
        try:
            user = User.objects.get(pk=user_id)
            profile = user.userprofile
            totp = pyotp.TOTP(profile.totp_secret)
            if totp.verify(code):
                LoginAttempt.objects.create(email=attempt_key, ip_address=ip, success=True, method='2fa')
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                del request.session['pending_2fa_user']
                next_url = request.session.pop('pending_2fa_next', get_dashboard_url(user))
                messages.success(request, _('✓ Uspješna 2FA provjera!'))
                return redirect(next_url)
            else:
                LoginAttempt.objects.create(email=attempt_key, ip_address=ip, success=False, method='2fa')
                messages.error(request, _('Pogrešan kod. Pokušajte ponovo.'))
        except Exception as e:
            messages.error(request, _('Greška provjere.'))
            return redirect('login')

    return render(request, 'accounts/verify_2fa.html')


# ── FORGOT PASSWORD
def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(email__iexact=email, is_active=True)
            magic = MagicToken.create_for_user(user, token_type='reset', hours=2)
            base_url = request.build_absolute_uri('/')[:-1]
            reset_url = f"{base_url}/auth/magic/{magic.token}/"
            send_email_task.delay(
                'LIMIT CONNECT – Reset lozinke',
                f"Kliknite za reset lozinke (vrijedi 2 sata):\n{reset_url}\n\nAko niste zatražili reset, ignorirajte ovu poruku.",
                settings.DEFAULT_FROM_EMAIL,
                [user.email]
            )
        except User.DoesNotExist:
            pass
        messages.success(request, _('Ako email postoji, link za reset je poslan.'))
        return redirect('login')
    return render(request, 'accounts/forgot_password.html')


# ── PASSWORD RESET CONFIRM
@login_required
def password_reset_confirm(request):
    if request.method == 'POST':
        p1 = request.POST.get('password1', '')
        p2 = request.POST.get('password2', '')
        if p1 != p2:
            messages.error(request, _('Lozinke se ne podudaraju.'))
        elif len(p1) < 10:
            messages.error(request, _('Lozinka mora imati najmanje 10 znakova.'))
        else:
            request.user.set_password(p1)
            request.user.save()
            messages.success(request, _('✓ Lozinka promijenjena! Prijavite se s novom lozinkom.'))
            logout(request)
            return redirect('login')
    return render(request, 'accounts/password_reset_confirm.html')


# ── GOOGLE SSO (OAuth2)
def google_login(request):
    """Inicira Google OAuth2 flow"""
    if not hasattr(settings, 'GOOGLE_CLIENT_ID'):
        messages.error(request, _('Google login nije konfiguriran.'))
        return redirect('login')

    state = secrets.token_urlsafe(16)
    request.session['oauth_state'] = state
    redirect_uri = request.build_absolute_uri('/auth/google/callback/')

    google_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=openid email profile"
        f"&state={state}"
        f"&prompt=select_account"
    )
    return redirect(google_url)


def google_callback(request):
    """Google OAuth2 callback"""
    import requests as req

    code = request.GET.get('code')
    state = request.GET.get('state')

    if state != request.session.get('oauth_state'):
        messages.error(request, _('OAuth state mismatch.'))
        return redirect('login')

    redirect_uri = request.build_absolute_uri('/auth/google/callback/')

    try:
        # Zamijeni code za token
        token_response = req.post('https://oauth2.googleapis.com/token', data={
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'code': code,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        })
        tokens = token_response.json()

        # Dohvati user info
        user_info = req.get('https://www.googleapis.com/oauth2/v3/userinfo',
                            headers={'Authorization': f"Bearer {tokens['access_token']}"}).json()

        email = user_info.get('email', '')
        name_parts = user_info.get('name', '').split(' ', 1)

        # Pronađi ili kreiraj usera
        user, created = User.objects.get_or_create(
            email__iexact=email,
            defaults={
                'username': email.split('@')[0],
                'email': email,
                'first_name': name_parts[0] if name_parts else '',
                'last_name': name_parts[1] if len(name_parts) > 1 else '',
            }
        )

        if not user.is_active:
            messages.error(request, _('Korisnički račun nije aktivan.'))
            return redirect('login')

        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        LoginAttempt.objects.create(email=email, ip_address=get_client_ip(request), success=True, method='google')
        messages.success(request, _(f'Prijavljeni ste putem Google: {email}'))
        return redirect(get_dashboard_url(user))

    except Exception as e:
        logger.error(f"Google OAuth greška: {e}")
        messages.error(request, _('Greška Google prijave. Pokušajte ponovo.'))
        return redirect('login')


# ── MICROSOFT SSO (OAuth2)
def microsoft_login(request):
    if not hasattr(settings, 'MICROSOFT_CLIENT_ID'):
        messages.error(request, _('Microsoft login nije konfiguriran.'))
        return redirect('login')

    state = secrets.token_urlsafe(16)
    request.session['ms_oauth_state'] = state
    redirect_uri = request.build_absolute_uri('/auth/microsoft/callback/')
    tenant = getattr(settings, 'MICROSOFT_TENANT_ID', 'common')

    ms_url = (
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
        f"?client_id={settings.MICROSOFT_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=openid email profile"
        f"&state={state}"
        f"&prompt=select_account"
    )
    return redirect(ms_url)


def microsoft_callback(request):
    import requests as req

    code = request.GET.get('code')
    state = request.GET.get('state')
    tenant = getattr(settings, 'MICROSOFT_TENANT_ID', 'common')

    if state != request.session.get('ms_oauth_state'):
        messages.error(request, _('OAuth state mismatch.'))
        return redirect('login')

    redirect_uri = request.build_absolute_uri('/auth/microsoft/callback/')

    try:
        token_response = req.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                'client_id': settings.MICROSOFT_CLIENT_ID,
                'client_secret': settings.MICROSOFT_CLIENT_SECRET,
                'code': code,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            }
        )
        tokens = token_response.json()
        user_info = req.get(
            'https://graph.microsoft.com/v1.0/me',
            headers={'Authorization': f"Bearer {tokens['access_token']}"}
        ).json()

        email = user_info.get('mail') or user_info.get('userPrincipalName', '')
        given = user_info.get('givenName', '')
        sur = user_info.get('surname', '')

        user, created = User.objects.get_or_create(
            email__iexact=email,
            defaults={'username': email.split('@')[0], 'email': email, 'first_name': given, 'last_name': sur}
        )

        if not user.is_active:
            messages.error(request, _('Korisnički račun nije aktivan.'))
            return redirect('login')

        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        LoginAttempt.objects.create(email=email, ip_address=get_client_ip(request), success=True, method='microsoft')
        messages.success(request, _(f'Prijavljeni ste putem Microsoft: {email}'))
        return redirect(get_dashboard_url(user))

    except Exception as e:
        logger.error(f"Microsoft OAuth greška: {e}")
        messages.error(request, _('Greška Microsoft prijave.'))
        return redirect('login')


# ── API ZA MAGIC LINK SLANJE (iz ERP-a / viskovic-group.de)
@login_required
def api_send_magic_link(request):
    """Admin šalje magic link korisniku"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    user_id = request.POST.get('user_id')
    token_type = request.POST.get('type', 'partner')
    context = {}

    if request.POST.get('project_id'):
        context['project_id'] = request.POST.get('project_id')
    if request.POST.get('invoice_id'):
        context['invoice_id'] = request.POST.get('invoice_id')

    try:
        user = User.objects.get(pk=user_id)
        magic = MagicToken.create_for_user(user, token_type=token_type, hours=48, context=context)
        base_url = request.build_absolute_uri('/')[:-1]
        magic_url = f"{base_url}/auth/magic/{magic.token}/"

        send_email_task.delay(
            'LIMIT CONNECT – Pozivnica za pristup',
            f"Poštovani {user.first_name or user.username},\n\nPozivnica za pristup:\n{magic_url}\n\nVrijedi 48 sati.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        )
        return JsonResponse({'success': True, 'url': magic_url})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── LOGOUT
def smart_logout(request):
    """
    Pametni logout — provjerava otvorene bonove prije odjave.
    B-02: Upozorenje pri odjavi s otvorenim bonovima.
    """
    if request.user.is_authenticated:
        try:
            from core.company_utils import get_user_company
            company = get_user_company(request)

            # B-02: Provjeri otvorene bonove
            if company:
                from pos.models import POSReceipt
                open_receipts = POSReceipt.objects.filter(
                    session__terminal__company=company,
                    status='open',
                    cashier__user=request.user,
                ).select_related('session')

                if open_receipts.exists() and request.method == 'GET':
                    # GET = prvi klik na logout → prikaži upozorenje
                    count = open_receipts.count()
                    receipt_list = list(open_receipts.values_list('receipt_number', flat=True)[:5])
                    messages.warning(
                        request,
                        'Imate %d otvorenih bonova (#%s). '
                        'Kliknite PONOVO za potvrdu odjave — otvoreni bonovi će biti stornirani.'
                        % (count, ', '.join(str(r) for r in receipt_list))
                    )
                    return redirect(request.META.get('HTTP_REFERER', '/'))

                # POST = potvrđeni logout → zatvori otvorene bonove
                if open_receipts.exists():
                    cancelled = 0
                    for receipt in open_receipts:
                        receipt.status = 'cancelled'
                        receipt.cancel_reason = 'Auto-cancel pri odjavi korisnika'
                        receipt.save(update_fields=['status', 'cancel_reason'])
                        cancelled += 1
                    if cancelled:
                        messages.info(request, '%d otvorenih bonova automatski stornirano.' % cancelled)

            # Zatvori radno vrijeme + waiter shift + cashier
            if company:
                from pos.worktime_bridge import device_logout_stop_all
                device_logout_stop_all(request.user, company)
        except Exception:
            pass
    logout(request)
    return redirect('login')


# ═══════════════════════════════════════════════════════════════
# DEVICE TOKEN — Mobilni barcode login (mobitel = čip kartica)
# ═══════════════════════════════════════════════════════════════

@login_required
def device_token_manage(request):
    """Upravljanje device tokenima — generiraj, pregledaj, deaktiviraj."""
    from accounts.models import DeviceToken
    from core.company_utils import get_user_company

    company = get_user_company(request)
    tokens = DeviceToken.objects.filter(user=request.user, company=company)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'create':
            device_name = request.POST.get('device_name', 'Moj uređaj')
            cashier_id = request.POST.get('cashier_id')
            from pos.models import POSCashier
            cashier = None
            if cashier_id:
                cashier = POSCashier.objects.filter(pk=cashier_id, company=company).first()
            token = DeviceToken.objects.create(
                user=request.user,
                company=company,
                device_name=device_name,
                cashier=cashier,
                auto_pos_login=True,
            )
            messages.success(request, 'Device token "%s" kreiran. Spremi barcode u mobitel.' % token.device_name)
            return redirect('device_token_detail', token_id=token.pk)

        elif action == 'deactivate':
            token_id = request.POST.get('token_id')
            try:
                token = tokens.get(pk=token_id)
                token.is_active = False
                token.save()
                messages.success(request, 'Token "%s" deaktiviran.' % token.device_name)
            except DeviceToken.DoesNotExist:
                messages.error(request, 'Token ne postoji.')

        elif action == 'activate':
            token_id = request.POST.get('token_id')
            try:
                token = tokens.get(pk=token_id)
                token.is_active = True
                token.save()
                messages.success(request, 'Token "%s" aktiviran.' % token.device_name)
            except DeviceToken.DoesNotExist:
                pass

        return redirect('device_token_manage')

    from pos.models import POSCashier
    cashiers = POSCashier.objects.filter(company=company, is_active=True)
    return render(request, 'accounts/device_token_manage.html', {
        'tokens': tokens,
        'cashiers': cashiers,
    })


@login_required
def device_token_detail(request, token_id):
    """Prikaz barkoda za spremanje u mobitel."""
    from accounts.models import DeviceToken
    token = DeviceToken.objects.filter(pk=token_id, user=request.user).first()
    if not token:
        messages.error(request, 'Token ne postoji.')
        return redirect('device_token_manage')

    # Generiraj barcode sliku (Code128 + QR)
    import io, base64
    try:
        import barcode
        from barcode.writer import ImageWriter
        code128 = barcode.get('code128', token.barcode_data, writer=ImageWriter())
        buf = io.BytesIO()
        code128.write(buf, options={'write_text': True, 'module_height': 15, 'font_size': 10})
        buf.seek(0)
        barcode_b64 = base64.b64encode(buf.read()).decode()
    except Exception:
        barcode_b64 = ''

    try:
        import qrcode
        qr = qrcode.make(token.barcode_data, box_size=8, border=2)
        buf = io.BytesIO()
        qr.save(buf, format='PNG')
        buf.seek(0)
        qr_b64 = base64.b64encode(buf.read()).decode()
    except Exception:
        qr_b64 = ''

    return render(request, 'accounts/device_token_detail.html', {
        'token': token,
        'barcode_b64': barcode_b64,
        'qr_b64': qr_b64,
    })


from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST as _require_POST


@csrf_exempt
@_require_POST
def device_token_login(request):
    """
    AJAX endpoint: POS terminal skenira barcode → auto-login.
    POST {barcode_data: "LC-DEV-XXXXXXXX"} ili {token: "uuid"}
    Returns {ok, redirect_url} ili {ok: false, error}
    """
    import json
    from accounts.models import DeviceToken
    from django.utils import timezone

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST.dict()

    barcode_data = data.get('barcode_data', '').strip()
    token_uuid = data.get('token', '').strip()

    if not barcode_data and not token_uuid:
        return JsonResponse({'ok': False, 'error': 'Barcode ili token obavezan.'}, status=400)

    # Lookup token
    dt = None
    if barcode_data:
        dt = DeviceToken.objects.filter(barcode_data=barcode_data, is_active=True).select_related('user', 'company', 'cashier').first()
    elif token_uuid:
        dt = DeviceToken.objects.filter(token=token_uuid, is_active=True).select_related('user', 'company', 'cashier').first()

    if not dt:
        return JsonResponse({'ok': False, 'error': 'Nepoznat ili deaktiviran token.'}, status=403)

    # B-20: Provjeri expiry
    if dt.is_expired:
        dt.is_active = False
        dt.save(update_fields=['is_active'])
        return JsonResponse({'ok': False, 'error': 'Token je istekao. Zatražite novi od admina.'}, status=403)

    # Login korisnika
    dt.user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, dt.user)

    # Update last used
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    dt.last_used_at = timezone.now()
    dt.last_ip = ip
    dt.save(update_fields=['last_used_at', 'last_ip'])

    # Set company context
    request.session['impersonated_company_id'] = str(dt.company.pk) if hasattr(dt.company.pk, 'hex') else dt.company.pk

    # UNIFIED START — radno vrijeme + waiter shift + cashier (jedan scan = sve)
    from pos.worktime_bridge import device_login_start_all
    work_result = device_login_start_all(dt, ip_address=ip)

    # Redirect to POS
    redirect_url = '/pos/'
    if dt.cashier or work_result.get('cashier_id'):
        from pos.models import POSTerminal
        terminal = POSTerminal.objects.filter(company=dt.company, is_active=True).first()
        if terminal:
            redirect_url = '/pos/quick/%d/' % terminal.pk

    return JsonResponse({
        'ok': True,
        'user': dt.user.get_full_name() or dt.user.username,
        'company': dt.company.name,
        'cashier_id': dt.cashier.pk if dt.cashier else None,
        'cashier_name': dt.cashier.name if dt.cashier else None,
        'redirect_url': redirect_url,
        'token': str(dt.token),
    })


def device_token_auto_login(request):
    """
    GET endpoint: mobitel otvori ovaj link s token parametrom → auto-login → POS.
    Koristi se kad POS radi na istom mobitelu.
    URL: /auth/device-login/?token=uuid
    """
    import json
    from accounts.models import DeviceToken
    from django.utils import timezone

    token_uuid = request.GET.get('token', '')
    if not token_uuid:
        return redirect('login')

    dt = DeviceToken.objects.filter(token=token_uuid, is_active=True).select_related('user', 'company').first()
    if not dt:
        messages.error(request, 'Token nije valjan ili je deaktiviran.')
        return redirect('login')

    # Login
    dt.user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, dt.user)

    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    dt.last_used_at = timezone.now()
    dt.last_ip = ip
    dt.save(update_fields=['last_used_at', 'last_ip'])

    request.session['impersonated_company_id'] = str(dt.company.pk) if hasattr(dt.company.pk, 'hex') else dt.company.pk

    # UNIFIED START — radno vrijeme + waiter shift + cashier
    from pos.worktime_bridge import device_login_start_all
    work_result = device_login_start_all(dt, ip_address=ip)
    started = work_result.get('started', [])

    parts = ['Prijava uspješna — %s' % dt.device_name]
    if 'radno_vrijeme' in started:
        parts.append('Radno vrijeme pokrenuto.')
    if 'waiter_shift' in started:
        parts.append('Konobarova smjena aktivna.')
    if 'cashier' in started:
        parts.append('Blagajnik: %s' % work_result.get('cashier_name', ''))
    messages.success(request, ' '.join(parts))

    from pos.models import POSTerminal
    terminal = POSTerminal.objects.filter(company=dt.company, is_active=True).first()
    if terminal:
        return redirect('pos:quick_pos', terminal_id=terminal.pk)
    return redirect('pos:dashboard')


@login_required
def device_token_qr_image(request, token_id):
    """Serve QR code as PNG image for inline display."""
    from accounts.models import DeviceToken
    import io
    token = DeviceToken.objects.filter(pk=token_id, user=request.user).first()
    if not token:
        return HttpResponse(status=404)
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(token.barcode_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='#c9a84c', back_color='#0a0a0a')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return HttpResponse(buf.getvalue(), content_type='image/png')
    except Exception:
        return HttpResponse(status=500)


# ══════════════════════════════════════════════════════════════════════════════
# GDPR Data Portability — Članak 20 (Sudo Mode)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def gdpr_export_view(request):
    """
    GDPR export osobnih podataka — Sudo Mode.
    GET: prikaži formu za potvrdu lozinke
    POST: provjeri lozinku → download JSON
    """
    from django.http import HttpResponse, JsonResponse

    if request.method == 'GET':
        return render(request, 'accounts/gdpr_export.html')

    # POST — sudo mode provjera
    password = request.POST.get('password', '')

    if not password or not request.user.check_password(password):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': 'Lozinka je netočna. Pokušajte ponovo.',
            }, status=403)
        from django.contrib import messages
        messages.error(request, 'Lozinka je netočna. Pokušajte ponovo.')
        return render(request, 'accounts/gdpr_export.html')

    # Lozinka OK — generiraj export
    try:
        from accounts.services.gdpr_export import GDPRExportService

        json_data = GDPRExportService.generate_export(request.user)

        # Audit log
        try:
            from core.models import SystemAuditLog
            SystemAuditLog.objects.create(
                user=request.user,
                action='export',
                model_name='User',
                object_id=str(request.user.pk),
                object_repr=f'GDPR export za {request.user.username}',
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
        except Exception:
            pass

        filename = f'limit_connect_gdpr_{request.user.username}_{timezone.now().strftime("%Y%m%d")}.json'
        response = HttpResponse(json_data, content_type='application/json; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        import logging
        logging.getLogger(__name__).error('GDPR export error: %s', e)
        return JsonResponse({
            'success': False,
            'error': 'Sistemska greška pri generiranju izvoza.',
        }, status=500)


# ── GDPR ANONIMIZACIJA (Clanak 17) ────────────────────────────────

@login_required
def gdpr_delete_view(request):
    """
    GDPR brisanje (anonimizacija) osobnih podataka -- Sudo Mode.
    GET: prikazi formu za potvrdu lozinke + upozorenje
    POST: provjeri lozinku -> anonimizacija -> logout
    """
    if request.method == 'GET':
        return render(request, 'accounts/gdpr_delete.html')

    # POST -- sudo mode provjera
    password = request.POST.get('password', '')

    if not password or not request.user.check_password(password):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': 'Lozinka je netocna. Pokusajte ponovo.',
            }, status=403)
        from django.contrib import messages as _msgs
        _msgs.error(request, 'Lozinka je netocna. Pokusajte ponovo.')
        return render(request, 'accounts/gdpr_delete.html')

    # Lozinka OK -- pokreni anonimizaciju
    try:
        from accounts.services.gdpr import GDPRAnonymizationService

        result = GDPRAnonymizationService.anonymize_user(request.user)

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if is_ajax:
            logout(request)
            return JsonResponse({
                'success': True,
                'message': 'Vas racun je trajno anonimiziran. Odjavljujemo vas.',
                'actions': result.get('actions', []),
            })

        logout(request)
        from django.contrib import messages as _msgs
        _msgs.success(request, 'Vas racun je trajno anonimiziran sukladno GDPR Clanku 17.')
        return redirect('login')

    except Exception as e:
        import logging
        logging.getLogger(__name__).error('GDPR delete error: %s', e)
        return JsonResponse({
            'success': False,
            'error': 'Sistemska greska pri anonimizaciji.',
        }, status=500)


# ── EMAIL VERIFICATION
def verify_email(request, token):
    """
    GET /auth/verify-email/<token>/
    Verificira email adresu korisnika.
    """
    from accounts.email_verification import verify_email_token

    success, user, message = verify_email_token(token, request)

    if success:
        messages.success(request,
            'Email adresa uspjesno verificirana! '
            'Vas racun je sada potpuno aktivan.'
        )
        # Audit
        try:
            from core.models import BookingSignature
            BookingSignature.log(request, 'approve',
                target_model='User', target_id=str(user.pk),
                target_repr=f'Email verified: {user.email}')
        except Exception:
            pass
        if request.user.is_authenticated:
            return redirect('/')
        return redirect('login')
    else:
        if 'istekao' in message.lower() or 'expired' in message.lower():
            messages.error(request,
                'Verifikacijski link je istekao (72h). '
                'Prijavite se i kliknite "Posalji ponovo" na dashboardu, '
                'ili nas kontaktirajte: info@limit-connect.com'
            )
        elif 'verificiran' in message.lower() or 'already' in message.lower():
            messages.info(request,
                'Email adresa je vec verificirana. Mozete se normalno prijaviti.'
            )
        else:
            messages.warning(request,
                f'{message} Ako imate poteskoca, kontaktirajte nas: info@limit-connect.com'
            )
        return redirect('login')


@login_required
def resend_verification(request):
    """
    POST /auth/resend-verification/
    Ponovo salje verifikacijski email.
    """
    from accounts.email_verification import resend_verification_email

    if request.method != 'POST':
        return redirect('/')

    user = request.user

    # Provjera: email vec verificiran?
    try:
        if user.profile.email_verified:
            messages.info(request, 'Vas email je vec verificiran! Sve je u redu.')
            return redirect(request.META.get('HTTP_REFERER', '/'))
    except Exception:
        pass

    # Provjera: postoji li drugi korisnik s istim emailom?
    from django.contrib.auth.models import User as AuthUser
    dupes = AuthUser.objects.filter(email=user.email).exclude(pk=user.pk)
    if dupes.exists():
        dupe_names = ', '.join(d.username for d in dupes[:3])
        messages.warning(request,
            f'U sustavu postoji jos {dupes.count()} racun(a) s ovom email adresom '
            f'({dupe_names}). Ako je to vas stariji racun, kontaktirajte nas '
            f'na info@limit-connect.com za spajanje racuna.'
        )

    success, message = resend_verification_email(user)
    if success:
        messages.success(request,
            f'Verifikacijski email poslan na {user.email}. '
            f'Provjerite inbox i spam/junk mapu. Link vrijedi 72 sata.'
        )
    else:
        if 'Previse' in message or 'limit' in message.lower():
            messages.error(request,
                'Dosegnuli ste limit od 3 pokusaja u 24 sata. '
                'Provjerite spam mapu ili nas kontaktirajte: info@limit-connect.com'
            )
        else:
            messages.warning(request, message)

    return redirect(request.META.get('HTTP_REFERER', '/'))
