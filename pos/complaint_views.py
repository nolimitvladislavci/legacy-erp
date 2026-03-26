"""
pos/complaint_views.py — Globalna Knjiga prigovora i utisaka.

Views:
- complaint_public_form: Mobile-first forma BEZ logina (QR pristup)
- complaint_api_public: REST API za public form submission
- complaint_respond: Admin odgovor s WhatsApp/email dostavom
- complaint_dashboard: Dashboard analytics (Chart.js)
- complaint_qr_terminal: QR per POSTerminal
- complaint_widget: Public embed widget (is_public=True)
- complaint_inspect: InspectionToken read-only pristup
- complaint_archive_pdf: Auto-archive u DocumentBlob
"""
import json
import hashlib
import logging
from collections import Counter
from datetime import timedelta
from io import BytesIO

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Avg, Count, Q, F
from django.db.models.functions import TruncMonth, TruncWeek
from django.template.loader import render_to_string

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
    terminal = request.GET.get('terminal', '')  # from QR per terminal

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
        'terminal_name': terminal,
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

    # Auto-archive PDF (async)
    try:
        from pos.tasks import archive_prigovor_pdf
        archive_prigovor_pdf.delay(p.pk)
    except Exception:
        logger.debug('Archive task not available')

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
#  ADMIN RESPOND — with WhatsApp/email delivery + ADR info
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
    p.adr_offered = data.get('adr_offered', True)
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

    # Auto-archive updated PDF
    try:
        from pos.tasks import archive_prigovor_pdf
        archive_prigovor_pdf.delay(p.pk)
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'message': f'Odgovor poslan na prigovor #{p.redni_broj} putem {channel}.',
    })


# ═══════════════════════════════════════════════════════════════════════
#  1. DASHBOARD ANALYTICS
# ═══════════════════════════════════════════════════════════════════════

@login_required
def complaint_dashboard(request):
    """Dashboard analitika za Knjigu prigovora i utisaka."""
    company = get_user_company(request)
    if not company:
        return redirect('pos:dashboard')

    from pos.models import KnjigaPrigovora
    qs = KnjigaPrigovora.objects.filter(company=company)

    # Date range filter
    months = int(request.GET.get('months', 12))
    date_from = timezone.now().date() - timedelta(days=months * 30)
    qs_period = qs.filter(datum_primitka__gte=date_from)

    # === KPI Cards ===
    total = qs_period.count()
    prigovori_cnt = qs_period.filter(record_type__in=['prigovor', 'reklamacija']).count()
    pohvale_cnt = qs_period.filter(record_type__in=['pohvala', 'utisak', 'prijedlog']).count()
    avg_rating = qs_period.filter(star_rating__isnull=False).aggregate(avg=Avg('star_rating'))['avg']
    pending_response = qs_period.filter(
        record_type__in=['prigovor', 'reklamacija'],
        datum_odgovora__isnull=True,
    ).count()
    escalated = qs_period.filter(is_escalated=True).count()
    overdue = sum(1 for p in qs_period.filter(
        record_type__in=['prigovor', 'reklamacija'],
        datum_odgovora__isnull=True,
    ) if p.rok_istekao)

    # === Trend by month ===
    monthly = list(
        qs_period.annotate(month=TruncMonth('datum_primitka'))
        .values('month')
        .annotate(
            cnt=Count('id'),
            prigovori=Count('id', filter=Q(record_type__in=['prigovor', 'reklamacija'])),
            pohvale=Count('id', filter=Q(record_type__in=['pohvala', 'utisak'])),
            avg_star=Avg('star_rating', filter=Q(star_rating__isnull=False)),
        )
        .order_by('month')
    )
    for m in monthly:
        m['month'] = m['month'].strftime('%Y-%m') if m['month'] else ''
        m['avg_star'] = round(float(m['avg_star'] or 0), 1)

    # === Breakdown by record_type ===
    by_type = list(
        qs_period.values('record_type')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')
    )

    # === Breakdown by ai_category (top 5) ===
    by_category = list(
        qs_period.exclude(ai_category='')
        .values('ai_category')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')[:5]
    )

    # === Breakdown by source_module ===
    by_source = list(
        qs_period.values('source_module')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')
    )

    # === Response time stats ===
    responded = qs_period.filter(
        datum_odgovora__isnull=False,
        record_type__in=['prigovor', 'reklamacija'],
    )
    response_times = []
    for p in responded:
        days = (p.datum_odgovora - p.datum_primitka).days
        response_times.append({
            'month': p.datum_primitka.strftime('%Y-%m'),
            'days': days,
        })
    avg_response_days = (
        sum(r['days'] for r in response_times) / len(response_times)
        if response_times else 0
    )

    # === Response time heatmap data (month vs day buckets) ===
    heatmap = {}
    for rt in response_times:
        m = rt['month']
        bucket = '0-3' if rt['days'] <= 3 else '4-7' if rt['days'] <= 7 else '8-14' if rt['days'] <= 14 else '15+'
        key = f"{m}|{bucket}"
        heatmap[key] = heatmap.get(key, 0) + 1

    # === Escalation stats ===
    esc_qs = qs_period.filter(is_escalated=True)
    esc_reasons = list(
        esc_qs.exclude(escalation_reason='')
        .values('escalation_reason')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')[:5]
    )

    # === AI Sentiment breakdown ===
    by_sentiment = list(
        qs_period.exclude(ai_sentiment='')
        .values('ai_sentiment')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')
    )

    context = {
        'company': company,
        'months': months,
        # KPIs
        'total': total,
        'prigovori_cnt': prigovori_cnt,
        'pohvale_cnt': pohvale_cnt,
        'avg_rating': round(float(avg_rating or 0), 1),
        'pending_response': pending_response,
        'escalated': escalated,
        'overdue': overdue,
        'avg_response_days': round(avg_response_days, 1),
        # Charts data (JSON)
        'monthly_json': json.dumps(monthly),
        'by_type_json': json.dumps(by_type),
        'by_category_json': json.dumps(by_category),
        'by_source_json': json.dumps(by_source),
        'by_sentiment_json': json.dumps(by_sentiment),
        'heatmap_json': json.dumps(heatmap),
        'esc_reasons_json': json.dumps(esc_reasons),
    }

    return render(request, 'pos/complaint_dashboard.html', context)


