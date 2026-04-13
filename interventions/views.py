import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import UserProfile

from .models import HitnaIntervencija

# Status → field that gets timestamped when entering that status
STATUS_TIMESTAMPS = {
    'DODIJELJENO': None,
    'NA_PUTU':     'started_at',
    'NA_LOKACIJI': 'arrived_at',
    'RIJESENO':    'resolved_at',
}

KANBAN_ORDER = [
    'NOVO', 'DODIJELJENO', 'NA_PUTU',
    'NA_LOKACIJI', 'RIJESENO', 'ESKALIRANO', 'FAKTURIRANO',
]


def _get_company_workers(company):
    """Return workers for assignment dropdown."""
    try:
        if company:
            user_ids = UserProfile.objects.filter(
                company=company, role='worker'
            ).values_list('user_id', flat=True)
        else:
            user_ids = UserProfile.objects.filter(
                role='worker'
            ).values_list('user_id', flat=True)
        return User.objects.filter(id__in=user_ids, is_active=True).order_by('first_name', 'username')
    except DatabaseError:
        return User.objects.none()


@login_required
def kanban(request):
    """Dispatcher Kanban – shows all interventions grouped by status."""
    all_items = HitnaIntervencija.objects.select_related('assigned_to', 'company').all()

    # Group by status
    grouped = {s: [] for s in KANBAN_ORDER}
    for item in all_items:
        if item.status in grouped:
            grouped[item.status].append(item)

    columns = []
    status_map = dict(HitnaIntervencija.Status.choices)
    for s in KANBAN_ORDER:
        columns.append({
            'status': s,
            'label': status_map.get(s, s),
            'color': HitnaIntervencija.STATUS_COLORS.get(s, '#888'),
            'items': grouped[s],
        })

    # Workers for assign dropdown
    from core.tenant import get_current_company
    company = get_current_company()
    workers = _get_company_workers(company) if company else User.objects.none()

    return render(request, 'interventions/kanban.html', {
        'columns': columns,
        'workers': workers,
        'total': all_items.count(),
        'active': all_items.exclude(status__in=['RIJESENO', 'ESKALIRANO', 'FAKTURIRANO']).count(),
    })


@login_required
def new_intervention(request):
    """Create a new HitnaIntervencija."""
    from core.tenant import get_current_company
    company = get_current_company()
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('interventions:kanban')

    workers = _get_company_workers(company)

    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        category    = request.POST.get('category', 'ostalo')
        address     = request.POST.get('address', '').strip()
        description = request.POST.get('description', '').strip()
        client_name = request.POST.get('client_name', '').strip()
        client_phone= request.POST.get('client_phone', '').strip()
        worker_id   = request.POST.get('assigned_to', '').strip()

        if not all([title, address, client_name, client_phone]):
            messages.error(request, _('Naslov, adresa, ime i telefon klijenta su obavezni.'))
        else:
            interv = HitnaIntervencija.objects.create(
                company=company,
                title=title,
                category=category,
                address=address,
                description=description,
                client_name=client_name,
                client_phone=client_phone,
            )
            if worker_id:
                try:
                    worker = User.objects.get(pk=worker_id)
                    interv.assign_worker(worker, ttl_minutes=3)
                    # WhatsApp notification
                    try:
                        from core.whatsapp_tasks import send_intervention_assignment_whatsapp
                        send_intervention_assignment_whatsapp.delay(interv.pk, worker.pk)
                    except ImportError:
                        pass
                except User.DoesNotExist:
                    pass

            messages.success(request, f'Intervencija "{title}" kreirana.')
            return redirect('interventions:kanban')

    return render(request, 'interventions/new.html', {
        'workers': workers,
        'categories': HitnaIntervencija.Category.choices,
    })


@login_required
def field_view(request, pk):
    """Mobile-first field worker view."""
    interv = get_object_or_404(HitnaIntervencija, pk=pk)
    return render(request, 'interventions/field.html', {'interv': interv})


