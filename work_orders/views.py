import logging
logger = logging.getLogger(__name__)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils.translation import gettext_lazy as _
from django.db import transaction, DatabaseError, IntegrityError

from core.tenant import get_current_company
from .models import WorkOrder, WorkOrderItem, VehicleCard, ClientCard


# ─── Helper ──────────────────────────────────────────────────────────────────

def _get_company(request):
    company = get_current_company()
    if not company:
        try:
            company = request.user.profile.company
        except AttributeError:
            pass
    return company


# ─── Work Order List ──────────────────────────────────────────────────────────

@login_required
def work_order_list(request):
    company = _get_company(request)
    if not company:
        return HttpResponseForbidden("No company.")

    qs = WorkOrder.objects.filter(company=company).select_related('client', 'assigned_to')

    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        qs = qs.filter(priority=priority_filter)

    q = request.GET.get('q', '').strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(order_number__icontains=q) |
            Q(client__name__icontains=q) |
            Q(description__icontains=q)
        )

    context = {
        'work_orders': qs,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'q': q,
        'STATUS_CHOICES': WorkOrder.STATUS_CHOICES,
        'PRIORITY_CHOICES': WorkOrder.PRIORITY_CHOICES,
    }
    return render(request, 'work_orders/work_order_list.html', context)


# ─── Work Order Create ────────────────────────────────────────────────────────

@transaction.atomic
@login_required
def work_order_create(request):
    company = _get_company(request)
    if not company:
        return HttpResponseForbidden("No company.")

    if request.method == 'POST':
        with transaction.atomic():
            wo = WorkOrder(company=company, created_by=request.user)
            wo.order_number = wo.generate_order_number()

            client_id = request.POST.get('client_id') or request.POST.get('client')
            if client_id:
                wo.client_id = int(client_id)

            assigned_id = request.POST.get('assigned_to')
            if assigned_id:
                wo.assigned_to_id = int(assigned_id)

            wo.description = request.POST.get('description', '')
            wo.notes = request.POST.get('notes', '')
            wo.priority = request.POST.get('priority', 'normal')

            # TASK 4b: Validacija statusa na kreiranju (zatvara injekciju linija 90)
            _initial_status = request.POST.get('status', 'draft')
            if _initial_status not in dict(WorkOrder.STATUS_CHOICES):
                _initial_status = 'draft'
            wo.status = _initial_status

            scheduled_date = request.POST.get('scheduled_date')
            if scheduled_date:
                wo.scheduled_date = scheduled_date

            scheduled_time = request.POST.get('scheduled_time')
            if scheduled_time:
                wo.scheduled_time = scheduled_time

            deadline = request.POST.get('deadline')
            if deadline:
                wo.deadline = deadline

            est_hours = request.POST.get('estimated_hours', '0')
            try:
                wo.estimated_hours = float(est_hours)
            except (ValueError, TypeError):
                wo.estimated_hours = 0

            discount = request.POST.get('discount', '0')
            try:
                wo.discount = float(discount)
            except (ValueError, TypeError):
                wo.discount = 0

            wo.save()

            # Save items
            _save_items(wo, request.POST)
            wo.recalculate_totals()

        messages.success(request, f"Radni nalog {wo.order_number} kreiran.")
        return redirect('work_orders:detail', pk=wo.pk)

    from partners.models import Partner
    from django.contrib.auth.models import User
    clients = Partner.objects.filter(company=company, is_active=True).order_by('name')
    employees = User.objects.filter(
        profile__company=company, is_active=True
    ).select_related('profile').order_by('first_name', 'last_name')

    context = {
        'clients': clients,
        'employees': employees,
        'STATUS_CHOICES': WorkOrder.STATUS_CHOICES,
        'PRIORITY_CHOICES': WorkOrder.PRIORITY_CHOICES,
        'work_order': None,
    }
    return render(request, 'work_orders/work_order_form.html', context)


# ─── Work Order Detail ────────────────────────────────────────────────────────

@login_required
def work_order_detail(request, pk):
    company = _get_company(request)
    wo = get_object_or_404(WorkOrder, pk=pk, company=company)
    items = wo.items.select_related('article').all()

    # Card activity timeline (BORG audit trail)
    from borg_ops.models import CardActivity
    from django.contrib.contenttypes.models import ContentType
    card_activities = CardActivity.objects.filter(
        content_type=ContentType.objects.get_for_model(wo),
        object_id=str(wo.pk),
    )[:50]

    context = {
        'wo': wo,
        'items': items,
        'labor_items': items.filter(item_type='labor'),
        'material_items': items.filter(item_type='material'),
        'activities': card_activities,
    }
    return render(request, 'work_orders/work_order_detail.html', context)