@login_required
def complaint_dashboard_api(request):
    """JSON API za dashboard (AJAX refresh)."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'No company'}, status=400)

    from pos.models import KnjigaPrigovora
    qs = KnjigaPrigovora.objects.filter(company=company)
    months = int(request.GET.get('months', 12))
    date_from = timezone.now().date() - timedelta(days=months * 30)
    qs = qs.filter(datum_primitka__gte=date_from)

    return JsonResponse({
        'total': qs.count(),
        'prigovori': qs.filter(record_type__in=['prigovor', 'reklamacija']).count(),
        'pohvale': qs.filter(record_type__in=['pohvala', 'utisak', 'prijedlog']).count(),
        'avg_rating': round(float(
            qs.filter(star_rating__isnull=False).aggregate(avg=Avg('star_rating'))['avg'] or 0
        ), 1),
        'pending': qs.filter(
            record_type__in=['prigovor', 'reklamacija'],
            datum_odgovora__isnull=True,
        ).count(),
        'escalated': qs.filter(is_escalated=True).count(),
    })


# ═══════════════════════════════════════════════════════════════════════
#  2. QR GENERIRANJE PER TERMINAL/LOKACIJA
# ═══════════════════════════════════════════════════════════════════════

@login_required
def complaint_qr_terminal(request, terminal_id):
    """Generira QR kod za Knjigu prigovora specifičnu za terminal."""
    from pos.models import POSTerminal
    company = get_user_company(request)
    terminal = get_object_or_404(POSTerminal, pk=terminal_id, company=company)

    fmt = request.GET.get('format', 'html')  # html, png, svg

    # URL koji QR sadrži
    base_url = 'https://limit-connect.com'
    qr_url = (
        f'{base_url}/pos/prigovori/new/'
        f'?company={company.pk}&source={terminal.terminal_code}'
        f'&terminal={terminal.name}'
    )

    if fmt == 'png':
        return _generate_qr_image(qr_url, fmt='png')
    elif fmt == 'svg':
        return _generate_qr_image(qr_url, fmt='svg')

    # HTML — print-ready A6 kartica
    return render(request, 'pos/complaint_qr_card.html', {
        'company': company,
        'terminal': terminal,
        'qr_url': qr_url,
    })


@login_required
def complaint_qr_list(request):
    """Lista svih terminala s QR kodovima za Knjigu prigovora."""
    company = get_user_company(request)
    if not company:
        return redirect('pos:dashboard')

    from pos.models import POSTerminal
    terminals = POSTerminal.objects.filter(company=company, is_active=True)

    return render(request, 'pos/complaint_qr_list.html', {
        'company': company,
        'terminals': terminals,
    })


def _generate_qr_image(url, fmt='png'):
    """Generira QR kod kao PNG ili SVG."""
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage

        if fmt == 'svg':
            qr = qrcode.QRCode(box_size=10, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(image_factory=SvgPathImage)
            buf = BytesIO()
            img.save(buf)
            return HttpResponse(buf.getvalue(), content_type='image/svg+xml')
        else:
            qr = qrcode.QRCode(box_size=10, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color='#1a1a2e', back_color='white')
            buf = BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return HttpResponse(buf.read(), content_type='image/png')
    except ImportError:
        # Fallback: return URL as text
        return HttpResponse(
            f'QR biblioteka nije instalirana. URL: {url}',
            content_type='text/plain',
        )


# ═══════════════════════════════════════════════════════════════════════
#  3. KNJIGA UTISAKA PUBLIC WIDGET (embed)
# ═══════════════════════════════════════════════════════════════════════

def complaint_widget(request, company_id):
    """
    Public widget — prikazuje is_public=True zapise (pohvale + utisci).
    Embed: <iframe src="/pos/prigovori/widget/123/"></iframe>
    """
    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        return HttpResponse('Tvrtka nije pronađena.', status=404)

    from pos.models import KnjigaPrigovora

    # Samo javno vidljivi zapisi
    public = KnjigaPrigovora.objects.filter(
        company=company,
        is_public=True,
        record_type__in=['pohvala', 'utisak', 'prijedlog'],
    ).order_by('-datum_primitka')[:10]

    # Agregat ocjena
    stats = KnjigaPrigovora.objects.filter(
        company=company,
        is_public=True,
        star_rating__isnull=False,
    ).aggregate(
        avg=Avg('star_rating'),
        cnt=Count('id'),
    )

    # Star distribution
    star_dist = {}
    if stats['cnt']:
        for s in range(1, 6):
            star_dist[s] = KnjigaPrigovora.objects.filter(
                company=company, is_public=True, star_rating=s,
            ).count()

    return render(request, 'pos/complaint_widget.html', {
        'company': company,
        'reviews': public,
        'avg_rating': round(float(stats['avg'] or 0), 1),
        'total_reviews': stats['cnt'] or 0,
        'star_dist': star_dist,
        'embed': request.GET.get('embed', '0') == '1',
    })


def complaint_widget_js(request, company_id):
    """JavaScript embed snippet — <script src="..."></script>."""
    base = 'https://limit-connect.com'
    js = f"""
