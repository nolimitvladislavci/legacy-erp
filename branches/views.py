"""Branch dashboard views for LIMIT Connect pod-firme."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render


def _branch_ctx(request):
    """Return common branch context, or redirect if no branch."""
    branch = getattr(request, 'current_branch', None)
    if not branch:
        # Company admins without branch see all – also allow access
        branch = None
    return branch


def _today_pos_revenue(branch):
    """Sum of today's paid receipts for terminals in this branch."""
    try:
        from pos.models import POSReceipt
        qs = POSReceipt.objects.filter(
            status='paid',
            paid_at__date=date.today(),
        )
        if branch:
            qs = qs.filter(session__terminal__branch=branch)
        return qs.aggregate(t=Sum('total'))['t'] or Decimal('0')
    except (ValueError, TypeError):
        return Decimal('0')


def _today_appointments(branch):
    """Count of today's appointments."""
    try:
        from appointments.models import Appointment
        qs = Appointment.objects.filter(start_time__date=date.today())
        return qs.count()
    except DatabaseError:
        return 0


def _open_receipts_count(branch):
    try:
        from pos.models import POSReceipt
        qs = POSReceipt.objects.filter(status='open')
        if branch:
            qs = qs.filter(session__terminal__branch=branch)
        return qs.count()
    except DatabaseError:
        return 0


def _inventory_low_stock(branch):
    try:
        from inventory.models import InventoryItem
        return InventoryItem.objects.filter(
            is_active=True,
            quantity__lte=models_F('min_quantity'),
        ).count()
    except DatabaseError:
        return 0


def _month_invoice_count():
    try:
        from invoicing.models import Invoice
        now = date.today()
        return Invoice.objects.filter(
            issue_date__year=now.year,
            issue_date__month=now.month,
        ).count()
    except DatabaseError:
        return 0


def _pending_invoices():
    try:
        from invoicing.models import Invoice
        return Invoice.objects.filter(status__in=['sent', 'overdue']).count()
    except DatabaseError:
        return 0


@login_required
def optika_dashboard(request):
    branch   = _branch_ctx(request)
    today    = date.today()
    ctx = {
        'branch':             branch,
        'page_title':         f'Optika – {branch.name}' if branch else 'Optika',
        'today_appts':        _today_appointments(branch),
        'pos_revenue_today':  _today_pos_revenue(branch),
        'open_receipts':      _open_receipts_count(branch),
        'week_appts':         _appts_week(),
        'recent_appts':       _recent_appts(5),
        'dashboard_type':     'optika',
    }
    return render(request, 'branches/optika.html', ctx)


@login_required
def fitness_dashboard(request):
    branch = _branch_ctx(request)
    ctx = {
        'branch':            branch,
        'page_title':        f'Fitness – {branch.name}' if branch else 'Fitness',
        'today_appts':       _today_appointments(branch),
        'pos_revenue_today': _today_pos_revenue(branch),
        'open_receipts':     _open_receipts_count(branch),
        'week_appts':        _appts_week(),
        'recent_appts':      _recent_appts(5),
        'dashboard_type':    'fitness',
    }
    return render(request, 'branches/fitness.html', ctx)


@login_required
def retail_dashboard(request):
    branch = _branch_ctx(request)
    ctx = {
        'branch':            branch,
        'page_title':        f'Trgovina – {branch.name}' if branch else 'Trgovina',
        'pos_revenue_today': _today_pos_revenue(branch),
        'open_receipts':     _open_receipts_count(branch),
        'dashboard_type':    'retail',
    }
    return render(request, 'branches/retail.html', ctx)


@login_required
def accounting_dashboard(request):
    branch = _branch_ctx(request)
    ctx = {
        'branch':         branch,
        'page_title':     f'Knjigovodstvo – {branch.name}' if branch else 'Knjigovodstvo',
        'invoice_count':  _month_invoice_count(),
        'pending_inv':    _pending_invoices(),
        'dashboard_type': 'accounting',
    }
    return render(request, 'branches/accounting.html', ctx)


@login_required
def restaurant_dashboard(request):
    branch = _branch_ctx(request)
    ctx = {
        'branch':            branch,
        'page_title':        f'Restoran – {branch.name}' if branch else 'Restoran',
        'pos_revenue_today': _today_pos_revenue(branch),
        'open_receipts':     _open_receipts_count(branch),
        'dashboard_type':    'restaurant',
    }
    return render(request, 'branches/retail.html', ctx)  # reuse retail template


@login_required
def other_dashboard(request):
    branch = _branch_ctx(request)
    ctx = {
        'branch':        branch,
        'page_title':    branch.name if branch else 'Podružnica',
        'dashboard_type':'other',
    }
    return render(request, 'branches/other.html', ctx)



@login_required
def salon_dashboard(request):
    branch = _branch_ctx(request)
    ctx = {
        'branch':            branch,
        'page_title':        f'Salon – {branch.name}' if branch else 'Salon ljepote',
        'today_appts':       _today_appointments(branch),
        'week_appts':        _appts_week(),
        'recent_appts':      _recent_appts(5),
        'pos_revenue_today': _today_pos_revenue(branch),
        'dashboard_type':    'salon',
    }
    return render(request, 'branches/salon.html', ctx)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _appts_week():
    try:
        from appointments.models import Appointment
        today = date.today()
        return Appointment.objects.filter(
            start_time__date__gte=today,
            start_time__date__lte=today + timedelta(days=7),
        ).count()
    except DatabaseError:
        return 0


def _recent_appts(n=5):
    try:
        from appointments.models import Appointment
        return list(
            Appointment.objects.filter(
                start_time__date__gte=date.today(),
            ).order_by('start_time')[:n]
        )
    except DatabaseError:
        return []
