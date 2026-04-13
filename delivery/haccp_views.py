"""
delivery/haccp_views.py — HACCP Forensic Report + Dispatcher Incident Management
"""
import hashlib
import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import HACCPIncident, SmartBox, SensorReading


@login_required
def haccp_incidents(request):
    """Dispatcher view — lista svih otvorenih HACCP incidenata."""
    from .models import HACCPIncident
    open_incidents = HACCPIncident.objects.filter(is_resolved=False).select_related('smart_box')
    resolved_recent = HACCPIncident.objects.filter(
        is_resolved=True,
        resolved_at__gte=timezone.now() - timezone.timedelta(days=7)
    ).select_related('smart_box', 'resolved_by')[:20]

    return render(request, 'delivery/haccp_incidents.html', {
        'open_incidents': open_incidents,
        'resolved_recent': resolved_recent,
    })


@login_required
@require_POST
def haccp_resolve(request, pk):
    """Dispatcher zatvara incident s obveznom biljeskom."""
    incident = get_object_or_404(HACCPIncident, pk=pk, is_resolved=False)
    note = request.POST.get('resolution_note', '').strip()
    if not note:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Resolution note je obavezan'}, status=400)
        from django.contrib import messages
        from django.utils.translation import gettext as _
        messages.error(request, _('Morate unijeti sto je poduzeto (resolution note).'))
        return redirect('delivery:haccp_incidents')

    incident.resolve(request.user, note)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'incident_id': pk})
    return redirect('delivery:haccp_incidents')


@login_required
def haccp_forensic_report(request, pk):
    """
    Generira forenzicki HACCP izvjestaj sa SHA-256 pecatom.
    EU 852/2004 compliant — za inspekciju i osiguravajuce kuce.
    """
    incident = get_object_or_404(HACCPIncident, pk=pk)
    box = incident.smart_box

    # Prave senzorske podatke iz baze
    reading_ids = incident.reading_ids or []
    if reading_ids:
        readings = SensorReading.objects.filter(id__in=reading_ids).order_by('timestamp')
    else:
        # Fallback: sva ocitanja za box u periodu incidenta
        readings = SensorReading.objects.filter(
            smart_box=box,
            timestamp__gte=incident.breach_start - timezone.timedelta(minutes=15),
            timestamp__lte=(incident.breach_end or incident.breach_start) + timezone.timedelta(minutes=15),
        ).order_by('timestamp')

    readings_data = list(readings.values('id', 'timestamp', 'temperature', 'latitude', 'longitude'))

    # SHA-256 digital seal
    seal_input = json.dumps([
        {'id': r['id'], 'ts': r['timestamp'].isoformat(), 'temp': str(r['temperature'])}
        for r in readings_data
    ], sort_keys=True)
    seal_input += f"|incident:{incident.id}|box:{box.box_id if box else 'none'}"
    seal_input += f"|start:{incident.breach_start.isoformat()}|max:{incident.max_temperature}"
    digital_seal = hashlib.sha256(seal_input.encode('utf-8')).hexdigest()

    # Delivery info
    delivery = incident.consolidated_delivery
    driver_name = ''
    company_name = ''
    if delivery:
        driver_name = delivery.driver.get_full_name() if delivery.driver else ''
        company_name = delivery.hub_company.name if delivery.hub_company else ''

    context = {
        'incident': incident,
        'box': box,
        'readings': readings_data,
        'digital_seal': digital_seal,
        'driver_name': driver_name,
        'company_name': company_name or (box.owner_company.name if box else ''),
        'generated_at': timezone.now(),
        'total_readings': len(readings_data),
    }

    return render(request, 'delivery/haccp_forensic_report.html', context)
