"""
core/cockpit_views.py
Fenix Cockpit — svi viewovi za superadmin dashboard.

Izvučeno iz core/views.py radi čistoće i održavanja.
Jedina točka istine za cockpit access kontrolu.
"""
import json
import os
import subprocess
import uuid

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import IntegrityError, DatabaseError
import logging
logger = logging.getLogger(__name__)

# ─── ACCESS CONTROL ────────────────────────────────────────────────────────────
# Jedino mjesto gdje se definira tko ima pristup cockpitu.
# Promjena ovdje automatski utječe na sve cockpit viewove.
COCKPIT_USERS = frozenset({'superadmin', 'marija.brtan'})


def _cockpit_allowed(user):
    """Vrati True ako user smije vidjeti cockpit."""
    return user.is_superuser or user.username in COCKPIT_USERS


def _cockpit_guard(request, json_error=False):
    """
    Provjeri pristup. Ako nije dozvoljen, vrati response objekt.
    Ako je dozvoljen, vrati None.
    Koristi:
        guard = _cockpit_guard(request)
        if guard: return guard
    """
    if not _cockpit_allowed(request.user):
        if json_error:
            return JsonResponse({'ok': False, 'error': 'Nemas pristup'}, status=403)
        return HttpResponseForbidden()
    return None


# ─── GLAVNI DASHBOARD ──────────────────────────────────────────────────────────

