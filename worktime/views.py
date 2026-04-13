from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rest_framework import permissions, viewsets
from django.core.exceptions import ObjectDoesNotExist

from .models import *
from .serializers import *


@extend_schema_view(list=extend_schema(tags=["Worktime"]))
class WorkGroupViewSet(viewsets.ModelViewSet):
    serializer_class = WorkGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        return WorkGroup.objects.filter(company=company).select_related("company", "manager", "members") if company else WorkGroup.objects.none()

@extend_schema_view(list=extend_schema(tags=["Worktime"]))
class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        return Project.objects.filter(company=company).select_related("company", "work_group", "members") if company else Project.objects.none()

@extend_schema_view(list=extend_schema(tags=["Worktime"]))
class EmployeeProfileViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        return EmployeeProfile.objects.filter(company=company).select_related("company", "user", "work_group") if company else EmployeeProfile.objects.none()

@extend_schema_view(list=extend_schema(tags=["Worktime"]))
class TimeEntryViewSet(viewsets.ModelViewSet):
    serializer_class = TimeEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        return TimeEntry.objects.filter(company=company).select_related("company", "user", "project") if company else TimeEntry.objects.none()

@login_required
def index(request):
    return render(request, 'worktime/index.html', {})
@login_required
def worker_camera_view(request):
    """Sučelje za radnike na terenu (Kamera)"""
    from burza.models import ProjectLead
    # Radnik bira na kojem je projektu od aktivnih
    active_leads = ProjectLead.objects.filter(status__in=['PREUZETO', 'NA_BURZI', 'INTERNA_PROCJENA'])
    return render(request, 'dashboards/worker_camera.html', {'active_leads': active_leads})

@login_required
def worker_camera_upload(request):
    """API za primanje slike s mobitela"""
    from django.http import JsonResponse

    from burza.models import ProjectLead

    from .models import ProjectPhoto

    if request.method == 'POST':
        image = request.FILES.get('image')
        lead_id = request.POST.get('lead_id')
        note = request.POST.get('note', '')

        if not image:
            return JsonResponse({'ok': False, 'error': 'Nije prenesena slika.'}, status=400)

        lead = None
        if lead_id:
            try:
                lead = ProjectLead.objects.get(id=lead_id)
            except ObjectDoesNotExist:
                pass

        ProjectPhoto.objects.create(
            user=request.user,
            project_lead=lead,
            image=image,
            note=note
        )
        return JsonResponse({'ok': True, 'msg': 'Fotografija uspješno spremljena u sustav!'})
    return JsonResponse({'ok': False, 'error': 'Nedozvoljena metoda.'}, status=405)


# ── Quick-add Project API ──────────────────────────────────────────
@login_required
def api_quick_create_project(request):
    """Create project via AJAX from quick-add modal."""
    import json
    from django.http import JsonResponse
    from core.company_utils import get_user_company

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema aktivne firme'}, status=400)

    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'error': 'Naziv projekta je obavezan'}, status=400)

        from worktime.models import Project
        project = Project(
            company=company,
            name=name,
            code=data.get('code', ''),
            hourly_rate=data.get('hourly_rate') or 0,
            description=data.get('description', ''),
        )
        project.save()
        return JsonResponse({
            'ok': True,
            'id': project.pk,
            'name': project.name,
            'message': f'Projekt "{project.name}" dodan!'
        })
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'error': str(e)}, status=400)


# ══════════════════════════════════════════════════════════════════════════════
# HYBRID TIME TRACKING API — Clock In/Out, Geofence, Auditor
# ══════════════════════════════════════════════════════════════════════════════
import math
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as drf_status
from drf_spectacular.utils import extend_schema, extend_schema_view



