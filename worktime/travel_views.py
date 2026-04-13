from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from core.company_utils import get_user_company

from .models import TravelExpense, TravelOrder


@login_required
def travel_order_list(request):
    company = get_user_company(request)
    qs = TravelOrder.objects.filter(company=company)
    status_filter = request.GET.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, "worktime/travel_order_list.html", {
        "orders": qs, "current_status": status_filter,
        "statuses": TravelOrder.STATUS_CHOICES})


@login_required
def travel_order_create(request):
    company = get_user_company(request)
    if request.method == "POST":
        order = TravelOrder(company=company, employee=request.user)
        order.order_number = TravelOrder.next_order_number(company)
        order.destination = request.POST.get("destination", "")
        order.purpose = request.POST.get("purpose", "")
        order.departure_date = request.POST.get("departure_date")
        order.return_date = request.POST.get("return_date")
        order.transport_type = request.POST.get("transport_type", "car_personal")
        order.distance_km = Decimal(request.POST.get("distance_km", "0") or "0")
        order.per_diem_rate = Decimal(request.POST.get("per_diem_rate", "26.55") or "26.55")
        order.per_diem_days = Decimal(request.POST.get("per_diem_days", "0") or "0")
        order.mileage_rate = Decimal(request.POST.get("mileage_rate", "0.40") or "0.40")
        order.other_costs = Decimal(request.POST.get("other_costs", "0") or "0")
        order.notes = request.POST.get("notes", "")
        employee_id = request.POST.get("employee")
        if employee_id:
            from django.contrib.auth.models import User
            order.employee = User.objects.get(id=employee_id)
        order.save()
        messages.success(request, f"Putni nalog {order.order_number} kreiran.")
        return redirect("worktime:travel_order_detail", pk=order.pk)
    from django.contrib.auth.models import User
    employees = User.objects.filter(is_active=True).order_by("last_name")
    return render(request, "worktime/travel_order_form.html", {
        "employees": employees, "transport_types": TravelOrder.TRANSPORT_CHOICES})


@login_required
def travel_order_detail(request, pk):
    company = get_user_company(request)
    order = get_object_or_404(TravelOrder, pk=pk, company=company)
    can_approve = request.user.is_staff or (hasattr(request.user, "employeeprofile") and request.user.employeeprofile.is_manager)
    expenses = order.expenses.all()
    expenses_total = sum(e.amount for e in expenses)
    return render(request, "worktime/travel_order_detail.html", {
        "order": order, "can_approve": can_approve,
        "expenses": expenses, "expenses_total": expenses_total,
        "expense_types": TravelExpense.EXPENSE_TYPES,
    })


@login_required
def travel_order_approve(request, pk):
    if request.method != "POST":
        return redirect("worktime:travel_order_detail", pk=pk)
    company = get_user_company(request)
    order = get_object_or_404(TravelOrder, pk=pk, company=company)
    action = request.POST.get("action", "approve")
    if action == "approve" and order.status == "draft":
        order.status = "approved"
        order.approved_by = request.user
        order.approved_at = timezone.now()
        order.save()
        messages.success(request, f"Putni nalog {order.order_number} odobren.")
    elif action == "complete" and order.status == "approved":
        order.status = "completed"
        order.save()
        messages.success(request, f"Putni nalog {order.order_number} zavrsen.")
    elif action == "cancel":
        order.status = "cancelled"
        order.save()
        messages.warning(request, f"Putni nalog {order.order_number} otkazan.")
    return redirect("worktime:travel_order_detail", pk=pk)


@login_required
def travel_expense_add(request, pk):
    """Dodaj pojedinacni trosak na putni nalog."""
    company = get_user_company(request)
    order = get_object_or_404(TravelOrder, pk=pk, company=company)
    if request.method == "POST" and order.status != "cancelled":
        TravelExpense.objects.create(
            travel_order=order,
            expense_type=request.POST.get("expense_type", "other"),
            description=request.POST.get("description", ""),
            amount=Decimal(request.POST.get("amount", "0")),
            receipt_file=request.FILES.get("receipt_file"),
            receipt_date=request.POST.get("receipt_date") or None,
            notes=request.POST.get("notes", ""),
        )
        messages.success(request, _("Trosak dodan."))
    return redirect("worktime:travel_order_detail", pk=pk)