@login_required
def ivan_cockpit(request):
    """Fenix Cockpit — superadmin real-time dashboard."""
    guard = _cockpit_guard(request)
    if guard:
        return guard

    from datetime import timedelta
    from django.contrib.auth.models import User
    from django.db.models import Count, Sum

    from companies.models import Company
    from documents.models import ArhivaEntry
    from eracun.models import ERacun
    from invoicing.models import Invoice
    from pos.models import ImprovementSuggestion, POSReceipt, POSSession, POSTerminal
    from registration.models import CompanySubscription

    now        = timezone.now()
    today      = now.date()
    week_ago   = now - timedelta(days=7)
    month_start = today.replace(day=1)

    # Pretplate i MRR
    subs = list(CompanySubscription.objects.filter(is_active=True)
                .select_related('company').order_by('-monthly_fee'))
    mrr = sum(float(s.monthly_fee or 0) for s in subs)

    # POS danas
    pos_today_qs = POSReceipt.objects.filter(created_at__date=today, status='paid')
    pos_by_company = list(
        POSReceipt.objects.filter(created_at__date=today, status='paid')
        .values('session__terminal__company__name')
        .annotate(promet=Sum('total'), bonovi=Count('id'), p=Sum('total'), b=Count('id'))
        .order_by('-promet')
    )

    # Server info
    try:
        disk     = subprocess.check_output(['df', '-h', '/'], text=True).split('\n')[1].split()
        disk_used, disk_free, disk_pct = disk[2], disk[3], disk[4]
        disk_info = f'{disk_pct} ({disk_free} slobodno)'
    except Exception:
        disk_used = disk_free = disk_pct = disk_info = 'N/A'

    try:
        mem      = subprocess.check_output(['free', '-h'], text=True).split('\n')[1].split()
        mem_used, mem_total = mem[2], mem[1]
        mem_info = f'{mem_used} / {mem_total}'
    except Exception:
        mem_used = mem_total = mem_info = 'N/A'

    try:
        logs_raw    = subprocess.check_output(
            ['tail', '-30', '/var/www/fina-connect/logs/django.log'], text=True
        ).strip().split('\n')
        recent_logs = [l for l in logs_raw
                       if any(k in l for k in ('ERROR', 'WARNING', 'INFO whatsapp'))][-8:]
    except Exception:
        recent_logs = []

    # Izračunate vrijednosti
    _pos_promet = pos_today_qs.aggregate(t=Sum('total'))['t'] or 0
    _pos_bonovi = pos_today_qs.count()
    _pos_open   = POSSession.objects.filter(status='open').count()
    _pos_week   = (POSReceipt.objects
                   .filter(created_at__gte=week_ago, status='paid')
                   .aggregate(t=Sum('total'))['t'] or 0)
    _inv_count  = Invoice.objects.filter(date_issued__date__gte=month_start).count()
    _inv_promet = (Invoice.objects.filter(date_issued__date__gte=month_start)
                   .aggregate(t=Sum('total'))['t'] or 0)
    _users_week = User.objects.filter(last_login__gte=week_ago).count()

    context = {
        'now': now, 'today': today,
        # Korisnici
        'users_total':       User.objects.count(),
        'users_week':        _users_week,
        'users_active_week': _users_week,
        'users_never':       User.objects.filter(last_login__isnull=True, is_active=True).count(),
        # Kompanije
        'companies': Company.objects.count(),
        # Pretplate
        'subs': subs, 'mrr': mrr,
        # POS — kratka i duga imena za kompatibilnost
        'pos_promet':        _pos_promet,
        'pos_promet_danas':  _pos_promet,
        'pos_bonovi':        _pos_bonovi,
        'pos_bonovi_danas':  _pos_bonovi,
        'pos_open':          _pos_open,
        'pos_open_sessions': _pos_open,
        'pos_week':          _pos_week,
        'pos_terminal_count': POSTerminal.objects.filter(is_active=True).count(),
        'pos_by_company':    pos_by_company,
        # Fakture
        'inv_count':       _inv_count,
        'invoices_month':  _inv_count,
        'inv_promet':      _inv_promet,
        'invoices_promet': _inv_promet,
        # Ostali moduli
        'eracun_total': ERacun.objects.count(),
        'eracun_sent':  ERacun.objects.filter(status='sent').count(),
        'arhiva':       ArhivaEntry.objects.count(),
        'arhiva_total': ArhivaEntry.objects.count(),
        # Server
        'disk_info': disk_info, 'disk_used': disk_used, 'disk_free': disk_free,
        'mem_info':  mem_info,  'mem_used':  mem_used,  'mem_total': mem_total,
        # Logovi i feedback
        'logs': recent_logs, 'recent_logs': recent_logs,
        'feedback': ImprovementSuggestion.objects.filter(status='new')
                    .order_by('-created_at')[:5],
    }

    # Anthropic API status
    try:
        import anthropic
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if api_key:
            try:
                c = anthropic.Anthropic(api_key=api_key)
                c.messages.create(
                    model='claude-haiku-4-5-20251001',
                    max_tokens=5,
                    messages=[{'role': 'user', 'content': 'ok'}],
                )
                context['api_status']    = 'ok'
                context['api_key_short'] = api_key[:12] + '...' + api_key[-4:]
            except anthropic.BadRequestError as e:
                context['api_status']    = 'no_credit' if 'credit balance' in str(e) else 'error'
                context['api_error']     = str(e)[:100]
                context['api_key_short'] = api_key[:12] + '...' + api_key[-4:]
            except (IntegrityError, DatabaseError) as e:
                context['api_status'] = 'error'
                context['api_error']  = str(e)[:100]
        else:
            context['api_status'] = 'missing'
    except (IntegrityError, DatabaseError):
        context['api_status'] = 'unknown'

    # FINA certifikati
    try:
        from eracun.services.cert_monitor import check_all_certs
        certs = check_all_certs()
        context['certs']          = certs
        context['certs_expiring'] = [
            c for c in certs
            if c.get('status') in ('CRITICAL', 'WARNING', 'ATTENTION', 'EXPIRED')
        ]
    except ImportError:
        context['certs']          = []
        context['certs_expiring'] = []

    return render(request, 'dashboards/ivan_cockpit.html', context)


# ─── COCKPIT API ENDPOINTI ─────────────────────────────────────────────────────

@login_required
@require_POST
def cockpit_gemini_task(request):
    """Pokreni Gemini agenta iz Fenix Cockpit okruglog stola."""
    guard = _cockpit_guard(request, json_error=True)
    if guard:
        return guard

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    task_desc = data.get('task', '').strip()
    if not task_desc:
        return JsonResponse({'ok': False, 'error': 'Task prazan'}, status=400)

    max_steps = min(int(data.get('max_steps', 10)), 20)

    from core.gemini_tasks import run_gemini_task
    result = run_gemini_task.delay(
        task_desc, max_steps=max_steps, requested_by=request.user.username
    )
    return JsonResponse({'ok': True, 'task_id': str(result.id)})