# ─── Work Order Edit ──────────────────────────────────────────────────────────

@login_required
def work_order_edit(request, pk):
    company = _get_company(request)
    wo = get_object_or_404(WorkOrder, pk=pk, company=company)

    if wo.status in ('invoiced', 'cancelled'):
        messages.error(request, _("Fakturirani/otkazani nalozi se ne mogu mijenjati."))
        return redirect('work_orders:detail', pk=pk)

    if request.method == 'POST':
        with transaction.atomic():
            client_id = request.POST.get('client_id') or request.POST.get('client')
            if client_id:
                wo.client_id = int(client_id)

            assigned_id = request.POST.get('assigned_to')
            wo.assigned_to_id = int(assigned_id) if assigned_id else None

            wo.description = request.POST.get('description', '')
            wo.notes = request.POST.get('notes', '')
            wo.priority = request.POST.get('priority', 'normal')

            # TASK 4c: FSM validated status change (zatvara injekciju linija 182)
            _new_status = request.POST.get('status', wo.status)
            if _new_status != wo.status:
                try:
                    wo.transition_to(_new_status, user=request.user, save=False)
                except ValueError as e:
                    messages.error(request, str(e))
                    return redirect('work_orders:detail', pk=wo.pk)

            scheduled_date = request.POST.get('scheduled_date')
            wo.scheduled_date = scheduled_date or None

            scheduled_time = request.POST.get('scheduled_time')
            wo.scheduled_time = scheduled_time or None

            deadline = request.POST.get('deadline')
            wo.deadline = deadline or None

            try:
                wo.estimated_hours = float(request.POST.get('estimated_hours', '0'))
            except (ValueError, TypeError):
                wo.estimated_hours = 0

            try:
                wo.discount = float(request.POST.get('discount', '0'))
            except (ValueError, TypeError):
                wo.discount = 0

            wo.save()

            # Rebuild items
            wo.items.all().delete()
            _save_items(wo, request.POST)
            wo.recalculate_totals()

        messages.success(request, _("Radni nalog ažuriran."))
        return redirect('work_orders:detail', pk=pk)

    from partners.models import Partner
    from django.contrib.auth.models import User
    clients = Partner.objects.filter(company=company, is_active=True).order_by('name')
    employees = User.objects.filter(
        profile__company=company, is_active=True
    ).select_related('profile').order_by('first_name', 'last_name')

    context = {
        'work_order': wo,
        'clients': clients,
        'employees': employees,
        'STATUS_CHOICES': WorkOrder.STATUS_CHOICES,
        'PRIORITY_CHOICES': WorkOrder.PRIORITY_CHOICES,
        'items': wo.items.select_related('article').all(),
    }
    return render(request, 'work_orders/work_order_form.html', context)


# ─── Work Order Complete ──────────────────────────────────────────────────────

@transaction.atomic
@login_required
def work_order_complete(request, pk):
    company = _get_company(request)
    wo = get_object_or_404(WorkOrder, pk=pk, company=company)
    if request.method == 'POST':
        wo.complete(user=request.user)
        messages.success(request, f"Nalog {wo.order_number} označen kao završen.")
    return redirect('work_orders:detail', pk=pk)


# ─── Work Order Cancel ────────────────────────────────────────────────────────

@login_required
def work_order_cancel(request, pk):
    company = _get_company(request)
    wo = get_object_or_404(WorkOrder, pk=pk, company=company)
    if request.method == 'POST':
        try:
            wo.transition_to('cancelled', user=request.user)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('work_orders:detail', pk=pk)
        messages.success(request, f"Nalog {wo.order_number} otkazan.")
    return redirect('work_orders:detail', pk=pk)


# ─── Work Order → Invoice ─────────────────────────────────────────────────────