@login_required
def travel_order_pdf(request, pk):
    """Generira print-ready HTML za putni nalog (A4 za ispis/PDF)."""
    from django.http import HttpResponse
    company = get_user_company(request)
    order = get_object_or_404(TravelOrder, pk=pk, company=company)
    expenses = order.expenses.all()
    expenses_total = sum(e.amount for e in expenses)

    html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Putni nalog %s</title>
<style>
body{font-family:Arial,sans-serif;margin:30px;font-size:12px;color:#000}
h1{font-size:18px;text-align:center;margin-bottom:5px}
.header{text-align:center;margin-bottom:20px;border-bottom:2px solid #000;padding-bottom:10px}
.header .firma{font-weight:bold;font-size:14px}
.header .oib{color:#555;font-size:11px}
table{width:100%%;border-collapse:collapse;margin:10px 0}
th,td{padding:5px 8px;text-align:left;border:1px solid #ccc;font-size:11px}
th{background:#f0f0f0;font-weight:bold}
.total-row td{font-weight:bold;background:#f9f9f0}
.signatures{margin-top:50px;display:flex;justify-content:space-between}
.sig-box{text-align:center;width:28%%}
.sig-line{border-top:1px solid #000;margin-top:40px;padding-top:4px;font-size:10px}
.footer{text-align:center;margin-top:30px;font-size:9px;color:#999}
@media print{body{margin:15mm}}
</style></head><body>
<div class="header">
<div class="firma">%s</div>
<div class="oib">OIB: %s | %s, %s %s</div>
</div>
<h1>PUTNI NALOG br. %s</h1>
<p style="text-align:center;color:#555">Status: %s</p>
<table>
<tr><th width="30%%">Zaposlenik</th><td>%s</td></tr>
<tr><th>Odrediste</th><td>%s</td></tr>
<tr><th>Svrha</th><td>%s</td></tr>
<tr><th>Polazak</th><td>%s</td></tr>
<tr><th>Povratak</th><td>%s</td></tr>
<tr><th>Prijevoz</th><td>%s</td></tr>
</table>
<h3 style="margin-top:15px">Troskovi</h3>
<table>
<tr><th>Stavka</th><th style="text-align:right">Iznos (EUR)</th></tr>
<tr><td>Kilometrina (%s km x %s EUR/km)</td><td style="text-align:right">%s</td></tr>
<tr><td>Dnevnice (%s dana x %s EUR/dan)</td><td style="text-align:right">%s</td></tr>
<tr><td>Ostali troskovi</td><td style="text-align:right">%s</td></tr>""" % (
        order.order_number,
        company.name, company.oib or '-',
        company.address or '', company.zip_code or '', company.city or '',
        order.order_number, order.get_status_display(),
        order.employee.get_full_name() if order.employee else '-',
        order.destination, order.purpose or '-',
        order.departure_date.strftime('%d.%m.%Y %H:%M') if order.departure_date else '-',
        order.return_date.strftime('%d.%m.%Y %H:%M') if order.return_date else '-',
        order.get_transport_type_display(),
        order.distance_km, order.mileage_rate, order.mileage_total,
        order.per_diem_days, order.per_diem_rate, order.per_diem_total,
        order.other_costs,
    )

    # Individual expenses
    if expenses:
        for exp in expenses:
            html += '<tr><td>%s: %s</td><td style="text-align:right">%s</td></tr>' % (
                exp.get_expense_type_display(), exp.description, exp.amount)

    grand_total = order.total_cost + expenses_total
    html += """<tr class="total-row"><td><strong>UKUPNO</strong></td><td style="text-align:right"><strong>%s EUR</strong></td></tr>
</table>""" % grand_total

    if order.notes:
        html += '<p><strong>Napomene:</strong> %s</p>' % order.notes

    html += """
<div class="signatures">
<div class="sig-box"><div class="sig-line">Djelatnik</div></div>
<div class="sig-box"><div class="sig-line">Odobrio</div></div>
<div class="sig-box"><div class="sig-line">Blagajnik</div></div>
</div>
<div class="footer">Ispis: %s | LIMIT Connect — limit-connect.com</div>
</body></html>""" % timezone.now().strftime('%d.%m.%Y %H:%M')

    response = HttpResponse(html, content_type='text/html; charset=utf-8')
    response['Content-Disposition'] = 'inline; filename="PN-%s.html"' % order.order_number
    return response
