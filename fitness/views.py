import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets

from .models import Member, MemberCheckIn
from .serializers import MemberCheckInSerializer, MemberSerializer


@login_required
def member_list(request):
    q = request.GET.get("q", "")
    membership = request.GET.get("membership", "")
    status = request.GET.get("status", "active")
    qs = Member.objects.order_by("last_name", "first_name")
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q)
        )
    if membership:
        qs = qs.filter(membership_type=membership)
    if status:
        qs = qs.filter(status=status)
    today = timezone.now().date()
    expiring_soon = Member.objects.filter(
        status="active", membership_expires__lte=today + datetime.timedelta(days=7), membership_expires__gte=today
    ).count()
    expired = Member.objects.filter(membership_expires__lt=today, status="active").count()
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "fitness/member_list.html",
        {
            "page_obj": page,
            "q": q,
            "membership": membership,
            "status_f": status,
            "total": qs.count(),
            "expiring_soon": expiring_soon,
            "expired": expired,
            "membership_choices": Member.MEMBERSHIP_CHOICES,
            "status_choices": Member.STATUS_CHOICES,
            "today": today,
        },
    )


@login_required
def member_detail(request, pk):
    member = get_object_or_404(Member, pk=pk)
    checkins = member.checkins.order_by("-check_in")[:30]
    today = timezone.now().date()
    is_checked_in = member.checkins.filter(check_out__isnull=True).exists()
    checkins_this_month = member.checkins.filter(check_in__year=today.year, check_in__month=today.month).count()
    return render(
        request,
        "fitness/member_detail.html",
        {
            "member": member,
            "checkins": checkins,
            "is_checked_in": is_checked_in,
            "checkins_this_month": checkins_this_month,
            "today": today,
        },
    )


@login_required
def member_create(request):
    if request.method == "POST":
        try:
            m = Member(
                first_name=request.POST["first_name"],
                last_name=request.POST["last_name"],
                email=request.POST.get("email", ""),
                phone=request.POST.get("phone", ""),
                membership_type=request.POST.get("membership_type", "basic"),
                status=request.POST.get("status", "active"),
                rfid_card=request.POST.get("rfid_card", ""),
                notes=request.POST.get("notes", ""),
            )
            expires = request.POST.get("membership_expires")
            if expires:
                m.membership_expires = expires
            m.save()
            messages.success(request, f"Član {m.first_name} {m.last_name} dodan.")
            return redirect("fitness:member_detail", pk=m.pk)
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, str(e))
    return render(
        request,
        "fitness/member_form.html",
        {
            "membership_choices": Member.MEMBERSHIP_CHOICES,
            "status_choices": Member.STATUS_CHOICES,
            "action": "Novi član",
        },
    )


@login_required
def member_edit(request, pk):
    member = get_object_or_404(Member, pk=pk)
    if request.method == "POST":
        try:
            member.first_name = request.POST["first_name"]
            member.last_name = request.POST["last_name"]
            member.email = request.POST.get("email", "")
            member.phone = request.POST.get("phone", "")
            member.membership_type = request.POST.get("membership_type", "basic")
            member.status = request.POST.get("status", "active")
            member.rfid_card = request.POST.get("rfid_card", "")
            member.notes = request.POST.get("notes", "")
            expires = request.POST.get("membership_expires")
            if expires:
                member.membership_expires = expires
            member.save()
            messages.success(request, f"Podaci za {member.first_name} {member.last_name} ažurirani.")
            return redirect("fitness:member_detail", pk=member.pk)
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, str(e))
    return render(
        request,
        "fitness/member_form.html",
        {
            "member": member,
            "membership_choices": Member.MEMBERSHIP_CHOICES,
            "status_choices": Member.STATUS_CHOICES,
            "action": "Uredi člana",
        },
    )


@login_required
def member_checkin(request, pk):
    member = get_object_or_404(Member, pk=pk)
    active = member.checkins.filter(check_out__isnull=True).first()
    if active:
        active.check_out = timezone.now()
        active.save()
        messages.success(
            request, f"{member.first_name} {member.last_name} – odjava {active.check_out.strftime('%H:%M')}"
        )
    else:
        MemberCheckIn.objects.create(member=member)
        messages.success(
            request, f"{member.first_name} {member.last_name} – prijava {timezone.now().strftime('%H:%M')}"
        )
    return redirect(request.META.get("HTTP_REFERER", "fitness:list"))


@login_required
def checkin_dashboard(request):
    today = timezone.now().date()
    present = (
        MemberCheckIn.objects.filter(check_out__isnull=True, check_in__date=today)
        .select_related("member")
        .order_by("-check_in")
    )
    today_log = MemberCheckIn.objects.filter(check_in__date=today).select_related("member").order_by("-check_in")[:50]
    return render(
        request,
        "fitness/checkin_dashboard.html",
        {
            "present": present,
            "today_log": today_log,
            "present_count": present.count(),
            "today_total": today_log.count(),
            "today": today,
        },
    )


@extend_schema_view(list=extend_schema(tags=["Fitness"]))
class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer
    permission_classes = [permissions.IsAuthenticated]


@extend_schema_view(list=extend_schema(tags=["Fitness"]))
class MemberCheckInViewSet(viewsets.ModelViewSet):
    queryset = MemberCheckIn.objects.all()
    serializer_class = MemberCheckInSerializer
    permission_classes = [permissions.IsAuthenticated]
