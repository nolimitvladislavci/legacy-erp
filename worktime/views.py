from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rest_framework import permissions, viewsets

from .models import *
from .serializers import *


class WorkGroupViewSet(viewsets.ModelViewSet):
    serializer_class = WorkGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        return WorkGroup.objects.filter(company=company) if company else WorkGroup.objects.none()

class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        return Project.objects.filter(company=company) if company else Project.objects.none()

class EmployeeProfileViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        return EmployeeProfile.objects.filter(company=company) if company else EmployeeProfile.objects.none()

class TimeEntryViewSet(viewsets.ModelViewSet):
    serializer_class = TimeEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        return TimeEntry.objects.filter(company=company) if company else TimeEntry.objects.none()

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
            except Exception:
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
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ══════════════════════════════════════════════════════════════════════════════
# HYBRID TIME TRACKING API — Clock In/Out, Geofence, Auditor
# ══════════════════════════════════════════════════════════════════════════════
import math
from decimal import Decimal
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as drf_status


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
    except Exception:
        pass
    try:
        return user.employeeprofile.company
    except Exception:
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
