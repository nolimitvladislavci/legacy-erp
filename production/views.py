"""
production/views.py — MRP / Proizvodni modul views

17 views:
  Dashboard, BOM CRUD, Order lifecycle, Steps, QC, Workstations, PDF, API
"""

import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction, DatabaseError
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.exceptions import ObjectDoesNotExist

from core.company_utils import get_user_company

from .forms import (
    BillOfMaterialsForm,
    ProductionOrderForm,
    QualityCheckForm,
    WorkstationForm,
    get_bomline_formset,
)
from .models import (
    BillOfMaterials,
    BOMLine,
    ProductionLog,
    ProductionOrder,
    ProductionStep,
    QualityCheck,
    Workstation,
)
from .services import calculate_costs, check_availability, consume_materials, produce_output
from .mrp import mrp_run, create_purchase_suggestions, calculate_workstation_load

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════

def _company_or_redirect(request):
    """Return user company or None (caller handles redirect)."""
    return get_user_company(request)


def _next_order_number(company):
    """Generate next order number: RN-YYYYMM-NNN."""
    now = timezone.now()
    prefix = f"RN-{now.strftime('%Y%m')}-"
    last = (
        ProductionOrder.objects
        .filter(company=company, order_number__startswith=prefix)
        .order_by('-order_number')
        .values_list('order_number', flat=True)
        .first()
    )
    if last:
        try:
            seq = int(last.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


# ════════════════════════════════════════════════════════════════
# 1. DASHBOARD
# ════════════════════════════════════════════════════════════════

@login_required
def dashboard(request):
    """Pregled proizvodnje: nalozi po statusu, KPI-evi."""
    company = _company_or_redirect(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('home')

    orders = ProductionOrder.objects.filter(company=company).select_related(
        'bom__output_item', 'workstation'
    )
    today = timezone.now().date()
    today_start = timezone.make_aware(
        timezone.datetime.combine(today, timezone.datetime.min.time())
    )

    # KPIs
    active_orders = orders.filter(status='in_progress').count()

    today_produced = (
        orders.filter(actual_end__gte=today_start, status='done')
        .aggregate(total=Sum('produced_quantity'))['total']
    ) or Decimal('0')

    done_orders = orders.filter(status='done')
    if done_orders.exists():
        total_planned = done_orders.aggregate(s=Sum('planned_quantity'))['s'] or Decimal('1')
        total_produced = done_orders.aggregate(s=Sum('produced_quantity'))['s'] or Decimal('0')
        yield_avg = (total_produced / total_planned * 100).quantize(Decimal('0.1')) if total_planned else Decimal('0')
    else:
        yield_avg = Decimal('0')

    # Workstation utilization (active orders / total active workstations)
    active_ws = Workstation.objects.filter(company=company, status='active').count()
    busy_ws = orders.filter(status='in_progress', workstation__isnull=False).values('workstation').distinct().count()
    ws_utilization = round(busy_ws / active_ws * 100) if active_ws else 0

    # Status columns for kanban-style board
    STATUS_CONFIG = [
        ('draft', 'Nacrt', '#6c757d', 'fas fa-pencil-alt'),
        ('confirmed', 'Potvrđen', '#17a2b8', 'fas fa-check-circle'),
        ('in_progress', 'U tijeku', '#0d6efd', 'fas fa-spinner'),
        ('done', 'Završen', '#28a745', 'fas fa-check'),
    ]
    status_columns = []
    for status_key, label, color, icon in STATUS_CONFIG:
        col_orders = orders.filter(status=status_key).order_by('-priority', '-created_at')[:15]
        status_columns.append({
            'status': status_key,
            'label': label,
            'color': color,
            'icon': icon,
            'orders': col_orders,
        })

    # Recent logs
    recent_logs = (
        ProductionLog.objects
        .filter(order__company=company)
        .select_related('order', 'user')
        .order_by('-created_at')[:15]
    )

    return render(request, 'production/dashboard.html', {
        'status_columns': status_columns,
        'active_orders': active_orders,
        'produced_today': today_produced,
        'yield_avg': yield_avg,
        'ws_utilization': ws_utilization,
        'recent_logs': recent_logs,
        'total_orders': orders.count(),
    })


# ════════════════════════════════════════════════════════════════
# 2-4. BOM (sastavnice)
# ════════════════════════════════════════════════════════════════

@login_required
def bom_list(request):
    """Lista svih sastavnica s pretragom (JS-side filtering)."""
    company = _company_or_redirect(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('home')

    boms = (
        BillOfMaterials.objects
        .filter(company=company)
        .select_related('output_item', 'default_workstation')
        .prefetch_related('lines')
    )

    return render(request, 'production/bom_list.html', {
        'boms': boms,
    })


@login_required
def bom_detail(request, pk):
    """Detalj sastavnice s linijama."""
    company = _company_or_redirect(request)
    bom = get_object_or_404(BillOfMaterials, pk=pk, company=company)
    return render(request, 'production/bom_detail.html', {'bom': bom})


@login_required
def bom_create(request, pk=None):
    """Kreiranje/uređivanje sastavnice s inline formset."""
    company = _company_or_redirect(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('home')

    bom = None
    if pk:
        bom = get_object_or_404(BillOfMaterials, pk=pk, company=company)

    if request.method == 'POST':
        form = BillOfMaterialsForm(request.POST, instance=bom, company=company)
        line_formset = get_bomline_formset(
            company=company,
            data=request.POST,
            instance=bom if bom else None,
            prefix='lines',
        )

        if form.is_valid() and line_formset.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.company = company
                if not bom:
                    obj.created_by = request.user
                obj.save()

                line_formset.instance = obj
                line_formset.save()

            action = "ažurirana" if bom else "kreirana"
            messages.success(request, f"Sastavnica '{obj.name}' {action}.")
            return redirect('production:bom_detail', pk=obj.pk)
    else:
        form = BillOfMaterialsForm(instance=bom, company=company)
        line_formset = get_bomline_formset(
            company=company,
            instance=bom,
            prefix='lines',
        )

    return render(request, 'production/bom_form.html', {
        'form': form,
        'line_formset': line_formset,
    })


# ════════════════════════════════════════════════════════════════
# 5-11. PRODUCTION ORDERS (radni nalozi)
# ════════════════════════════════════════════════════════════════

@login_required
def order_list(request):
    """Lista radnih naloga s filterima."""
    company = _company_or_redirect(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('home')

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    qs = (
        ProductionOrder.objects
        .filter(company=company)
        .select_related('bom__output_item', 'workstation')
    )

    if q:
        qs = qs.filter(
            Q(order_number__icontains=q) |
            Q(bom__name__icontains=q) |
            Q(bom__output_item__name__icontains=q) |
            Q(batch_number__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'production/order_list.html', {
        'orders': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'status_choices': ProductionOrder.STATUS_CHOICES,
    })


@login_required
def order_detail(request, pk):
    """Detalj radnog naloga: koraci, QC, logovi, materijali."""
    company = _company_or_redirect(request)
    order = get_object_or_404(
        ProductionOrder.objects.select_related('bom__output_item', 'workstation', 'created_by'),
        pk=pk, company=company,
    )

    steps = order.steps.select_related('workstation', 'completed_by').all()
    qc_checks = order.quality_checks.select_related('checked_by', 'step').all()
    logs = order.logs.select_related('user').all()[:30]

    # Availability check
    availability, all_available = check_availability(order)

    # QC form for inline creation
    qc_form = QualityCheckForm(order=order)

    return render(request, 'production/order_detail.html', {
        'order': order,
        'steps': steps,
        'qc_checks': qc_checks,
        'logs': logs,
        'availability': availability,
        'all_available': all_available,
        'qc_form': qc_form,
    })


@login_required
def order_create(request, pk=None):
    """Kreiranje ili uređivanje radnog naloga."""
    company = _company_or_redirect(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('home')

    order = None
    if pk:
        order = get_object_or_404(ProductionOrder, pk=pk, company=company)

    if request.method == 'POST':
        form = ProductionOrderForm(request.POST, instance=order, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            if not order:
                obj.order_number = _next_order_number(company)
                obj.created_by = request.user
            obj.save()

            # Auto-create steps for new orders from BOM duration
            if not order and obj.bom.estimated_duration_minutes:
                dur = obj.bom.estimated_duration_minutes
                ProductionStep.objects.bulk_create([
                    ProductionStep(
                        order=obj, step_number=1,
                        name='Priprema materijala',
                        estimated_minutes=max(1, dur // 4),
                        workstation=obj.workstation,
                    ),
                    ProductionStep(
                        order=obj, step_number=2,
                        name='Proizvodnja',
                        estimated_minutes=max(1, dur // 2),
                        workstation=obj.workstation,
                    ),
                    ProductionStep(
                        order=obj, step_number=3,
                        name='Kontrola i pakiranje',
                        estimated_minutes=max(1, dur // 4),
                        workstation=obj.workstation,
                    ),
                ])

            if not order:
                ProductionLog.objects.create(
                    order=obj,
                    action='created',
                    description=f'Radni nalog {obj.order_number} kreiran za {obj.planned_quantity} '
                                f'{obj.bom.output_unit} {obj.bom.output_item.name}',
                    user=request.user,
                )

            action = "ažuriran" if order else "kreiran"
            messages.success(request, f"Radni nalog {obj.order_number} {action}.")
            return redirect('production:order_detail', pk=obj.pk)
    else:
        initial = {}
        if not order:
            initial['order_number'] = _next_order_number(company)
            # Pre-select BOM if passed via GET
            bom_id = request.GET.get('bom')
            if bom_id:
                initial['bom'] = bom_id
        form = ProductionOrderForm(instance=order, company=company, initial=initial)

    return render(request, 'production/order_form.html', {
        'form': form,
    })


@login_required
@require_POST
def order_action(request, pk, action):
    """Unified action handler for order lifecycle: confirm, start, complete, cancel."""
    company = _company_or_redirect(request)
    order = get_object_or_404(ProductionOrder, pk=pk, company=company)

    if action == 'confirm':
        if order.status != 'draft':
            messages.warning(request, _("Nalog nije u nacrtu."))
            return redirect('production:order_detail', pk=pk)
        order.status = 'confirmed'
        order.save(update_fields=['status'])
        messages.success(request, f"Nalog {order.order_number} potvrđen.")

    elif action == 'start':
        if order.status not in ('draft', 'confirmed'):
            messages.warning(request, f"Nalog {order.order_number} nije u statusu za pokretanje.")
            return redirect('production:order_detail', pk=pk)
        # Confirm first if draft
        if order.status == 'draft':
            order.status = 'confirmed'
            order.save(update_fields=['status'])
        try:
            consume_materials(order, user=request.user)
            order.status = 'in_progress'
            order.actual_start = timezone.now()
            order.save(update_fields=['status', 'actual_start'])
            messages.success(request, f"Nalog {order.order_number} pokrenut, materijali utrošeni.")
        except ValueError as e:
            messages.error(request, str(e))

    elif action == 'complete':
        if order.status not in ('in_progress', 'confirmed'):
            messages.warning(request, _("Nalog nije u statusu za završetak."))
            return redirect('production:order_detail', pk=pk)
        calculate_costs(order)
        order.status = 'done'
        order.actual_end = timezone.now()
        order.save(update_fields=['status', 'actual_end'])

        # Auto-knjiženje u konto (glavna knjiga)
        journal_entry = None
        try:
            from production.konto import book_production_order
            journal_entry = book_production_order(order, user=request.user)
        except ImportError as ke:
            logger.warning(f'Konto booking failed for {order.order_number}: {ke}')

        msg = f"Nalog {order.order_number} završen. Ukupni trošak: {order.total_cost:.2f} EUR"
        if journal_entry:
            msg += f" — proknjiženo (temeljnica #{journal_entry.pk})"
        messages.success(request, msg)

    elif action == 'cancel':
        if order.status == 'done':
            messages.warning(request, _("Završen nalog se ne može otkazati."))
            return redirect('production:order_detail', pk=pk)
        reason = request.POST.get('reason', '')
        order.status = 'cancelled'
        order.save(update_fields=['status'])
        ProductionLog.objects.create(
            order=order,
            action='cancelled',
            description=f'Otkazano. Razlog: {reason}' if reason else 'Otkazano.',
            user=request.user,
        )
        messages.success(request, f"Nalog {order.order_number} otkazan.")

    else:
        messages.error(request, f"Nepoznata akcija: {action}")

    return redirect('production:order_detail', pk=pk)


@login_required
@require_POST
def order_produce(request, pk):
    """Evidentiraj proizvedenu količinu."""
    company = _company_or_redirect(request)
    order = get_object_or_404(ProductionOrder, pk=pk, company=company)

    if order.status not in ('confirmed', 'in_progress'):
        messages.warning(request, _("Nalog nije u statusu za evidentiranje proizvodnje."))
        return redirect('production:order_detail', pk=pk)

    qty_str = request.POST.get('quantity', '0')
    scrap_str = request.POST.get('scrap_quantity', '0')

    try:
        qty = Decimal(qty_str)
        scrap = Decimal(scrap_str or '0')
        if qty <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        messages.error(request, _("Nevaljana količina."))
        return redirect('production:order_detail', pk=pk)

    try:
        produce_output(order, qty, user=request.user)
        if scrap > 0:
            order.refresh_from_db()
            order.scrap_quantity += scrap
            order.save(update_fields=['scrap_quantity'])
            ProductionLog.objects.create(
                order=order,
                action='scrap',
                quantity=scrap,
                description=f'Škart: {scrap} {order.bom.output_unit}',
                user=request.user,
            )
        messages.success(request, f"Evidentirano: {qty} {order.bom.output_unit} proizvedeno.")
    except (IntegrityError, DatabaseError) as e:
        messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))

    return redirect('production:order_detail', pk=pk)


# ════════════════════════════════════════════════════════════════
# 12. STEP UPDATE
# ════════════════════════════════════════════════════════════════

@login_required
@require_POST
def step_update(request, pk):
    """Označi korak kao završen ili u tijeku."""
    company = _company_or_redirect(request)
    step = get_object_or_404(
        ProductionStep.objects.select_related('order'),
        pk=pk, order__company=company,
    )

    new_status = request.POST.get('status', 'done')
    actual_minutes = request.POST.get('actual_minutes', '')

    step.status = new_status
    if new_status == 'done':
        step.completed_at = timezone.now()
        step.completed_by = request.user
        if not step.started_at:
            from datetime import timedelta
            step.started_at = step.completed_at - timedelta(minutes=step.estimated_minutes or 1)
    elif new_status == 'in_progress':
        step.started_at = timezone.now()

    if actual_minutes:
        try:
            step.actual_minutes = int(actual_minutes)
        except ValueError:
            pass

    step.save()

    ProductionLog.objects.create(
        order=step.order,
        action='step_done' if new_status == 'done' else 'started',
        description=f'Korak #{step.step_number} "{step.name}" → {step.get_status_display()}',
        user=request.user,
    )

    messages.success(request, f'Korak "{step.name}" ažuriran.')
    return redirect('production:order_detail', pk=step.order_id)


# ════════════════════════════════════════════════════════════════
# 13. QC CREATE
# ════════════════════════════════════════════════════════════════

@login_required
def qc_create(request, order_pk):
    """GET: vrati inline QC formu (HTMX partial). POST: spremi QC zapis."""
    company = _company_or_redirect(request)
    order = get_object_or_404(ProductionOrder, pk=order_pk, company=company)

    if request.method == 'GET':
        form = QualityCheckForm(order=order)
        return render(request, 'production/qc_form_partial.html', {
            'qc_form': form,
            'order': order,
        })

    form = QualityCheckForm(request.POST, order=order)
    if form.is_valid():
        qc = form.save(commit=False)
        qc.order = order
        qc.checked_by = request.user
        qc.save()

        action = 'qc_pass' if qc.result == 'pass' else 'qc_fail'
        ProductionLog.objects.create(
            order=order,
            action=action,
            description=f'QC "{qc.check_name}": {qc.get_result_display()} (stvarno: {qc.actual_value})',
            user=request.user,
        )
        messages.success(request, f'Kontrola kvalitete "{qc.check_name}" zabilježena: {qc.get_result_display()}')
    else:
        messages.error(request, _("Ispravite greške u QC obrascu."))

    return redirect('production:order_detail', pk=order_pk)


# ════════════════════════════════════════════════════════════════
# 14-15. WORKSTATIONS
# ════════════════════════════════════════════════════════════════

@login_required
def workstation_list(request):
    """Lista radnih stanica."""
    company = _company_or_redirect(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('home')

    workstations = Workstation.objects.filter(company=company)
    return render(request, 'production/workstation_list.html', {
        'workstations': workstations,
    })


@login_required
def workstation_create(request, pk=None):
    """Kreiranje/uređivanje radne stanice."""
    company = _company_or_redirect(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('home')

    ws = None
    if pk:
        ws = get_object_or_404(Workstation, pk=pk, company=company)

    if request.method == 'POST':
        form = WorkstationForm(request.POST, instance=ws)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            action = "ažurirana" if ws else "kreirana"
            messages.success(request, f"Radna stanica '{obj.name}' {action}.")
            return redirect('production:workstation_list')
    else:
        form = WorkstationForm(instance=ws)

    return render(request, 'production/workstation_form.html', {
        'form': form,
        'ws': ws,
    })


# ════════════════════════════════════════════════════════════════
# 16. ORDER PDF
# ════════════════════════════════════════════════════════════════

@login_required
def order_pdf(request, pk):
    """Generiraj PDF radnog naloga (WeasyPrint, HTML fallback)."""
    company = _company_or_redirect(request)
    order = get_object_or_404(
        ProductionOrder.objects.select_related('bom__output_item', 'workstation', 'created_by'),
        pk=pk, company=company,
    )

    steps = order.steps.select_related('workstation').all()
    qc_checks = order.quality_checks.all()

    # Build material requirements with extra fields for PDF template
    multiplier = order.planned_quantity / order.bom.output_quantity
    material_requirements = []
    for line in order.bom.lines.select_related('item').all():
        material_requirements.append({
            'item': line.item,
            'base_qty': line.quantity,
            'unit': line.unit,
            'waste': f"{line.waste_percent}%",
            'effective': line.effective_quantity,
            'required': line.effective_quantity * multiplier,
        })

    html_content = render(request, 'production/order_pdf.html', {
        'order': order,
        'steps': steps,
        'qc_checks': qc_checks,
        'material_requirements': material_requirements,
        'company': company,
        'now': timezone.now(),
    }).content

    # Try WeasyPrint, fallback to HTML
    try:
        from weasyprint import HTML
        pdf = HTML(string=html_content.decode('utf-8')).write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="RN_{order.order_number}.pdf"'
        return response
    except ImportError:
        logger.warning("WeasyPrint not installed, returning HTML for print")
        return HttpResponse(html_content, content_type='text/html')


# ════════════════════════════════════════════════════════════════
# 17. API — MATERIAL AVAILABILITY
# ════════════════════════════════════════════════════════════════



# ════════════════════════════════════════════════════════════════
# MRP — Material Requirements Planning
# ════════════════════════════════════════════════════════════════

@login_required
@require_POST
def mrp_run_view(request):
    """Pokreni MRP algoritam za firmu."""
    company = _company_or_redirect(request)
    if not isinstance(company, object) or hasattr(company, 'status_code'):
        return company

    horizon = int(request.POST.get('horizon_days', 30))
    result = mrp_run(company, horizon_days=horizon, user=request.user)
    messages.success(request, result['message'])
    return redirect('production:mrp_dashboard')


@login_required
def mrp_dashboard(request):
    """MRP nadzorna ploča — planirani nalozi, purchase suggestions, kapacitet."""
    company = _company_or_redirect(request)
    if not isinstance(company, object) or hasattr(company, 'status_code'):
        return company

    from .models import MRPPlannedOrder
    planned = MRPPlannedOrder.objects.filter(company=company).select_related('item', 'bom')
    produce_plans = planned.filter(order_type='produce')
    purchase_plans = planned.filter(order_type='purchase')
    purchase_data = create_purchase_suggestions(company)
    capacity = calculate_workstation_load(company)

    return render(request, 'production/mrp_dashboard.html', {
        'produce_plans': produce_plans,
        'purchase_plans': purchase_plans,
        'purchase_data': purchase_data,
        'capacity': capacity,
    })


@login_required
def variance_report(request):
    """Cost variance report — planirano vs stvarno."""
    company = _company_or_redirect(request)
    if not isinstance(company, object) or hasattr(company, 'status_code'):
        return company

    from .models import ProductionOrder
    orders = ProductionOrder.objects.filter(
        company=company, status='done',
        planned_total_cost__gt=0,
    ).order_by('-actual_end')[:50]

    total_planned = sum(o.planned_total_cost for o in orders)
    total_actual = sum(o.total_cost for o in orders)
    total_variance = total_actual - total_planned if total_planned else Decimal('0')

    return render(request, 'production/variance_report.html', {
        'orders': orders,
        'total_planned': total_planned,
        'total_actual': total_actual,
        'total_variance': total_variance,
        'variance_percent': (total_variance / total_planned * 100).quantize(Decimal('0.1')) if total_planned else 0,
    })


@login_required
def stock_movements(request):
    """Pregled kretanja zaliha vezanih uz proizvodnju."""
    company = _company_or_redirect(request)
    if not isinstance(company, object) or hasattr(company, 'status_code'):
        return company

    from inventory.models import StockMovement
    movements = StockMovement.objects.filter(
        item__company=company,
        movement_type__in=('consumption', 'production', 'scrap'),
    ).select_related('item', 'production_order').order_by('-created_at')[:100]

    return render(request, 'production/stock_movements.html', {
        'movements': movements,
    })

@login_required
def api_availability(request):
    """JSON: provjera dostupnosti materijala za BOM."""
    company = _company_or_redirect(request)
    if not company:
        return JsonResponse({'error': 'Nema konteksta tvrtke'}, status=403)

    bom_id = request.GET.get('bom_id')
    quantity = request.GET.get('quantity', '1')

    if not bom_id:
        return JsonResponse({'error': 'bom_id je obavezan'}, status=400)

    try:
        bom = BillOfMaterials.objects.get(pk=bom_id, company=company)
    except BillOfMaterials.DoesNotExist:
        return JsonResponse({'error': 'BOM ne postoji'}, status=404)

    try:
        qty = Decimal(quantity)
    except (InvalidOperation, ValueError):
        return JsonResponse({'error': 'Nevaljana količina'}, status=400)

    # Create a temporary pseudo-order for availability check
    temp_order = ProductionOrder(
        company=company,
        bom=bom,
        planned_quantity=qty,
    )

    result, all_ok = check_availability(temp_order)

    items = []
    for r in result:
        items.append({
            'item_name': r['item_name'],
            'item_sku': r['item_sku'],
            'required': float(r['required']),
            'available': float(r['available']),
            'missing': float(r['missing']),
            'sufficient': r['sufficient'],
            'unit': r['unit'],
        })

    return JsonResponse({
        'bom_name': bom.name,
        'output_item': bom.output_item.name,
        'quantity': float(qty),
        'all_available': all_ok,
        'materials': items,
    })
