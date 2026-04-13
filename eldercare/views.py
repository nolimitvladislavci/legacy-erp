"""Eldercare Light views -- dashboard, residents, rooms, shifts, activities."""
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from .models import Room, Resident, MonthlyCharge, StaffShift, Activity
from django.db import IntegrityError, DatabaseError


def _company(request):
    return get_user_company(request)


@login_required
def dashboard(request):
    company = _company(request)
    today = timezone.now().date()

    residents_active = Resident.objects.filter(company=company, status="active").select_related("company", "room").count()
    residents_waitlist = Resident.objects.filter(company=company, status="waitlist").select_related("company", "room").count()
    rooms = Room.objects.filter(company=company).select_related("company")
    rooms_available = rooms.filter(is_available=True).count()

    unpaid = MonthlyCharge.objects.filter(
        resident__company=company, status__in=["sent", "overdue"],
    ).aggregate(total=Sum("total_amount"))["total"] or 0

    today_shifts = StaffShift.objects.filter(
        company=company, date=today,
    ).select_related("staff_member").order_by("shift_type")

    upcoming_activities = Activity.objects.filter(
        company=company, date__gte=today,
    )[:5]

    return render(request, "eldercare/dashboard.html", {
        "residents_active": residents_active,
        "residents_waitlist": residents_waitlist,
        "rooms_total": rooms.count(),
        "rooms_available": rooms_available,
        "unpaid_total": unpaid,
        "today_shifts": today_shifts,
        "upcoming_activities": upcoming_activities,
        "today": today,
    })


@login_required
def resident_list(request):
    company = _company(request)
    status_filter = request.GET.get("status", "active")
    qs = Resident.objects.filter(company=company).select_related("room")
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, "eldercare/resident_list.html", {
        "residents": qs,
        "status_filter": status_filter,
    })


@login_required
def resident_detail(request, pk):
    company = _company(request)
    resident = get_object_or_404(Resident, pk=pk, company=company)
    relatives = resident.relatives.all()
    charges = resident.charges.order_by("-year", "-month")[:12]
    activities = resident.activities.order_by("-date")[:10]
    return render(request, "eldercare/resident_detail.html", {
        "resident": resident,
        "relatives": relatives,
        "charges": charges,
        "activities": activities,
    })


@login_required
def resident_create(request):
    company = _company(request)
    rooms = Room.objects.filter(company=company, is_available=True).select_related("company")

    if request.method == "POST":
        d = request.POST
        try:
            resident = Resident.objects.create(
                company=company,
                first_name=d.get("first_name", "").strip(),
                last_name=d.get("last_name", "").strip(),
                date_of_birth=d.get("date_of_birth"),
                oib=d.get("oib", "").strip(),
                gender=d.get("gender", ""),
                room_id=d.get("room") or None,
                status=d.get("status", "active"),
                admission_date=d.get("admission_date") or timezone.now().date(),
                emergency_contact_name=d.get("emergency_contact_name", "").strip(),
                emergency_contact_phone=d.get("emergency_contact_phone", "").strip(),
                dietary_requirements=d.get("dietary_requirements", "").strip(),
                mobility_notes=d.get("mobility_notes", "").strip(),
                gdpr_consent=bool(d.get("gdpr_consent")),
                gdpr_consent_date=timezone.now() if d.get("gdpr_consent") else None,
                notes=d.get("notes", "").strip(),
            )
            messages.success(request, f"Korisnik {resident} primljen.")
            return redirect("eldercare:resident_detail", pk=resident.pk)
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, str(e))

    return render(request, "eldercare/resident_form.html", {
        "rooms": rooms, "mode": "create",
    })


@login_required
def room_list(request):
    company = _company(request)
    rooms = Room.objects.filter(company=company).select_related("company").annotate(
        occupants=Count("residents", filter=Q(residents__status="active")),
    )
    return render(request, "eldercare/room_list.html", {"rooms": rooms})


@login_required
def shift_schedule(request):
    company = _company(request)
    date_str = request.GET.get("date", "")
    try:
        view_date = date.fromisoformat(date_str) if date_str else timezone.now().date()
    except ValueError:
        view_date = timezone.now().date()

    # Week view
    week_start = view_date - timedelta(days=view_date.weekday())
    week_dates = [week_start + timedelta(days=i) for i in range(7)]

    shifts = StaffShift.objects.filter(
        company=company,
        date__gte=week_start,
        date__lte=week_start + timedelta(days=6),
    ).select_related("staff_member").order_by("date", "shift_type")

    return render(request, "eldercare/shift_schedule.html", {
        "shifts": shifts,
        "week_dates": week_dates,
        "view_date": view_date,
        "prev_week": (week_start - timedelta(days=7)).isoformat(),
        "next_week": (week_start + timedelta(days=7)).isoformat(),
    })


@login_required
def activity_list(request):
    company = _company(request)
    upcoming = Activity.objects.filter(
        company=company, date__gte=timezone.now().date(),
    ).order_by("date")[:20]
    past = Activity.objects.filter(
        company=company, date__lt=timezone.now().date(),
    ).order_by("-date")[:10]
    return render(request, "eldercare/activity_list.html", {
        "upcoming": upcoming, "past": past,
    })


@login_required
def billing_list(request):
    company = _company(request)
    year = int(request.GET.get("year", timezone.now().year))
    month = int(request.GET.get("month", timezone.now().month))
    charges = MonthlyCharge.objects.filter(
        resident__company=company, year=year, month=month,
    ).select_related("resident", "resident__room")
    total = charges.aggregate(s=Sum("total_amount"))["s"] or 0
    return render(request, "eldercare/billing_list.html", {
        "charges": charges, "year": year, "month": month, "total": total,
    })


@login_required
@require_POST
def billing_generate(request):
    company = _company(request)
    year = int(request.POST.get("year", timezone.now().year))
    month = int(request.POST.get("month", timezone.now().month))

    residents = Resident.objects.filter(company=company, status="active", room__isnull=False).select_related("company", "room")
    created = 0
    for r in residents.select_related("room"):
        charge, is_new = MonthlyCharge.objects.get_or_create(
            resident=r, year=year, month=month,
            defaults={
                "base_amount": r.room.monthly_price,
                "total_amount": r.room.monthly_price,
            },
        )
        charge.calculate()
        if month == 12:
            charge.due_date = date(year + 1, 1, 15)
        else:
            charge.due_date = date(year, month + 1, 15)
        charge.save()
        if is_new:
            created += 1

    messages.success(request, f"Generirano {created} novih naplata za {month}/{year}.")
    return redirect(f"{reverse('eldercare:billing_list')}?year={year}&month={month}")