@login_required
@require_POST
def update_status(request, pk):
    """AJAX: update intervention status (FSM validated, transaction-locked)."""
    try:
        data = json.loads(request.body)
        new_status = data.get('status', '').upper()
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if new_status not in HitnaIntervencija.Status.values:
        return JsonResponse({'error': 'Nevazeci status'}, status=400)

    try:
        with transaction.atomic():
            interv = HitnaIntervencija.objects.select_for_update().get(pk=pk)

            # FSM validated transition
            try:
                interv.transition_to(new_status, user=request.user, save=False)
            except ValueError as e:
                return JsonResponse({'ok': False, 'error': str(e)}, status=400)

            # Set timestamp for this status
            ts_field = STATUS_TIMESTAMPS.get(new_status)
            if ts_field:
                setattr(interv, ts_field, timezone.now())

            # If assigning, set assigned fields
            if new_status == 'DODIJELJENO' and not interv.assigned_to:
                interv.assigned_to = request.user
                interv.assigned_at = timezone.now()
                interv.ttl_expires_at = timezone.now() + timedelta(minutes=3)

            super(type(interv), interv).save()

        status_label = dict(HitnaIntervencija.Status.choices).get(new_status, new_status)
        return JsonResponse({
            'ok': True,
            'status': new_status,
            'status_label': status_label,
            'message': f'Status azuriran: {status_label}',
        })
    except HitnaIntervencija.DoesNotExist:
        return JsonResponse({'error': 'Intervencija nije pronadena'}, status=404)
    except (IntegrityError, DatabaseError) as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def assign_worker(request, pk):
    """AJAX: assign a worker to an intervention."""
    try:
        data = json.loads(request.body)
        worker_id = data.get('worker_id')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    interv = get_object_or_404(HitnaIntervencija, pk=pk)
    try:
        worker = User.objects.get(pk=worker_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Korisnik nije pronaden'}, status=404)

    interv.assign_worker(worker, ttl_minutes=3)
    # Push notifikacija radniku
    try:
        from push_notifications.push import send_push_to_user
        push_url = f'/interventions/{interv.pk}/field/'
        send_push_to_user(
            worker,
            title='Nova hitna intervencija',
            body=f'{interv.title} – {interv.address or interv.client_name}',
            url=push_url,
        )
    except ImportError as _push_err:
        import logging
        logging.getLogger(__name__).warning(f'Push assign_worker: {_push_err}')
    # In-app notification
    try:
        from notifications.services import notify
        notify(
            recipient=worker,
            notification_type='intervention_assigned',
            title='Nova hitna intervencija',
            message=f'{interv.title} - {interv.address or interv.client_name}',
            url=f'/interventions/{interv.pk}/field/',
            sender=request.user,
        )
    except ImportError:
        pass
    # WhatsApp notification
    try:
        from core.whatsapp_tasks import send_intervention_assignment_whatsapp
        send_intervention_assignment_whatsapp.delay(interv.pk, worker.pk)
    except ImportError:
        pass
    return JsonResponse({
        'ok': True,
        'worker_name': worker.get_full_name() or worker.username,
        'message': f'Dodijeljeno: {worker.get_full_name() or worker.username}',
    })


@login_required
@require_POST
def escalate(request, pk):
    """Escalate intervention to Burza kanban (creates ProjectLead)."""
    interv = get_object_or_404(HitnaIntervencija, pk=pk)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    try:
        from burza.models import ProjectLead
        lead = ProjectLead.objects.create(
            company=interv.company,
            title=data.get('title', f'Eskalacija: {interv.title}'),
            description=data.get('description', interv.description or ''),
            category='ostalo',
            location=interv.address,
            contact_name=interv.client_name,
            contact_phone=interv.client_phone,
            status='NOVI_UPIT',
            internal_notes=f'Eskalirano s hitne intervencije #{interv.pk} | {interv.get_category_display()}',
            created_by=request.user,
        )
        # FSM validated escalation
        try:
            interv.transition_to('ESKALIRANO', user=request.user, save=True)
        except ValueError as e:
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
        interv.project_lead = lead
        super(type(interv), interv).save(update_fields=['project_lead'])
        return JsonResponse({
            'ok': True,
            'lead_id': lead.pk,
            'message': f'Eskalirano u Zlatni Kanban. Upit #{lead.pk} kreiran.',
        })
    except (ValueError, TypeError) as e:
        return JsonResponse({'error': str(e)}, status=500)



@login_required
@require_POST
def gps_update(request, pk):
    """Terenska karta salje GPS koordinate."""
    import json

    from django.utils import timezone
    iv = get_object_or_404(HitnaIntervencija, pk=pk)
    if iv.assigned_to != request.user and not request.user.profile.is_superadmin:
        return JsonResponse({'error': 'Nije vasa intervencija.'}, status=403)
    try:
        data = json.loads(request.body)
        lat  = float(data['lat'])
        lng  = float(data['lng'])
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Neispravan format.'}, status=400)
    iv.last_lat        = lat
    iv.last_lng        = lng
    iv.last_gps_update = timezone.now()
    iv.save(update_fields=['last_lat', 'last_lng', 'last_gps_update'])
    return JsonResponse({'ok': True})

def tracking_view(request, tracking_token):
    """Public client tracking page – no login required."""
    interv = get_object_or_404(HitnaIntervencija, tracking_token=tracking_token)

    steps = [
        ('NOVO', 'Zaprimljeno'),
        ('DODIJELJENO', 'Dodjeljeno'),
        ('NA_PUTU', 'Na putu'),
        ('NA_LOKACIJI', 'Na lokaciji'),
        ('RIJESENO', 'Riješeno'),
    ]
    status_order = [s[0] for s in steps]
    cur_idx = status_order.index(interv.status) if interv.status in status_order else -1
    step_data = []
    for i, (s, lbl) in enumerate(steps):
        if i < cur_idx:
            cls = 'done'
        elif i == cur_idx:
            cls = 'active done' if interv.status == 'RIJESENO' else 'active'
        else:
            cls = ''
        step_data.append({'status': s, 'label': lbl, 'done': i <= cur_idx, 'cls': cls})

    return render(request, 'interventions/tracking.html', {'interv': interv, 'step_data': step_data})


# CSRF exempt: public booking endpoint — uses BookingSignature
@csrf_exempt
def public_intervention(request):
    """Public (no login) form to submit a new Hitna Intervencija."""
    from companies.models import Company

    categories = HitnaIntervencija.Category.choices

    if request.method == 'POST':
        client_name  = request.POST.get('client_name', '').strip()
        client_phone = request.POST.get('client_phone', '').strip()
        address      = request.POST.get('address', '').strip()
        category     = request.POST.get('category', 'ostalo')
        title        = request.POST.get('title', '').strip() or 'Hitna intervencija'
        description  = request.POST.get('description', '').strip()

        if not all([client_name, client_phone, address]):
            return render(request, 'interventions/public_form.html', {
                'categories': categories,
                'error': 'Ime, telefon i adresa su obavezni.',
                'post': request.POST,
            })

        from core.tenant import get_current_company
        company = get_current_company()
        if not company:
            company = Company.objects.first()

        if not company:
            return render(request, 'interventions/public_form.html', {
                'categories': categories,
                'error': 'Sustav nije konfiguriran. Molimo nazovite nas.',
                'post': request.POST,
            })

        interv = HitnaIntervencija.objects.create(
            company=company,
            title=title,
            category=category,
            address=address,
            description=description,
            client_name=client_name,
            client_phone=client_phone,
            status=HitnaIntervencija.Status.NOVO,
        )

        return redirect(f'/track/{interv.tracking_token}/')

    return render(request, 'interventions/public_form.html', {
        'categories': categories,
    })