@login_required
def work_order_to_invoice(request, pk):
    """Create invoice from work order and redirect to invoice edit."""
    company = _get_company(request)
    wo = get_object_or_404(WorkOrder, pk=pk, company=company)

    if wo.status == 'invoiced':
        messages.warning(request, _("Nalog je već fakturiran."))
        return redirect('work_orders:detail', pk=pk)

    if request.method == 'POST':
        with transaction.atomic():
            from invoicing.models import Invoice, InvoiceItem
            import datetime

            # Generate invoice number same way as invoicing app
            last = Invoice.objects.order_by('-id').first()
            now = datetime.date.today()
            next_num = f"KNJ-{now.year}-{(last.id + 1 if last else 1):04d}"

            client_name = wo.client.name if wo.client else ''
            client_address = ''
            client_oib = ''
            if wo.client:
                client_address = getattr(wo.client, 'address', '') or ''
                client_oib = getattr(wo.client, 'oib', '') or ''

            invoice = Invoice.objects.create(
                company=company,
                doctype='R',
                number=next_num,
                status='DRAFT',
                date_issued=datetime.datetime.now(),
                date_due=now + datetime.timedelta(days=30),
                client_name=client_name,
                client_address=client_address,
                client_oib=client_oib,
                note=f"Radni nalog {wo.order_number}\n{wo.notes}".strip(),
                created_by=request.user,
            )

            for item in wo.items.select_related('article').all():
                InvoiceItem.objects.create(
                    invoice=invoice,
                    description=item.description,
                    quantity=item.quantity,
                    unit=item.unit,
                    unit_price=item.unit_price,
                    discount_percent=item.discount_percent,
                    tax_rate=item.tax_rate,
                    inventory_item=item.article,
                )

            # Link work order to invoice via FSM transition
            wo.transition_to('invoiced', user=request.user, save=True)
            wo.invoice = invoice
            super(WorkOrder, wo).save(update_fields=['invoice'])

        messages.success(request, f"Račun kreiran iz naloga {wo.order_number}.")
        return redirect('invoicing:invoice_edit', pk=invoice.pk)

    return render(request, 'work_orders/work_order_to_invoice.html', {'wo': wo})


# ─── Vehicle Cards ────────────────────────────────────────────────────────────

@login_required
def vehicle_card_list(request):
    company = _get_company(request)
    if not company:
        return HttpResponseForbidden("No company.")

    qs = VehicleCard.objects.filter(company=company).select_related('client')
    q = request.GET.get('q', '').strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(make__icontains=q) |
            Q(model__icontains=q) |
            Q(registration_plate__icontains=q) |
            Q(client__name__icontains=q) |
            Q(vin__icontains=q)
        )

    context = {'vehicles': qs, 'q': q}
    return render(request, 'work_orders/vehicle_card_list.html', context)


@login_required
def vehicle_card_create(request):
    company = _get_company(request)
    if not company:
        return HttpResponseForbidden("No company.")

    if request.method == 'POST':
        vc = VehicleCard(company=company)
        client_id = request.POST.get('client')
        if client_id:
            vc.client_id = int(client_id)
        vc.make = request.POST.get('make', '')
        vc.model = request.POST.get('model', '')
        year = request.POST.get('year')
        vc.year = int(year) if year else None
        vc.registration_plate = request.POST.get('registration_plate', '')
        vc.vin = request.POST.get('vin', '')
        vc.engine_type = request.POST.get('engine_type', '')
        mileage = request.POST.get('mileage', '0')
        vc.mileage = int(mileage) if mileage else 0
        vc.color = request.POST.get('color', '')
        vc.notes = request.POST.get('notes', '')
        vc.save()
        messages.success(request, f"Karton vozila {vc} kreiran.")
        return redirect('work_orders:vehicle_list')

    from partners.models import Partner
    clients = Partner.objects.filter(company=company, is_active=True).order_by('name')
    return render(request, 'work_orders/vehicle_card_form.html', {'clients': clients, 'vehicle': None})


@login_required
def vehicle_card_detail(request, pk):
    company = _get_company(request)
    vc = get_object_or_404(VehicleCard, pk=pk, company=company)
    work_orders = WorkOrder.objects.filter(
        company=company, client=vc.client
    ).select_related('assigned_to').order_by('-created_at')[:10]
    return render(request, 'work_orders/vehicle_card_detail.html', {
        'vehicle': vc, 'work_orders': work_orders
    })


