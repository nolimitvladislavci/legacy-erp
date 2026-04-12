from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import permissions, viewsets

from partners.models import Partner

from .models import InsurancePolicy
from .serializers import InsurancePolicySerializer


class InsurancePolicyViewSet(viewsets.ModelViewSet):
    queryset = InsurancePolicy.objects.all()
    serializer_class = InsurancePolicySerializer
    permission_classes = [permissions.IsAuthenticated]


@login_required
def policy_list(request):
    q = request.GET.get("q", "")
    ins_type = request.GET.get("type", "")
    status = request.GET.get("status", "")

    qs = InsurancePolicy.objects.select_related("partner").order_by("-start_date")
    if q:
        qs = qs.filter(
            Q(policy_number__icontains=q) |
            Q(insurer__icontains=q) |
            Q(partner__name__icontains=q)
        )
    if ins_type:
        qs = qs.filter(insurance_type=ins_type)
    if status:
        qs = qs.filter(status=status)

    today = timezone.now().date()
    expiring_soon = qs.filter(
        status="active", end_date__lte=today + timezone.timedelta(days=30)
    ).count()
    total_premium = qs.filter(status="active").aggregate(s=Sum("premium"))["s"] or 0

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "insurance/policy_list.html", {
        "page_obj": page,
        "q": q, "ins_type": ins_type, "status": status,
        "total": qs.count(),
        "active_count": qs.filter(status="active").count(),
        "expiring_soon": expiring_soon,
        "total_premium": total_premium,
        "type_choices": InsurancePolicy.TYPE_CHOICES,
        "status_choices": InsurancePolicy.STATUS_CHOICES,
    })


@login_required
def policy_create(request):
    if request.method == "POST":
        try:
            partner_id = request.POST.get("partner")
            partner = Partner.objects.get(pk=partner_id) if partner_id else None
            InsurancePolicy.objects.create(
                policy_number=request.POST["policy_number"],
                insurance_type=request.POST["insurance_type"],
                insurer=request.POST["insurer"],
                partner=partner,
                start_date=request.POST["start_date"],
                end_date=request.POST["end_date"],
                premium=request.POST["premium"],
                coverage_amount=request.POST.get("coverage_amount", 0),
                status=request.POST.get("status", "active"),
                notes=request.POST.get("notes", ""),
            )
            messages.success(request, _("Polica kreirana."))
            return redirect("insurance:list")
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "insurance/policy_form.html", {
        "partners": Partner.objects.filter(is_active=True).order_by("name"),
        "type_choices": InsurancePolicy.TYPE_CHOICES,
        "status_choices": InsurancePolicy.STATUS_CHOICES,
        "action": "Nova polica",
    })


@login_required
def policy_edit(request, pk):
    policy = get_object_or_404(InsurancePolicy, pk=pk)
    if request.method == "POST":
        try:
            partner_id = request.POST.get("partner")
            policy.partner = Partner.objects.get(pk=partner_id) if partner_id else None
            policy.policy_number = request.POST["policy_number"]
            policy.insurance_type = request.POST["insurance_type"]
            policy.insurer = request.POST["insurer"]
            policy.start_date = request.POST["start_date"]
            policy.end_date = request.POST["end_date"]
            policy.premium = request.POST["premium"]
            policy.coverage_amount = request.POST.get("coverage_amount", 0)
            policy.status = request.POST.get("status", "active")
            policy.notes = request.POST.get("notes", "")
            policy.save()
            messages.success(request, _("Polica ažurirana."))
            return redirect("insurance:list")
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "insurance/policy_form.html", {
        "policy": policy,
        "partners": Partner.objects.filter(is_active=True).order_by("name"),
        "type_choices": InsurancePolicy.TYPE_CHOICES,
        "status_choices": InsurancePolicy.STATUS_CHOICES,
        "action": "Uredi policu",
    })


@login_required
def policy_delete(request, pk):
    policy = get_object_or_404(InsurancePolicy, pk=pk)
    if request.method == "POST":
        policy.delete()
        messages.success(request, _("Polica obrisana."))
    return redirect("insurance:list")
