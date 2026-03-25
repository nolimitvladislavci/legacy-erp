from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
from core.company_utils import get_user_company
from .models import TravelOrder, TravelExpense


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
        messages.success(request, "Trosak dodan.")
    return redirect("worktime:travel_order_detail", pk=pk)