@login_required
def cockpit_upload_photo(request):
    """Upload fotke s okruglog stola — sprema u media/cockpit/ i ažurira feed.json."""
    guard = _cockpit_guard(request, json_error=True)
    if guard:
        return guard

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    photo = request.FILES.get('photo')
    if not photo:
        return JsonResponse({'ok': False, 'error': 'Nema slike'}, status=400)

    seat    = request.POST.get('seat', 'unknown')
    message = request.POST.get('message', '')[:200]

    ext      = os.path.splitext(photo.name)[1] or '.jpg'
    filename = 'cockpit_%s_%s%s' % (seat, uuid.uuid4().hex[:8], ext)
    save_dir = '/var/www/fina-connect/media/cockpit/'
    os.makedirs(save_dir, exist_ok=True)

    with open(os.path.join(save_dir, filename), 'wb') as f:
        for chunk in photo.chunks():
            f.write(chunk)

    log_path = os.path.join(save_dir, 'feed.json')
    try:
        with open(log_path) as f:
            feed = json.load(f)
    except (json.JSONDecodeError, ValueError):
        feed = []

    feed.insert(0, {
        'filename':    filename,
        'url':         '/media/cockpit/%s' % filename,
        'seat':        seat,
        'user':        request.user.username,
        'message':     message,
        'time':        timezone.now().strftime('%H:%M'),
        'date':        timezone.now().strftime('%d.%m.'),
        'uploaded_at': timezone.now().isoformat(),
    })
    feed = feed[:50]

    with open(log_path, 'w') as f:
        json.dump(feed, f, ensure_ascii=False)

    return JsonResponse({'ok': True, 'url': '/media/cockpit/%s' % filename})


@login_required
def cockpit_photos(request):
    """Dohvati zadnjih 20 fotki s okruglog stola."""
    log_path = '/var/www/fina-connect/media/cockpit/feed.json'
    try:
        with open(log_path) as f:
            feed = json.load(f)
    except (json.JSONDecodeError, ValueError):
        feed = []
    return JsonResponse({'photos': feed[:20]})


@login_required
@require_POST
def cockpit_send_whatsapp(request):
    """Pošalji WhatsApp poruku iz cockpit okruglog stola."""
    guard = _cockpit_guard(request, json_error=True)
    if guard:
        return guard

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    phone   = data.get('phone', '').strip()
    message = data.get('message', '').strip()
    seat    = data.get('seat', '')

    if not phone or not message:
        return JsonResponse({'ok': False, 'error': 'phone i message obavezni'}, status=400)

    try:
        from core.whatsapp_tasks import send_whatsapp_text_task
        send_whatsapp_text_task.delay(phone, message)

        from superadmin_ai.models import PendingAIAction
        PendingAIAction.objects.create(
            module='cockpit',
            action_type='whatsapp_sent',
            description='[COCKPIT→%s] %s' % (seat.upper(), message[:100]),
            status='executed',
            payload={'phone': phone, 'seat': seat},
        )
        return JsonResponse({'ok': True})
    except (IntegrityError, DatabaseError) as e:
        return JsonResponse({'ok': False, 'error': str(e)[:100]}, status=500)


# ─── TIM CHAT ─────────────────────────────────────────────────────────────────

@login_required
def tim_chat(request):
    """Tim chat — prikazuje poruke korisnika (ImprovementSuggestion)."""
    from pos.models import ImprovementSuggestion
    qs = (ImprovementSuggestion.objects
          .filter(author=request.user)
          .order_by('-created_at')[:10])
    return render(request, 'dashboards/tim_chat.html', {'user_messages': qs})


