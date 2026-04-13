"""
Reports views — Revenue, Worktime summaries with CSV/Excel export.
"""
import csv
import io
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import render


def _parse_dates(request):
    """Get date_from / date_to from GET params, default to current month."""
    today = date.today()
    first = today.replace(day=1)
    try:
        df = date.fromisoformat(request.GET.get('date_from', ''))
    except (ValueError, TypeError):
        df = first
    try:
        dt = date.fromisoformat(request.GET.get('date_to', ''))
    except (ValueError, TypeError):
        dt = today
    return df, dt


# ── DASHBOARD ──────────────────────────────────────────────────
@login_required
def reports_dashboard(request):
    date_from, date_to = _parse_dates(request)
    from invoicing.models import Invoice
    from worktime.models import TimeEntry

    inv_qs = Invoice.objects.filter(date_issued__date__gte=date_from, date_issued__date__lte=date_to)
    revenue = inv_qs.filter(status='PAID').aggregate(s=Sum('total'))['s'] or Decimal('0')
    inv_count = inv_qs.count()

    te_qs = TimeEntry.objects.filter(date__gte=date_from, date__lte=date_to)
    total_hours = te_qs.aggregate(s=Sum('duration'))['s'] or Decimal('0')

    return render(request, 'reports/dashboard.html', {
        'title': 'Izvještaji',
        'date_from': date_from,
        'date_to': date_to,
        'revenue': revenue,
        'inv_count': inv_count,
        'total_hours': total_hours,
        'te_count': te_qs.count(),
    })


# ── REVENUE REPORT ────────────────────────────────────────────
@login_required
def revenue_report(request):
    date_from, date_to = _parse_dates(request)
    from invoicing.models import Invoice

    qs = Invoice.objects.filter(
        date_issued__date__gte=date_from,
        date_issued__date__lte=date_to,
        status='PAID',
    ).order_by('date_issued')

    daily = {}
    for inv in qs:
        d = inv.date_issued.date().isoformat()
        daily.setdefault(d, Decimal('0'))
        daily[d] += inv.total

    labels = sorted(daily.keys())
    values = [float(daily[l]) for l in labels]
    total = sum(values)

    return render(request, 'reports/revenue.html', {
        'title': 'Prihod',
        'date_from': date_from,
        'date_to': date_to,
        'labels': labels,
        'values': values,
        'total': total,
        'invoices': qs,
    })


# ── WORKTIME REPORT ───────────────────────────────────────────
@login_required
def worktime_report(request):
    date_from, date_to = _parse_dates(request)
    from worktime.models import TimeEntry

    qs = TimeEntry.objects.filter(date__gte=date_from, date__lte=date_to)

    by_user = (
        qs.values('user__username', 'user__first_name', 'user__last_name')
        .annotate(total_hours=Sum('duration'), entries=Count('id'))
        .order_by('-total_hours')
    )
    by_project = (
        qs.values('project__code', 'project__name')
        .annotate(total_hours=Sum('duration'), entries=Count('id'))
        .order_by('-total_hours')
    )
    total_hours = qs.aggregate(s=Sum('duration'))['s'] or 0

    return render(request, 'reports/worktime.html', {
        'title': 'Radno vrijeme',
        'date_from': date_from,
        'date_to': date_to,
        'by_user': by_user,
        'by_project': by_project,
        'total_hours': total_hours,
    })


# ── CSV EXPORTS ───────────────────────────────────────────────
@login_required
def export_revenue_csv(request):
    date_from, date_to = _parse_dates(request)
    from invoicing.models import Invoice

    qs = Invoice.objects.filter(
        date_issued__date__gte=date_from,
        date_issued__date__lte=date_to,
        status='PAID',
    ).order_by('date_issued')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="revenue_{date_from}_{date_to}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Broj', 'Datum', 'Klijent', 'Iznos', 'Valuta'])
    for inv in qs:
        writer.writerow([inv.number, inv.date_issued.strftime('%Y-%m-%d'), inv.client_name, inv.total, inv.currency])
    return response


@login_required
def export_worktime_csv(request):
    date_from, date_to = _parse_dates(request)
    from worktime.models import TimeEntry

    qs = TimeEntry.objects.filter(
        date__gte=date_from, date__lte=date_to
    ).select_related('user', 'project').order_by('date')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="worktime_{date_from}_{date_to}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Datum', 'Korisnik', 'Projekt', 'Sati', 'Zadatak', 'Status'])
    for te in qs:
        writer.writerow([te.date, te.user.get_full_name() or te.user.username, te.project.code, te.duration, te.get_task_type_display(), te.status])
    return response


# ── EXCEL EXPORTS ─────────────────────────────────────────────
@login_required
def export_revenue_excel(request):
    date_from, date_to = _parse_dates(request)
    from invoicing.models import Invoice

    qs = Invoice.objects.filter(
        date_issued__date__gte=date_from,
        date_issued__date__lte=date_to,
        status='PAID',
    ).order_by('date_issued')

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'Prihod'
    ws.append(['Broj', 'Datum', 'Klijent', 'Iznos', 'Valuta'])
    for inv in qs:
        ws.append([inv.number, inv.date_issued.strftime('%Y-%m-%d'), inv.client_name, float(inv.total), inv.currency])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(buf.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="revenue_{date_from}_{date_to}.xlsx"'
    return response


@login_required
def export_worktime_excel(request):
    date_from, date_to = _parse_dates(request)
    from worktime.models import TimeEntry

    qs = TimeEntry.objects.filter(
        date__gte=date_from, date__lte=date_to
    ).select_related('user', 'project').order_by('date')

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'Radno vrijeme'
    ws.append(['Datum', 'Korisnik', 'Projekt', 'Sati', 'Zadatak', 'Status'])
    for te in qs:
        ws.append([te.date.isoformat(), te.user.get_full_name() or te.user.username, te.project.code, float(te.duration), te.get_task_type_display(), te.status])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(buf.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="worktime_{date_from}_{date_to}.xlsx"'
    return response
