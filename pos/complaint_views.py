"""
pos/complaint_views.py — Globalna Knjiga prigovora i utisaka.

Views:
- complaint_public_form: Mobile-first forma BEZ logina (QR pristup)
- complaint_api_public: REST API za public form submission
- complaint_respond: Admin odgovor s WhatsApp/email dostavom
- complaint_dashboard: Statistike i analitika
"""
import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from companies.models import Company
from core.company_utils import get_user_company

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  PUBLIC FORM — Mobile-first, no login required (QR entry)
# ═══════════════════════════════════════════════════════════════════════

def complaint_public_form(request):
    """
    Mobile-first forma za prigovor/utisak.
    Pristup: /pos/prigovori/new/?company=X&source=qr
    BEZ logina — potrošač sam ispunjava na svom mobitelu.
    """
    company_id = request.GET.get('company', '')
    source = request.GET.get('source', 'qr')
    record_type = request.GET.get('type', '')  # pre-select type

    company = None
    if company_id:
        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist:
            pass

    # If no company from URL, try logged-in user
    if not company and request.user.is_authenticated:
        company = get_user_company(request)

    if not company:
        return render(request, 'pos/complaint_public_form.html', {
            'error': _('Tvrtka nije pronađena. Molimo skenirajte QR kod ponovno.')
        })

    # Detect language from company country or browser
    lang = 'hr'
    if hasattr(company, 'country') and company.country == 'DE':
        lang = 'de'
    accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    if 'de' in accept_lang[:5]:
        lang = 'de'
    elif 'en' in accept_lang[:5]:
        lang = 'en'

    return render(request, 'pos/complaint_public_form.html', {
        'company': company,
        'source_module': source,
        'default_type': record_type,
        'lang': lang,
    })


