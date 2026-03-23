import logging

logger = logging.getLogger(__name__)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework import viewsets

from core.company_utils import get_user_company

from .models import Partner
from .serializers import PartnerSerializer


@login_required
def partner_list(request):
    q = request.GET.get("q", "")
    ptype = request.GET.get("type", "")
    active = request.GET.get("active", "")
    company = get_user_company(request)
    qs = Partner.objects.select_related("company").filter(company=company).order_by("name") if company else Partner.objects.none()
    if q:
        qs = qs.filter(Q(name__icontains=q)|Q(email__icontains=q)|Q(oib__icontains=q)|Q(city__icontains=q))
    if ptype:
        qs = qs.filter(partner_type=ptype)
    if active == "1":
        qs = qs.filter(is_active=True)
    elif active == "0":
        qs = qs.filter(is_active=False)
    elif active == "incomplete":
        qs = qs.filter(Q(oib="")|Q(address="")|Q(city="")|Q(email=""))
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "partners/partner_list.html", {
        "page_obj": page, "q": q, "ptype": ptype, "active": active,
        "total": qs.count(), "type_choices": Partner.TYPE_CHOICES,
    })


@login_required
def partner_detail(request, pk):
    partner = get_object_or_404(Partner, pk=pk)
    transactions = []
    docs = []
    appointments = []
    try:
        transactions = partner.transactions.order_by("-date")[:20]
    except Exception:
        pass
    try:
        docs = partner.documents.order_by("-date_issued")[:10]
    except Exception:
        pass
    try:
        appointments = partner.appointments.order_by("-start_time")[:10]
    except Exception:
        pass
    return render(request, "partners/partner_detail.html", {
        "partner": partner,
        "transactions": transactions,
        "docs": docs,
        "appointments": appointments,
    })


@login_required
def partner_create(request):
    companies = [get_user_company(request)] if get_user_company(request) else []
    if request.method == "POST":
        try:
            company = get_user_company(request)
            if not company:
                messages.error(request, 'Nema aktivne firme.')
                return redirect('dashboard')
            p = Partner(
                company=company,
                name=request.POST["name"],
                oib=request.POST.get("oib", "").strip() or None,
                address=request.POST.get("address", ""),
                city=request.POST.get("city", ""),
                zip_code=request.POST.get("zip_code", ""),
                country=request.POST.get("country", "Hrvatska"),
                email=request.POST.get("email", ""),
                phone=request.POST.get("phone", ""),
                web=request.POST.get("web", ""),
                partner_type=request.POST.get("partner_type", "client"),
                buyer_type=request.POST.get("buyer_type", "b2c"),
                is_budget_user="is_budget_user" in request.POST,
                is_nonprofit_no_activity="is_nonprofit_no_activity" in request.POST,
                is_vat_registered="is_vat_registered" in request.POST,
                payment_term=int(request.POST.get("payment_term", 0) or 0),
                discount_percent=request.POST.get("discount_percent", 0) or 0,
                notes=request.POST.get("notes", ""),
            )
            nkd_id = request.POST.get("nkd_code_id", "").strip()
            if nkd_id:
                try:
                    p.nkd_code_id = int(nkd_id)
                except (ValueError, TypeError):
                    pass
            p.save()
            messages.success(request, f"Partner {p.name} kreiran.")
            return redirect("partners:detail", pk=p.pk)
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "partners/partner_form.html", {
        "companies": companies, "type_choices": Partner.TYPE_CHOICES,
        "action": "Novi partner",
    })


@login_required
def partner_edit(request, pk):
    partner = get_object_or_404(Partner, pk=pk)
    companies = [get_user_company(request)] if get_user_company(request) else []
    if request.method == "POST":
        try:
            # Company remains unchanged on edit — only admins may reassign via admin panel
            partner.name = request.POST["name"]
            partner.oib = request.POST.get("oib", "").strip() or None
            partner.address = request.POST.get("address", "")
            partner.city = request.POST.get("city", "")
            partner.zip_code = request.POST.get("zip_code", "")
            partner.country = request.POST.get("country", "Hrvatska")
            partner.email = request.POST.get("email", "")
            partner.phone = request.POST.get("phone", "")
            partner.web = request.POST.get("web", "")
            partner.partner_type = request.POST.get("partner_type", "client")
            partner.buyer_type = request.POST.get("buyer_type", "b2c")
            partner.is_budget_user = "is_budget_user" in request.POST
            partner.is_nonprofit_no_activity = "is_nonprofit_no_activity" in request.POST
            partner.is_vat_registered = "is_vat_registered" in request.POST
            partner.payment_term = int(request.POST.get("payment_term", 0) or 0)
            partner.discount_percent = request.POST.get("discount_percent", 0) or 0
            partner.notes = request.POST.get("notes", "")
            partner.is_active = "is_active" in request.POST
            nkd_id = request.POST.get("nkd_code_id", "").strip()
            if nkd_id:
                try:
                    partner.nkd_code_id = int(nkd_id)
                except (ValueError, TypeError):
                    pass
            elif not nkd_id:
                partner.nkd_code_id = None
            partner.save()
            messages.success(request, f"Partner {partner.name} azuriran.")
            return redirect("partners:detail", pk=partner.pk)
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "partners/partner_form.html", {
        "partner": partner, "companies": companies,
        "type_choices": Partner.TYPE_CHOICES, "action": "Uredi partnera",
    })