@login_required
@require_POST
def tim_chat_send(request):
    """API: Spremi poruku iz tim chata kao ImprovementSuggestion."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    desc = data.get('description', '').strip()
    if not desc:
        return JsonResponse({'error': 'Prazna poruka'}, status=400)

    from core.company_utils import get_user_company
    from pos.models import ImprovementSuggestion

    s = ImprovementSuggestion.objects.create(
        company=get_user_company(request),
        author=request.user,
        source='user',
        title='Tim Chat: ' + desc[:50],
        description=desc,
        category=data.get('module', 'tim_chat'),
        priority=int(data.get('priority', 2)),
        status='new',
    )
    return JsonResponse({'ok': True, 'id': str(s.id), 'message': 'Poruka primljena ✅'})




# ─── SYSTEM IMPROVEMENT API (bez login-a) ─────────────────────────────────────

@csrf_exempt
@require_POST
def system_improvement_api(request):
    """
    Interni API za kreiranje ImprovementSuggestion s source='system'.
    Koristi se iz fenixNetworkError (JS auto-error-logging) i Celery taskova.
    Auth: X-System-Token header (HMAC od SECRET_KEY).
    Ako je korisnik ulogiran, koristi session auth kao fallback.
    """
    import hashlib
    from django.conf import settings

    # Auth: ulogiran korisnik ILI validan system token
    is_authenticated = hasattr(request, 'user') and request.user.is_authenticated
    system_token = request.META.get('HTTP_X_SYSTEM_TOKEN', '')
    expected_token = hashlib.sha256(
        ('fenix-system:' + settings.SECRET_KEY[:20]).encode()
    ).hexdigest()[:48]

    if not is_authenticated and system_token != expected_token:
        return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    title = (data.get('title') or '')[:200].strip()
    desc = (data.get('description') or '').strip()
    if not desc:
        return JsonResponse({'ok': False, 'error': 'description obavezan'}, status=400)
    if not title:
        title = 'System: ' + desc[:50]

    # Odredjivanje company
    company = None
    company_id = data.get('company_id', '')
    if company_id:
        from companies.models import Company
        company = Company.objects.filter(pk=company_id).first()
    elif is_authenticated:
        from core.company_utils import get_user_company
        company = get_user_company(request)

    if not company:
        from companies.models import Company
        company = Company.objects.first()
        if not company:
            return JsonResponse({'ok': False, 'error': 'Nema kompanije'}, status=400)

    from pos.models import ImprovementSuggestion
    source = data.get('source', 'system')
    if source not in ('system', 'anonymous'):
        source = 'system'

    s = ImprovementSuggestion.objects.create(
        company=company,
        author=request.user if is_authenticated else None,
        source=source,
        title=title,
        description=desc,
        category=(data.get('category') or 'auto')[:50],
        priority=min(max(int(data.get('priority', 3) or 3), 1), 5),
        status='new',
    )
    return JsonResponse({'ok': True, 'id': s.pk})

# ─── PARTNER SIGNUP API ───────────────────────────────────────────────────────

@csrf_exempt
def partner_signup_api(request):
    """
    Public API: Online registracija Tippgeber/Posrednik partnera.
    CSRF exempt — public endpoint, zaštita je validacija polja.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    first_name = request.POST.get('first_name', '').strip()
    last_name  = request.POST.get('last_name', '').strip()
    email      = request.POST.get('email', '').strip()
    phone      = request.POST.get('phone', '').strip()
    country    = request.POST.get('country', 'DE')
    address    = request.POST.get('address', '').strip()
    tax_id     = request.POST.get('tax_id', '').strip()
    iban       = request.POST.get('iban', '').strip()
    region     = request.POST.get('region', '').strip()
    lang       = request.POST.get('lang', 'de')

    if not all([first_name, last_name, email, phone, iban]):
        return JsonResponse(
            {'ok': False, 'error': 'Pflichtfelder fehlen / Obavezna polja nedostaju'},
            status=400,
        )

    from companies.models import Company
    from partners.models import AgentReferral, Partner

    konjik = Company.objects.filter(oib='37590751921').first() or Company.objects.first()

    if Partner.objects.filter(company=konjik, email=email).exists():
        return JsonResponse(
            {'ok': False, 'error': 'E-Mail bereits registriert / Email već registriran'},
            status=400,
        )

    partner = Partner.objects.create(
        company=konjik,
        name='%s %s' % (first_name, last_name),
        email=email, phone=phone,
        oib=tax_id or ('AGT-%s' % email[:8]),
        address=address, country=country,
        partner_type='agent', payment_term=14,
    )

    import hashlib
    ref_code = 'REF-%s-%s' % (
        last_name[:5].upper().replace(' ', ''),
        hashlib.md5(email.encode()).hexdigest()[:4].upper(),
    )
    AgentReferral.objects.create(
        agent=partner,
        referred_company=konjik,
        referral_code=ref_code,
        status='pending',
        commission_percent=20,
        commission_months=12,
        agent_iban=iban,
        contract_signed_at=timezone.now(),
        contract_ip=request.META.get('HTTP_X_FORWARDED_FOR',
                                     request.META.get('REMOTE_ADDR', '')),
        contract_user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
        expires_at=timezone.now() + timezone.timedelta(days=365),
    )

    # Spremi metadata JSON
    agents_dir = '/var/www/fina-connect/media/agents/'
    os.makedirs(agents_dir, exist_ok=True)
    agent_data = {
        'partner_id': partner.pk, 'referral_code': ref_code,
        'first_name': first_name, 'last_name': last_name,
        'email': email, 'phone': phone, 'country': country,
        'iban': iban, 'region': region, 'lang': lang,
        'signed_at': timezone.now().isoformat(),
        'ip': request.META.get('HTTP_X_FORWARDED_FOR',
                               request.META.get('REMOTE_ADDR', '')),
        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
        'agreed_terms': True, 'agreed_independent': True, 'agreed_tax': True,
    }
    with open(os.path.join(agents_dir, '%s_%s.json' % (
            partner.pk, email.replace('@', '_'))), 'w') as f:
        json.dump(agent_data, f, ensure_ascii=False, indent=2)

    # WhatsApp potvrda partneru
    try:
        from core.whatsapp import normalize_phone
        from core.whatsapp_tasks import send_whatsapp_text_task
        norm_phone = normalize_phone(phone)
        if norm_phone:
            if lang == 'de':
                wa_msg = (
                    'Willkommen als LIMIT Connect Partner! 🎉\n\n'
                    'Ihr Vertrag wurde digital unterzeichnet.\n'
                    'Partner-ID: %s\nProvision: 20%% monatlich, 12 Monate\n\n'
                    'Ihr Verkaufsmaterial:\nhttps://limit-connect.com/de/\n\n'
                    '— LIMIT Connect Team'
                ) % str(partner.pk)[:8]
            else:
                wa_msg = (
                    'Dobrodošli kao LIMIT Connect partner! 🎉\n\n'
                    'Vaš ugovor je digitalno potpisan.\n'
                    'Partner-ID: %s\nProvizija: 20%% mjesečno, 12 mjeseci\n\n'
                    '— LIMIT Connect tim'
                ) % str(partner.pk)[:8]
            send_whatsapp_text_task.delay(norm_phone, wa_msg)
    except ImportError:
        logger.exception("Failed to import normalize_phone")

    # Notifikacija superadminu
    try:
        from superadmin_ai.tasks import _notify_superadmins
        _notify_superadmins(
            title='Novi partner: %s %s (%s)' % (first_name, last_name, country),
            message='Email: %s\nTelefon: %s\nRegija: %s\nIBAN: %s' % (
                email, phone, region, iban[:8] + '...'),
            notification_type='system',
        )
    except ImportError:
        logger.exception("Failed to import _notify_superadmins")

    return JsonResponse({'ok': True, 'partner_id': str(partner.pk)[:8]})

@login_required
def feedback_count_api(request):
    """Vraća broj novih ImprovementSuggestion za badge u sidebaru."""
    if not request.user.is_superuser:
        return JsonResponse({'count': 0})
    from pos.models import ImprovementSuggestion
    count = ImprovementSuggestion.objects.filter(status='new', source='user').count()
    return JsonResponse({'count': count})