@login_required
def vehicle_card_edit(request, pk):
    company = _get_company(request)
    vc = get_object_or_404(VehicleCard, pk=pk, company=company)

    if request.method == 'POST':
        client_id = request.POST.get('client')
        if client_id:
            vc.client_id = int(client_id)
        vc.make = request.POST.get('make', '')
        vc.model = request.POST.get('model', '')
        year = request.POST.get('year')
        vc.year = int(year) if year else None
        vc.registration_plate = request.POST.get('registration_plate', '')
        vc.vin = request.POST.get('vin', '')
        vc.engine_type = request.POST.get('engine_type', '')
        mileage = request.POST.get('mileage', '0')
        vc.mileage = int(mileage) if mileage else 0
        vc.color = request.POST.get('color', '')
        vc.notes = request.POST.get('notes', '')
        vc.save()
        messages.success(request, _("Karton vozila ažuriran."))
        return redirect('work_orders:vehicle_detail', pk=pk)

    from partners.models import Partner
    clients = Partner.objects.filter(company=company, is_active=True).order_by('name')
    return render(request, 'work_orders/vehicle_card_form.html', {'clients': clients, 'vehicle': vc})


# ─── Client Cards ─────────────────────────────────────────────────────────────

@login_required
def client_card_list(request):
    company = _get_company(request)
    if not company:
        return HttpResponseForbidden("No company.")

    qs = ClientCard.objects.filter(company=company).select_related('client')
    card_type_filter = request.GET.get('card_type', '')
    if card_type_filter:
        qs = qs.filter(card_type=card_type_filter)

    q = request.GET.get('q', '').strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(client__name__icontains=q))

    context = {
        'client_cards': qs,
        'card_type_filter': card_type_filter,
        'CARD_TYPES': ClientCard.CARD_TYPES,
        'q': q,
    }
    return render(request, 'work_orders/client_card_list.html', context)


@login_required
def client_card_create(request):
    company = _get_company(request)
    if not company:
        return HttpResponseForbidden("No company.")

    if request.method == 'POST':
        cc = ClientCard(company=company)
        client_id = request.POST.get('client')
        if client_id:
            cc.client_id = int(client_id)
        cc.card_type = request.POST.get('card_type', 'general')
        _fill_client_card(cc, request.POST)
        try:
            cc.save()
            messages.success(request, f"Karton klijenta {cc} kreiran.")
            return redirect('work_orders:client_card_list')
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))

    from partners.models import Partner
    clients = Partner.objects.filter(company=company, is_active=True).order_by('name')
    return render(request, 'work_orders/client_card_form.html', {
        'clients': clients, 'card': None, 'CARD_TYPES': ClientCard.CARD_TYPES
    })


@login_required
def client_card_detail(request, pk):
    company = _get_company(request)
    cc = get_object_or_404(ClientCard, pk=pk, company=company)
    return render(request, 'work_orders/client_card_detail.html', {'card': cc})


@login_required
def client_card_edit(request, pk):
    company = _get_company(request)
    cc = get_object_or_404(ClientCard, pk=pk, company=company)

    if request.method == 'POST':
        client_id = request.POST.get('client')
        if client_id:
            cc.client_id = int(client_id)
        cc.card_type = request.POST.get('card_type', cc.card_type)
        _fill_client_card(cc, request.POST)
        cc.save()
        messages.success(request, _("Karton klijenta ažuriran."))
        return redirect('work_orders:client_card_detail', pk=pk)

    from partners.models import Partner
    clients = Partner.objects.filter(company=company, is_active=True).order_by('name')
    return render(request, 'work_orders/client_card_form.html', {
        'clients': clients, 'card': cc, 'CARD_TYPES': ClientCard.CARD_TYPES
    })


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _save_items(wo, post):
    """Parse POST arrays and create WorkOrderItems."""
    item_types = post.getlist('item_type[]')
    descriptions = post.getlist('item_description[]')
    quantities = post.getlist('item_quantity[]')
    units = post.getlist('item_unit[]')
    prices = post.getlist('item_price[]')
    discounts = post.getlist('item_discount[]')
    tax_rates = post.getlist('item_tax_rate[]')
    article_ids = post.getlist('item_article_id[]')

    for i, desc in enumerate(descriptions):
        if not desc.strip():
            continue
        try:
            qty = float(quantities[i]) if i < len(quantities) else 1
            price = float(prices[i]) if i < len(prices) else 0
            disc = float(discounts[i]) if i < len(discounts) else 0
            tax = float(tax_rates[i]) if i < len(tax_rates) else 25
            itype = item_types[i] if i < len(item_types) else 'labor'
            unit = units[i] if i < len(units) else 'sat'
            art_id = article_ids[i] if i < len(article_ids) else ''
        except (ValueError, TypeError):
            continue

        item = WorkOrderItem(
            work_order=wo,
            item_type=itype,
            description=desc.strip(),
            quantity=qty,
            unit=unit,
            unit_price=price,
            discount_percent=disc,
            tax_rate=tax,
        )
        if art_id:
            try:
                item.article_id = int(art_id)
            except (ValueError, TypeError):
                pass
        item.save()