@csrf_exempt
def complaint_api_public(request):
    """
    POST /pos/api/prigovori/public/
    Public API — no login required. Creates complaint/impression record.
    Returns confirmation with integrity hash.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    company_id = data.get('company_id')
    if not company_id:
        return JsonResponse({'error': 'company_id required'}, status=400)

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        return JsonResponse({'error': 'Company not found'}, status=404)

    # Validate required fields
    ime = (data.get('ime', '') or '').strip()
    opis = (data.get('opis', '') or '').strip()
    record_type = data.get('record_type', 'prigovor')

    if not ime:
        return JsonResponse({'error': _('Ime je obavezno')}, status=400)
    if not opis and record_type in ('prigovor', 'reklamacija'):
        return JsonResponse({'error': _('Opis je obavezan za prigovor')}, status=400)

    from pos.models import KnjigaPrigovora

    # Get IP
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR')
    )

    # Parse GPS
    gps_lat = None
    gps_lng = None
    gps = data.get('gps')
    if gps and isinstance(gps, dict):
        try:
            gps_lat = round(float(gps.get('lat', 0)), 7) or None
            gps_lng = round(float(gps.get('lng', 0)), 7) or None
        except (ValueError, TypeError):
            pass

    # Parse signature timestamp
    sig_ts = None
    if data.get('signature_timestamp'):
        try:
            from django.utils.dateparse import parse_datetime
            sig_ts = parse_datetime(data['signature_timestamp']) or timezone.now()
        except Exception:
            sig_ts = timezone.now()

    # Star rating validation
    star = data.get('star_rating')
    if star is not None:
        try:
            star = int(star)
            if star < 1 or star > 5:
                star = None
        except (ValueError, TypeError):
            star = None

    p = KnjigaPrigovora(
        company=company,
        record_type=record_type,
        ime_potrosaca=ime[:200],
        kontakt=data.get('kontakt', '')[:200],
        consumer_email=data.get('email', '')[:254],
        consumer_phone=data.get('phone', '')[:30],
        opis_prigovora=opis or data.get('opis', _('Pozitivna ocjena')) or '',
        source_module=data.get('source_module', 'qr'),
        source_url=data.get('source_url', '')[:200],
        language=data.get('language', 'hr')[:2],
        star_rating=star,
        # SES metadata
        gps_latitude=gps_lat,
        gps_longitude=gps_lng,
        device_info=(data.get('device_info', '') or '')[:500],
        client_ip=ip,
        signature_timestamp=sig_ts,
        # Identity
        id_photo=data.get('id_photo', '') or '',
        signature=data.get('signature', '') or '',
        voice_input=bool(data.get('voice_input', False)),
        # Created by (if authenticated)
        created_by=request.user if request.user.is_authenticated else None,
    )
    p.save()

    # Audio recording (base64 WebM → file)
    audio_b64 = data.get('audio_recording', '')
    if audio_b64:
        import base64
        from django.core.files.base import ContentFile
        try:
            audio_data = base64.b64decode(audio_b64.split(',')[-1])
            p.audio_recording.save(
                f'prigovor_{p.redni_broj}.webm',
                ContentFile(audio_data), save=True,
            )
        except Exception:
            pass

    # Trigger AI analysis (async Celery)
    try:
        from pos.tasks import ai_analyze_prigovor
        ai_analyze_prigovor.delay(p.pk)
    except Exception:
        logger.debug('AI analysis task not available')

    # Send confirmation via WhatsApp if phone provided
    if p.consumer_phone:
        try:
            _send_complaint_confirmation_wa(p)
        except Exception:
            logger.debug('WhatsApp confirmation failed')

    # Send confirmation via email if email provided
    if p.consumer_email:
        try:
            _send_complaint_confirmation_email(p)
        except Exception:
            logger.debug('Email confirmation failed')

    # Notify admin about new complaint
    try:
        _notify_admin_new_complaint(p)
    except Exception:
        logger.debug('Admin notification failed')

    type_labels = {
        'prigovor': _('Prigovor zaprimljen'),
        'pohvala': _('Hvala na pohvali!'),
        'utisak': _('Hvala na utiscima!'),
        'reklamacija': _('Reklamacija zaprimljena'),
        'prijedlog': _('Hvala na prijedlogu!'),
    }

    return JsonResponse({
        'success': True,
        'redni_broj': p.redni_broj,
        'message': str(type_labels.get(record_type, _('Zapis evidentiran'))),
        'integrity_hash': p.integrity_hash,
        'deadline': p.dana_do_roka,
    })


# ═══════════════════════════════════════════════════════════════════════
#  ADMIN RESPOND — with WhatsApp/email delivery
# ═══════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def complaint_respond(request):
    """Admin odgovor na prigovor/reklamaciju s automatskom dostavom."""
    company = get_user_company(request)
    data = json.loads(request.body)

    from pos.models import KnjigaPrigovora
    p = get_object_or_404(KnjigaPrigovora, pk=data.get('id'), company=company)

    p.odgovor = data.get('odgovor', '')
    p.datum_odgovora = timezone.now().date()
    p.responded_by = request.user
    p.response_channel = data.get('channel', 'email')
    p.response_sent_at = timezone.now()
    p.save()

    # Deliver response
    channel = data.get('channel', 'email')
    if channel in ('whatsapp', 'both') and p.consumer_phone:
        try:
            _send_response_wa(p)
        except Exception:
            logger.warning('WhatsApp response delivery failed for #%d', p.redni_broj)

    if channel in ('email', 'both') and p.consumer_email:
        try:
            _send_response_email(p)
        except Exception:
            logger.warning('Email response delivery failed for #%d', p.redni_broj)

    return JsonResponse({
        'success': True,
        'message': f'Odgovor poslan na prigovor #{p.redni_broj} putem {channel}.',
    })


# ═══════════════════════════════════════════════════════════════════════
#  NOTIFICATION HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _send_complaint_confirmation_wa(p):
    """WhatsApp potvrda potrošaču."""
    from core.whatsapp_tasks import send_whatsapp_text_task
    type_label = dict(p.RECORD_TYPES).get(p.record_type, p.record_type)
    msg = (
        f"✅ {type_label} zaprimljen/a\n\n"
        f"Poštovani/a {p.ime_potrosaca},\n"
        f"Vaš zapis #{p.redni_broj} je evidentiran kod {p.company.name}.\n"
    )
    if p.needs_response:
        msg += f"\nRok za odgovor: {p.legal_deadline_days} dana.\n"
    msg += f"\nHash: {p.integrity_hash[:16]}..."
    send_whatsapp_text_task.delay(p.consumer_phone, msg)


def _send_complaint_confirmation_email(p):
    """Email potvrda potrošaču."""
    from django.core.mail import send_mail
    from django.conf import settings
    type_label = dict(p.RECORD_TYPES).get(p.record_type, p.record_type)
    subject = f'{type_label} #{p.redni_broj} — {p.company.name}'
    body = (
        f'Poštovani/a {p.ime_potrosaca},\n\n'
        f'Vaš {type_label.lower()} je zaprimljen i evidentiran pod brojem #{p.redni_broj}.\n'
    )
    if p.needs_response:
        body += f'Odgovor ćete primiti u zakonskom roku od {p.legal_deadline_days} dana.\n'
    body += (
        f'\nIntegritetski hash: {p.integrity_hash}\n'
        f'Ovaj hash je dokaz autentičnosti i nepromjenjivosti Vašeg zapisa.\n\n'
        f'S poštovanjem,\n{p.company.name}\n'
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [p.consumer_email], fail_silently=True)
    except Exception:
        pass


def _send_response_wa(p):
    """WhatsApp dostava odgovora potrošaču."""
    from core.whatsapp_tasks import send_whatsapp_text_task
    msg = (
        f"📋 Odgovor na Vaš prigovor #{p.redni_broj}\n\n"
        f"Poštovani/a {p.ime_potrosaca},\n\n"
        f"{p.odgovor}\n\n"
        f"S poštovanjem,\n{p.company.name}"
    )
    send_whatsapp_text_task.delay(p.consumer_phone, msg)


def _send_response_email(p):
    """Email dostava odgovora potrošaču."""
    from django.core.mail import send_mail
    from django.conf import settings
    subject = f'Odgovor na prigovor #{p.redni_broj} — {p.company.name}'
    body = (
        f'Poštovani/a {p.ime_potrosaca},\n\n'
        f'U vezi Vašeg prigovora od {p.datum_primitka.strftime("%d.%m.%Y")} '
        f'(evidencijski broj #{p.redni_broj}), odgovaramo:\n\n'
        f'{p.odgovor}\n\n'
        f'S poštovanjem,\n{p.company.name}\n\n'
        f'---\n'
        f'Ako niste zadovoljni odgovorom, možete se obratiti:\n'
        f'• Sudski nadležnom tijelu za alternativno rješavanje sporova\n'
        f'• Inspektoratu za zaštitu potrošača\n'
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [p.consumer_email], fail_silently=True)
    except Exception:
        pass


def _notify_admin_new_complaint(p):
    """Obavijesti admin o novom zapisu. WA + push."""
    if p.record_type not in ('prigovor', 'reklamacija'):
        return  # Don't spam for pohvale/utisci

    # Find company admins
    from accounts.models import UserProfile
    admins = UserProfile.objects.filter(
        company=p.company,
        role__in=['tenant_admin', 'company_admin'],
    ).select_related('user')

    for profile in admins[:3]:  # Max 3 admins
        # WhatsApp to admin
        if profile.phone:
            try:
                from core.whatsapp_tasks import send_whatsapp_text_task
                priority = '🔴' if p.ai_priority >= 4 else '🟡' if p.ai_priority >= 2 else '🟢'
                msg = (
                    f"{priority} Novi prigovor #{p.redni_broj}\n\n"
                    f"Od: {p.ime_potrosaca}\n"
                    f"Opis: {p.opis_prigovora[:200]}\n"
                    f"Rok: {p.legal_deadline_days} dana\n\n"
                    f"Odgovorite na: https://limit-connect.com/pos/prigovori/"
                )
                send_whatsapp_text_task.delay(profile.phone, msg)
            except Exception:
                pass

        # In-app notification
        try:
            from notifications.models import Notification
            Notification.objects.create(
                recipient=profile.user,
                company=p.company,
                title=f'Novi prigovor #{p.redni_broj}',
                message=f'{p.ime_potrosaca}: {p.opis_prigovora[:100]}',
                url='/pos/prigovori/',
                notification_type='warning',
            )
        except Exception:
            pass