def _haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two GPS points in meters (Haversine formula)."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _get_worker_company(user):
    """Get company for a worker via profile or direct field."""
    try:
        return user.profile.company
    except AttributeError:
        pass
    try:
        return user.employeeprofile.company
    except AttributeError:
        pass
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_clock_in(request):
    """
    Clock-in with geofence verification.
    POST /api/hr/clock-in/
    Body: {lat: float, lon: float}
    """
    from worktime.models import TimeLog

    lat = request.data.get('lat')
    lon = request.data.get('lon')

    if lat is None or lon is None:
        return Response(
            {'error': 'GPS koordinate su obavezne (lat, lon).'},
            status=drf_status.HTTP_400_BAD_REQUEST
        )

    lat = float(lat)
    lon = float(lon)

    company = _get_worker_company(request.user)
    if not company:
        return Response(
            {'error': 'Radnik nema dodijeljenu tvrtku.'},
            status=drf_status.HTTP_400_BAD_REQUEST
        )

    # Geofence check
    company_lat = getattr(company, 'latitude', None)
    company_lon = getattr(company, 'longitude', None)
    geofence_radius = getattr(company, 'geofence_radius', 200) or 200

    if company_lat and company_lon:
        distance = _haversine(lat, lon, company_lat, company_lon)
        if distance > geofence_radius:
            return Response({
                'error': (
                    f'Prijava odbijena: udaljenost od tvrtke je {distance:.0f}m, '
                    f'dozvoljeno max {geofence_radius}m. '
                    f'Morate biti fizicki prisutni na lokaciji tvrtke.'
                ),
                'distance': round(distance, 1),
                'max_allowed': geofence_radius,
            }, status=drf_status.HTTP_403_FORBIDDEN)
    else:
        distance = None

    # Check if already clocked in
    from django.utils import timezone
    existing = TimeLog.objects.filter(
        user=request.user, status='OPEN'
    ).first()
    if existing:
        return Response({
            'error': 'Vec imate otvorenu smjenu. Prvo se odjavite.',
            'open_since': existing.start_time.isoformat(),
        }, status=drf_status.HTTP_409_CONFLICT)

    now = timezone.now()
    log = TimeLog.objects.create(
        company=company,
        user=request.user,
        start_time=now,
        date=now.date(),
        clock_in_lat=lat,
        clock_in_lon=lon,
        clock_in_distance=distance,
        status='OPEN',
    )

    return Response({
        'ok': True,
        'timelog_id': log.pk,
        'start_time': log.start_time.isoformat(),
        'distance': round(distance, 1) if distance else None,
        'message': 'Prijava uspjesna.',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_clock_out(request):
    """
    Clock-out with ArbZG automatic break deduction.
    POST /api/hr/clock-out/
    Body: {lat: float, lon: float, start_time: iso (optional), end_time: iso (optional)}
    """
    from worktime.models import TimeLog
    from django.utils import timezone
    import dateutil.parser

    lat = request.data.get('lat')
    lon = request.data.get('lon')

    company = _get_worker_company(request.user)

    # Support explicit start_time/end_time for testing
    start_time_str = request.data.get('start_time')
    end_time_str = request.data.get('end_time')

    if start_time_str and end_time_str:
        # Direct shift submission (e.g., from test or retroactive entry)
        start_time = dateutil.parser.isoparse(start_time_str)
        end_time = dateutil.parser.isoparse(end_time_str)

        log = TimeLog.objects.create(
            company=company,
            user=request.user,
            start_time=start_time,
            end_time=end_time,
            date=start_time.date(),
            clock_out_lat=float(lat) if lat else None,
            clock_out_lon=float(lon) if lon else None,
            status='OPEN',
        )
    else:
        # Close existing open shift
        log = TimeLog.objects.filter(
            user=request.user, status='OPEN'
        ).order_by('-start_time').first()

        if not log:
            return Response({
                'error': 'Nemate otvorenu smjenu za zatvaranje.',
            }, status=drf_status.HTTP_400_BAD_REQUEST)

        log.end_time = timezone.now()
        if lat is not None:
            log.clock_out_lat = float(lat)
        if lon is not None:
            log.clock_out_lon = float(lon)

    # Calculate geofence distance at clock-out
    if lat and lon and company:
        company_lat = getattr(company, 'latitude', None)
        company_lon = getattr(company, 'longitude', None)
        if company_lat and company_lon:
            log.clock_out_distance = _haversine(
                float(lat), float(lon), company_lat, company_lon
            )

    # Close shift — calculates ArbZG break + payable hours
    log.close_shift()

    return Response({
        'ok': True,
        'timelog_id': log.pk,
        'start_time': log.start_time.isoformat(),
        'end_time': log.end_time.isoformat(),
        'gross_hours': float(log.gross_hours),
        'break_minutes': log.break_minutes,
        'payable_hours': float(log.payable_hours),
        'message': (
            f'Smjena zatvorena. Bruto: {log.gross_hours}h, '
            f'ArbZG pauza: {log.break_minutes}min, '
            f'Za placu: {log.payable_hours}h.'
        ),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_auditor_flags(request):
    """
    Invisible Auditor — find discrepancies between TimeLog and ActivityEvent.
    GET /api/hr/auditor/flags/
    Returns shifts where first physical activity is >30 min after clock-in.
    """
    from worktime.models import TimeLog, ActivityEvent
    from django.utils import timezone
    import datetime

    company = _get_worker_company(request.user)
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')

    if not date_from:
        date_from = (timezone.now() - datetime.timedelta(days=7)).date()
    if not date_to:
        date_to = timezone.now().date()

    logs = TimeLog.objects.filter(
        company=company,
        date__gte=date_from,
        date__lte=date_to,
    ).select_related('user')

    flagged = []
    THRESHOLD_MINUTES = 30  # Flag if gap > 30 min

    for log in logs:
        # Find first ActivityEvent after clock-in for this user on this date
        first_activity = ActivityEvent.objects.filter(
            user=log.user,
            timestamp__gte=log.start_time,
            timestamp__date=log.date,
        ).order_by('timestamp').first()

        if first_activity:
            gap = (first_activity.timestamp - log.start_time).total_seconds() / 60
            if gap > THRESHOLD_MINUTES:
                flagged.append({
                    'timelog_id': log.pk,
                    'user_id': log.user_id,
                    'user_name': log.user.get_full_name() or log.user.username,
                    'date': str(log.date),
                    'clock_in': log.start_time.isoformat(),
                    'first_activity': first_activity.timestamp.isoformat(),
                    'gap_minutes': round(gap, 1),
                    'activity_type': first_activity.action,
                    'flag': f'Rupa od {int(gap)} minuta izmedju prijave i prvog rada.',
                })

                # Auto-flag the log
                if not log.audit_flag:
                    log.audit_flag = f'Gap {int(gap)}min do prvog rada'
                    log.is_audited = False
                    log.status = 'FLAGGED'
                    log.save(update_fields=['audit_flag', 'is_audited', 'status'])
        else:
            # No activity at all — even worse
            if log.status == 'CLOSED':
                flagged.append({
                    'timelog_id': log.pk,
                    'user_id': log.user_id,
                    'user_name': log.user.get_full_name() or log.user.username,
                    'date': str(log.date),
                    'clock_in': log.start_time.isoformat(),
                    'first_activity': None,
                    'gap_minutes': None,
                    'activity_type': None,
                    'flag': 'Nema fizicke aktivnosti za cijelu smjenu!',
                })

    return Response({
        'flagged_logs': flagged,
        'total_checked': logs.count(),
        'total_flagged': len(flagged),
    })


@login_required
@require_POST
def offline_sync(request):
    """Sync offline worktime entries from IndexedDB."""
    import json
    from django.http import JsonResponse
    from .models import TimeLog
    from core.company_utils import get_user_company

    data = json.loads(request.body)
    entries = data.get('entries', [])
    company = get_user_company(request)
    synced = 0

    for entry in entries:
        entry_type = entry.get('type', '')
        ts = entry.get('timestamp', '')

        if entry_type == 'clock_in':
            TimeLog.objects.create(
                user=request.user,
                company=company,
                clock_in=ts,
                source='offline',
                lat_in=entry.get('lat'),
                lon_in=entry.get('lon'),
                note=entry.get('note', '') + ' [OFFLINE SYNC]',
            )
            synced += 1

        elif entry_type == 'clock_out':
            # Find last open TimeLog
            last = TimeLog.objects.filter(
                user=request.user, clock_out__isnull=True
            ).order_by('-clock_in').first()
            if last:
                last.clock_out = ts
                last.duration_hours = entry.get('duration_hours', 0)
                last.lat_out = entry.get('lat')
                last.lon_out = entry.get('lon')
                last.save()
                synced += 1

    return JsonResponse({'ok': True, 'synced': synced})


# ═══════════════════════════════════════════════════════════════════════════
# FAZA 4: SELF-SERVICE PORTAL — Radnik vidi svoje sate i plaću
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def my_hours(request):
    """Radnik vidi SVOJE sate — ne može vidjeti tuđe."""
    from django.utils import timezone
    from django.db.models import Sum

    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    today = timezone.now().date()
    month_start = today.replace(day=1)

    # Odabir mjeseca
    import datetime
    month_str = request.GET.get('month', '')
    if month_str:
        try:
            year, month = month_str.split('-')
            month_start = datetime.date(int(year), int(month), 1)
            if int(month) == 12:
                month_end = datetime.date(int(year) + 1, 1, 1) - datetime.timedelta(days=1)
            else:
                month_end = datetime.date(int(year), int(month) + 1, 1) - datetime.timedelta(days=1)
        except (ValueError, TypeError):
            month_end = today
    else:
        month_end = today

    entries = TimeEntry.objects.filter(
        user=request.user,
        date__gte=month_start,
        date__lte=month_end,
    ).order_by('-date')

    agg = entries.aggregate(
        total=Sum('duration'),
        regular=Sum('regular_hours'),
        overtime=Sum('overtime_hours'),
        night=Sum('night_hours'),
    )
    total_hours = float(agg['total'] or 0)
    regular = float(agg['regular'] or 0)
    overtime = float(agg['overtime'] or 0)
    night = float(agg['night'] or 0)

    # Projekcija plaće
    projected_pay = None
    hourly_rate = None
    try:
        ep = request.user.employeeprofile
        hourly_rate = float(ep.hourly_rate)
        projected_pay = round(hourly_rate * total_hours, 2)
    except (ValueError, TypeError):
        pass

    # Dnevni breakdown za graf
    daily_data = []
    for entry in entries:
        daily_data.append({
            'date': entry.date.strftime('%d.%m'),
            'hours': float(entry.duration or 0),
            'overtime': float(entry.overtime_hours or 0),
            'type': entry.get_task_type_display(),
        })

    # Prethodni/sljedeći mjesec
    if month_start.month == 1:
        prev_month = f'{month_start.year - 1}-12'
    else:
        prev_month = f'{month_start.year}-{month_start.month - 1:02d}'
    if month_start.month == 12:
        next_month = f'{month_start.year + 1}-01'
    else:
        next_month = f'{month_start.year}-{month_start.month + 1:02d}'

    return render(request, 'worktime/my_hours.html', {
        'entries': entries,
        'total_hours': total_hours,
        'regular': regular,
        'overtime': overtime,
        'night': night,
        'projected_pay': projected_pay,
        'hourly_rate': hourly_rate,
        'daily_data': daily_data,
        'month_start': month_start,
        'month_end': month_end,
        'prev_month': prev_month,
        'next_month': next_month,
        'page_title': 'Moji sati',
    })


@login_required
def my_pay(request):
    """Radnik vidi svoje isplatne liste."""
    from payroll.models import Payslip
    company = getattr(getattr(request.user, 'profile', None), 'company', None)

    payslips = Payslip.objects.filter(
        user=request.user,
        payroll_run__company=company,
    ).select_related('payroll_run').order_by('-payroll_run__year', '-payroll_run__month')[:24]

    return render(request, 'worktime/my_pay.html', {
        'payslips': payslips,
        'page_title': 'Moja plaća',
    })


@login_required
def my_requests(request):
    """Radnik šalje zahtjeve — godišnji, bolovanje, PIN promjena."""

    if request.method == 'POST':
        req_type = request.POST.get('type', '')
        date_from = request.POST.get('date_from', '')
        date_to = request.POST.get('date_to', '')
        note = request.POST.get('note', '').strip()

        if req_type == 'pin_change':
            # PIN promjena — redirect na TriKey
            return redirect('trikey_change_pin')

        if not req_type or not date_from:
            messages.error(request, 'Popunite sva polja.')
            return redirect('worktime:my_requests')

        # Kreiraj TimeEntry za odsutnost
        try:
            import datetime
            df = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            dt = datetime.datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else df
            company = getattr(request.user.profile, 'company', None)

            # Za svaki dan u rasponu kreiraj entry
            created = 0
            current = df
            while current <= dt:
                if current.weekday() < 5:  # samo radni dani
                    TimeEntry.objects.create(
                        user=request.user,
                        company=company,
                        project_id=1,  # default project — TODO: absence project
                        date=current,
                        duration=8,
                        regular_hours=8,
                        absence_type=req_type,
                        status='PENDING',
                        description=note,
                        task_type='OTHER',
                    )
                    created += 1
                current += datetime.timedelta(days=1)

            # Audit
            try:
                from core.models import BookingSignature
                BookingSignature.log(request, 'create',
                    target_model='TimeEntry',
                    target_repr=f'Zahtjev: {req_type} {df}—{dt} ({created} dana)',
                )
            except ImportError:
                pass

            messages.success(request, f'Zahtjev poslan: {created} dana {req_type}. Čeka odobrenje.')
        except ImportError as e:
            messages.error(request, f'Greška: {e}')

        return redirect('worktime:my_requests')

    # GET — prikaži formu + aktivni zahtjevi
    pending = TimeEntry.objects.filter(
        user=request.user,
        status='PENDING',
        absence_type__gt='',
    ).order_by('-date')[:20]

    approved = TimeEntry.objects.filter(
        user=request.user,
        status='APPROVED',
        absence_type__gt='',
    ).order_by('-date')[:10]

    return render(request, 'worktime/my_requests.html', {
        'pending': pending,
        'approved': approved,
        'absence_types': TimeEntry.ABSENCE_TYPES[1:],  # skip empty
        'page_title': 'Moji zahtjevi',
    })