def _fill_client_card(cc, post):
    """Fill ClientCard fields from POST data."""
    def _dec(key):
        v = post.get(key, '').strip()
        from decimal import Decimal, InvalidOperation
        try:
            return Decimal(v) if v else None
        except InvalidOperation:
            return None

    def _int(key):
        v = post.get(key, '').strip()
        try:
            return int(v) if v else None
        except (ValueError, TypeError):
            return None

    # Optics
    cc.sphere_right = _dec('sphere_right')
    cc.cylinder_right = _dec('cylinder_right')
    cc.axis_right = _int('axis_right')
    cc.sphere_left = _dec('sphere_left')
    cc.cylinder_left = _dec('cylinder_left')
    cc.axis_left = _int('axis_left')
    cc.pd = _dec('pd')
    cc.add_power = _dec('add_power')
    # Hair
    cc.hair_type = post.get('hair_type', '')
    cc.allergies = post.get('allergies', '')
    # General
    cc.gdpr_consent = 'gdpr_consent' in post
    last_visit = post.get('last_visit', '').strip()
    cc.last_visit = last_visit or None
    cc.notes = post.get('notes', '')


# ─── Work Order Kanban Board (BORG Faza 2) ───────────────────────────────────

@login_required
def work_order_board(request):
    """Kanban board for work orders — 5 columns by status.
    
    Dron #2 fix: Prefetch StatusTimestamp da se izbjegne N+1.
    Jedan SQL za sve kartice + jedan Prefetch za SLA timestamps.
    Total: 2 SQL umjesto 1 + N*2.
    """
    from django.db.models import Prefetch
    from borg_ops.models import StatusTimestamp
    from django.contrib.contenttypes.models import ContentType

    company = _get_company(request)
    if not company:
        return HttpResponseForbidden("No company.")

    # ContentType za WorkOrder — jedan lookup, cached
    ct = ContentType.objects.get_for_model(WorkOrder)

    # Prefetch samo otvorene SLA timestamps (exited_at IS NULL)
    sla_prefetch = Prefetch(
        'sla_timestamps',
        queryset=StatusTimestamp.objects.filter(exited_at__isnull=True),
        to_attr='_sla_open',
    )

    qs = (WorkOrder.objects
          .filter(company=company)
          .select_related('client', 'assigned_to')
          .prefetch_related(sla_prefetch))

    ACTIVE = ['draft', 'in_progress', 'completed', 'invoiced', 'cancelled']
    all_cards = list(qs.filter(status__in=ACTIVE).order_by('-created_at')[:150])

    # Grupiraj u memoriji — nema extra SQL-a
    by_status = {}
    for card in all_cards:
        by_status.setdefault(card.status, []).append(card)

    columns = [
        {'id': 'draft',       'label': 'Nacrt',      'icon': '📝', 'color': '#64748b',
         'items': by_status.get('draft', [])[:30]},
        {'id': 'in_progress', 'label': 'U tijeku',   'icon': '🔧', 'color': '#3b82f6',
         'items': by_status.get('in_progress', [])[:30]},
        {'id': 'completed',   'label': 'Završen',    'icon': '✅', 'color': '#22c55e',
         'items': by_status.get('completed', [])[:30]},
        {'id': 'invoiced',    'label': 'Fakturiran', 'icon': '📄', 'color': '#c9a84c',
         'items': by_status.get('invoiced', [])[:30]},
        {'id': 'cancelled',   'label': 'Otkazan',    'icon': '❌', 'color': '#ef4444',
         'items': by_status.get('cancelled', [])[:30]},
    ]

    return render(request, 'work_orders/board.html', {
        'columns': columns,
        'STATUS_CHOICES': WorkOrder.STATUS_CHOICES,
    })