@login_required
def partner_delete(request, pk):
    partner = get_object_or_404(Partner, pk=pk)
    if request.method == "POST":
        name = partner.name
        partner.delete()
        messages.success(request, f"Partner {name} obrisan.")
        return redirect("partners:list")
    return render(request, "partners/partner_confirm_delete.html", {"partner": partner})



@login_required
@require_POST
def partner_quick_create(request):
    import json
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    name = (data.get('name') or '').strip()
    oib  = (data.get('oib') or '').strip()

    if not name:
        return JsonResponse({'ok': False, 'error': 'Naziv je obavezan.'}, status=400)

    company = get_user_company(request)
    if not company:
        return JsonResponse({'ok': False, 'error': 'Nema aktivne firme.'}, status=403)

    # Duplicate check by OIB first, then name
    existing = None
    if oib:
        existing = Partner.objects.select_related("company").filter(company=company, oib=oib).first()
    if not existing:
        existing = Partner.objects.select_related("company").filter(company=company, name__iexact=name).first()

    if existing:
        return JsonResponse({
            'ok': True, 'status': 'exists',
            'id': existing.pk, 'name': existing.name,
            'oib': existing.oib, 'email': existing.email,
            'address': existing.address, 'city': existing.city,
        })

    p = Partner(
        company=company,
        name=name,
        oib=oib,
        email=(data.get('email') or '').strip(),
        phone=(data.get('phone') or '').strip(),
        address=(data.get('address') or '').strip(),
        city=(data.get('city') or '').strip(),
        partner_type=(data.get('partner_type') or 'client'),
    )
    p.save()
    return JsonResponse({
        'ok': True, 'status': 'created',
        'id': p.pk, 'name': p.name,
        'oib': p.oib, 'email': p.email,
        'address': p.address, 'city': p.city,
    }, status=201)



@login_required
def partner_oib_lookup(request):
    """AJAX: Dohvati podatke firme po OIB-u / VAT ID-u — koristi centralni business_lookup servis."""
    oib = request.GET.get('oib', '').strip()
    country = request.GET.get('country', 'HR').strip().upper()
    if len(country) > 3:
        country = 'HR'

    if not oib:
        return JsonResponse({'error': 'OIB je obavezan'}, status=400)

    from core.oib_validator import validate_vat_id
    if not validate_vat_id(oib, country):
        return JsonResponse({'error': 'Neispravan OIB/VAT format', 'valid_format': False}, status=400)

    company = get_user_company(request)

    from core.business_lookup import lookup_business
    result = lookup_business(oib, country, company=company)
    return JsonResponse(result.to_dict())


class PartnerViewSet(viewsets.ModelViewSet):
    serializer_class = PartnerSerializer

    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        return Partner.objects.select_related("company").filter(company=company) if company else Partner.objects.none()


# ── Quick-add API ──────────────────────────────────────────────────
@login_required
def api_quick_create(request):
    """Create partner via AJAX from quick-add modal."""
    import json
    from django.http import JsonResponse
    from core.company_utils import get_user_company

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema aktivne firme'}, status=400)

    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'error': 'Naziv je obavezan'}, status=400)

        partner = Partner(
            company=company,
            name=name,
            email=data.get('email', ''),
            oib=data.get('oib', ''),
            address=data.get('address', ''),
            city=data.get('city', ''),
            phone=data.get('phone', ''),
            partner_type='client',
        )
        partner.save()
        return JsonResponse({
            'ok': True,
            'id': partner.pk,
            'name': partner.name,
            'message': f'Partner "{partner.name}" dodan!'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
