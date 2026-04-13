import logging
from drf_spectacular.utils import extend_schema, extend_schema_view

logger = logging.getLogger(__name__)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
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
    except (IntegrityError, DatabaseError):
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
                messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
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
        except (ValueError, TypeError) as e:
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
        except (ValueError, TypeError) as e:
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
        return redirect("partners:partner_list")
    return render(request, "partners/partner_confirm_delete.html", {"partner": partner})



@login_required
@require_POST
def partner_quick_create(request):
    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
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


@extend_schema_view(list=extend_schema(tags=["Partners"]))
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
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'error': str(e)}, status=400)


# ── Buyer Type Verification ───────────────────────────────────────
import re



@login_required
def buyer_type_verify(request):
    """View za Mariju: pregled i potvrda 469 auto-klasificiranih partnera."""
    from collections import OrderedDict

    from django.utils import timezone

    from companies.models import Company

    qs = Partner.objects.select_related('company').filter(
        notes__contains='needs_verification'
    ).order_by('buyer_type', 'name')

    # ── POST: potvrdi ili promijeni ──
    if request.method == 'POST':
        # Single confirm
        single_id = request.POST.get('confirm_single')
        if single_id:
            p = get_object_or_404(Partner, pk=single_id)
            new_type = request.POST.get(f'new_type_{single_id}', p.buyer_type)
            _verify_partner(p, new_type)
            messages.success(request, f'{p.name} verificiran kao {new_type}.')
            return redirect(request.get_full_path())

        # Bulk confirm
        ids = request.POST.getlist('ids')
        if ids:
            partners = Partner.objects.filter(pk__in=ids)
            if 'bulk_b2c' in request.POST:
                for p in partners:
                    _verify_partner(p, 'b2c')
                messages.success(request, f'{len(ids)} partnera vraćeno na B2C.')
            else:
                count = 0
                for p in partners:
                    new_type = request.POST.get(f'new_type_{p.pk}', p.buyer_type)
                    _verify_partner(p, new_type)
                    count += 1
                messages.success(request, f'{count} partnera verificirano.')
            return redirect(request.get_full_path())

    # ── GET: filtriranje ──
    q = request.GET.get('q', '')
    filter_bt = request.GET.get('buyer_type', '')
    filter_company = request.GET.get('company', '')

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(oib__icontains=q))
    if filter_bt:
        qs = qs.filter(buyer_type=filter_bt)
    if filter_company:
        qs = qs.filter(company_id=filter_company)

    # Stats
    stats = OrderedDict()
    for row in qs.values('buyer_type').annotate(cnt=Q(pk__isnull=False)).order_by():
        stats[row['buyer_type']] = row['cnt']
    # Use actual count
    from django.db.models import Count
    stats_qs = qs.values('buyer_type').annotate(cnt=Count('id')).order_by('-cnt')
    stats = OrderedDict((r['buyer_type'], r['cnt']) for r in stats_qs)

    total = qs.count()
    verified_today = Partner.objects.filter(
        notes__contains='VERIFIED',
        updated_at__date=timezone.now().date(),
    ).count()

    # Annotate classify reason from notes
    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page'))

    for p in page:
        match = re.search(r'\[AUTO-CLASSIFY[^\]]*\][^\|]*\|\s*(.+)', p.notes or '')
        p.classify_reason = match.group(1).strip() if match else ''

    companies = Company.objects.all().order_by('name')

    return render(request, 'partners/buyer_type_verify.html', {
        'page_obj': page,
        'total': total,
        'verified_today': verified_today,
        'stats': stats,
        'q': q,
        'filter_bt': filter_bt,
        'filter_company': int(filter_company) if filter_company else '',
        'companies': companies,
        'buyer_type_choices': Partner.BUYER_TYPE_CHOICES,
    })


def _verify_partner(partner, new_type):
    """Potvrdi buyer_type i ukloni needs_verification marker."""
    from django.utils import timezone
    valid_types = [c[0] for c in Partner.BUYER_TYPE_CHOICES]
    if new_type not in valid_types:
        new_type = partner.buyer_type

    partner.buyer_type = new_type
    partner.is_budget_user = (new_type == 'b2g')
    partner.is_nonprofit_no_activity = new_type.startswith('udruga')

    # Replace needs_verification with VERIFIED marker
    notes = partner.notes or ''
    notes = re.sub(
        r'\[AUTO-CLASSIFY[^\]]*\] needs_verification=True',
        f'[VERIFIED {timezone.now():%Y-%m-%d}]',
        notes,
    )
    partner.notes = notes
    partner.save(update_fields=[
        'buyer_type', 'is_budget_user', 'is_nonprofit_no_activity',
        'notes', 'updated_at',
    ])