(function() {{
    var iframe = document.createElement('iframe');
    iframe.src = '{base}/pos/prigovori/widget/{company_id}/?embed=1';
    iframe.style.width = '100%';
    iframe.style.minHeight = '400px';
    iframe.style.border = 'none';
    iframe.style.borderRadius = '12px';
    iframe.setAttribute('loading', 'lazy');
    document.currentScript.parentElement.appendChild(iframe);
}})();
"""
    return HttpResponse(js.strip(), content_type='application/javascript')


# ═══════════════════════════════════════════════════════════════════════
#  4. AUTO-ARCHIVE U DOCUMENTBLOB (helper, called from task)
# ═══════════════════════════════════════════════════════════════════════

def generate_prigovor_pdf_bytes(prigovor):
    """Generira PDF bytes za jedan prigovor/utisak."""
    from pos.models import KnjigaPrigovora

    # ADR info
    adr_info = _get_adr_info(prigovor)

    html = render_to_string('pos/knjiga_prigovora_single_pdf.html', {
        'p': prigovor,
        'company': prigovor.company,
        'adr': adr_info,
        'lang': prigovor.language or 'hr',
    })

    try:
        from xhtml2pdf import pisa
        buf = BytesIO()
        pisa.CreatePDF(html, dest=buf)
        buf.seek(0)
        return buf.read()
    except ImportError:
        return html.encode('utf-8')


def archive_prigovor_to_blob(prigovor):
    """Sprema PDF prigovora u DocumentBlob."""
    from documents.models import DocumentBlob

    pdf_bytes = generate_prigovor_pdf_bytes(prigovor)
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # Ako već postoji blob, ažuriraj
    if prigovor.archive_blob_id:
        try:
            blob = prigovor.archive_blob
            blob.file_data = pdf_bytes
            blob.file_size = len(pdf_bytes)
            blob.file_hash = file_hash
            blob.save(update_fields=['file_data', 'file_size', 'file_hash'])
            return blob
        except DocumentBlob.DoesNotExist:
            pass

    type_label = dict(prigovor.RECORD_TYPES).get(prigovor.record_type, prigovor.record_type)
    blob = DocumentBlob.objects.create(
        company=prigovor.company,
        filename=f'{type_label}_{prigovor.redni_broj}.pdf',
        content_type='application/pdf',
        file_data=pdf_bytes,
        file_size=len(pdf_bytes),
        file_hash=file_hash,
        source_type='knjiga_prigovora',
    )

    prigovor.archive_blob = blob
    prigovor.save(update_fields=['archive_blob'])

    return blob


# ═══════════════════════════════════════════════════════════════════════
#  5. ADR/ODR EU COMPLIANCE
# ═══════════════════════════════════════════════════════════════════════

def _get_adr_info(prigovor):
    """Vraća ADR/ODR informacije ovisno o zemlji."""
    lang = prigovor.language or 'hr'
    if lang == 'de':
        return {
            'title': 'Alternative Streitbeilegung (ADR)',
            'body': (
                'Gemäß der EU-Richtlinie 2013/11/EU (ADR-Richtlinie) und '
                'der Verordnung (EU) Nr. 524/2013 (ODR-Verordnung) informieren wir Sie:'
            ),
            'adr_body': (
                'Allgemeine Verbraucherschlichtungsstelle des Zentrums für Schlichtung e.V.\n'
                'Straßburger Str. 8, 77694 Kehl\n'
                'www.verbraucher-schlichter.de'
            ),
            'odr_link': 'https://ec.europa.eu/consumers/odr/',
            'odr_label': 'EU Online-Streitbeilegungsplattform (ODR)',
            'note': (
                'Wir sind nicht bereit oder verpflichtet, an Streitbeilegungsverfahren '
                'vor einer Verbraucherschlichtungsstelle teilzunehmen, bieten es jedoch freiwillig an.'
            ),
        }
    else:
        return {
            'title': 'Alternativno rješavanje sporova (ADR)',
            'body': (
                'Sukladno Direktivi EU 2013/11/EU (ADR Direktiva) i '
                'Uredbi EU br. 524/2013 (ODR Uredba) obavještavamo Vas:'
            ),
            'adr_body': (
                'Centar za mirenje pri Hrvatskoj gospodarskoj komori (HGK)\n'
                'Rooseveltov trg 2, 10000 Zagreb\n'
                'www.hgk.hr/centar-za-mirenje'
            ),
            'odr_link': 'https://ec.europa.eu/consumers/odr/',
            'odr_label': 'EU Platforma za online rješavanje sporova (ODR)',
            'note': (
                'Trgovac je dužan obavijestiti potrošača o mogućnosti alternativnog '
                'rješavanja spora (čl. 10 ZZP). Nova ADR Direktiva (01/2026) — '
                'transpozicija do 03/2028.'
            ),
        }


# ═══════════════════════════════════════════════════════════════════════
#  6. INSPECTION TOKEN INTEGRACIJA
# ═══════════════════════════════════════════════════════════════════════

def complaint_inspect(request, token):
    """
    Read-only pristup Knjizi prigovora putem InspectionToken.
    /inspect/<token>/prigovori/ — bez logina, vremenski ograničeno.
    """
    from core.models import InspectionToken

    try:
        tok = InspectionToken.objects.select_related('company').get(token=token)
    except InspectionToken.DoesNotExist:
        return HttpResponse('Token nije valjan.', status=404)

    if not tok.is_valid:
        return HttpResponse('Token je istekao ili deaktiviran.', status=403)

    if tok.scope not in ('prigovori', 'all'):
        return HttpResponse('Token nema pristup Knjizi prigovora.', status=403)

    # Record access
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR')
    )
    tok.record_access(ip=ip)

    from pos.models import KnjigaPrigovora
    qs = KnjigaPrigovora.objects.filter(company=tok.company).order_by('redni_broj')

    # Date filter from token
    if tok.date_from:
        qs = qs.filter(datum_primitka__gte=tok.date_from)
    if tok.date_to:
        qs = qs.filter(datum_primitka__lte=tok.date_to)

    fmt = request.GET.get('format', 'html')

    if fmt == 'pdf':
        return _inspection_pdf(tok.company, qs)

    return render(request, 'pos/complaint_inspect.html', {
        'company': tok.company,
        'prigovori': qs,
        'token': tok,
        'total': qs.count(),
        'prigovori_cnt': qs.filter(record_type__in=['prigovor', 'reklamacija']).count(),
        'pohvale_cnt': qs.filter(record_type__in=['pohvala', 'utisak', 'prijedlog']).count(),
    })


def _inspection_pdf(company, qs):
    """PDF za inspekcijski pregled."""
    prigovori = qs.filter(record_type__in=['prigovor', 'reklamacija'])
    pohvale = qs.filter(record_type__in=['pohvala', 'utisak', 'prijedlog'])

    html = render_to_string('pos/knjiga_prigovora_pdf.html', {
        'prigovori': prigovori,
        'pohvale': pohvale,
        'prigovori_count': prigovori.count(),
        'pohvale_count': pohvale.count(),
        'company': company,
        'lang': 'hr',
        'inspection_mode': True,
    })
    try:
        from xhtml2pdf import pisa
        buf = BytesIO()
        pisa.CreatePDF(html, dest=buf)
        buf.seek(0)
        response = HttpResponse(buf.read(), content_type='application/pdf')
        response['Content-Disposition'] = (
            'inline; filename="Inspekcija_Knjiga_Prigovora_%s.pdf"' % (company.name or 'firma')
        )
        return response
    except ImportError:
        return HttpResponse(html)


# ═══════════════════════════════════════════════════════════════════════
#  NOTIFICATION HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _send_complaint_confirmation_wa(p):
    """WhatsApp potvrda potrošaču."""
    from core.whatsapp_tasks import send_whatsapp_text_task
    type_label = dict(p.RECORD_TYPES).get(p.record_type, p.record_type)
    msg = (
        f"\u2705 {type_label} zaprimljen/a\n\n"
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
    adr = _get_adr_info(p)
    msg = (
        f"\U0001f4cb Odgovor na Vaš prigovor #{p.redni_broj}\n\n"
        f"Poštovani/a {p.ime_potrosaca},\n\n"
        f"{p.odgovor}\n\n"
        f"S poštovanjem,\n{p.company.name}"
    )
    if p.adr_offered:
        msg += f"\n\n---\n{adr['title']}\n{adr['adr_body']}\n{adr['odr_link']}"
    send_whatsapp_text_task.delay(p.consumer_phone, msg)


def _send_response_email(p):
    """Email dostava odgovora potrošaču s ADR informacijama."""
    from django.core.mail import send_mail
    from django.conf import settings
    adr = _get_adr_info(p)
    subject = f'Odgovor na prigovor #{p.redni_broj} — {p.company.name}'
    body = (
        f'Poštovani/a {p.ime_potrosaca},\n\n'
        f'U vezi Vašeg prigovora od {p.datum_primitka.strftime("%d.%m.%Y")} '
        f'(evidencijski broj #{p.redni_broj}), odgovaramo:\n\n'
        f'{p.odgovor}\n\n'
        f'S poštovanjem,\n{p.company.name}\n\n'
    )
    # ADR/ODR footer
    body += (
        f'---\n'
        f'{adr["title"]}\n'
        f'{adr["body"]}\n\n'
        f'{adr["adr_body"]}\n\n'
        f'{adr["odr_label"]}: {adr["odr_link"]}\n\n'
        f'{adr["note"]}\n'
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
                priority = '\U0001f534' if p.ai_priority >= 4 else '\U0001f7e1' if p.ai_priority >= 2 else '\U0001f7e2'
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
