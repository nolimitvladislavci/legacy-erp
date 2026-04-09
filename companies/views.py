import logging

logger = logging.getLogger(__name__)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import permissions, viewsets

from .models import Company
from .serializers import CompanySerializer


@login_required
def company_list(request):
    companies = Company.objects.all().order_by("name")
    return render(request, "companies/company_list.html", {"companies": companies})


@login_required
def company_create(request):
    if request.method == "POST":
        try:
            c = Company(
                name=request.POST["name"],
                oib=request.POST["oib"],
                address=request.POST.get("address", ""),
                city=request.POST.get("city", ""),
                zip_code=request.POST.get("zip_code", ""),
                iban=request.POST.get("iban", ""),
                is_vat_registered="is_vat_registered" in request.POST,
            )
            if "logo" in request.FILES:
                c.logo = request.FILES["logo"]
            c.save()
            messages.success(request, f"Tvrtka {c.name} kreirana.")
            return redirect("companies:list")
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "companies/company_form.html", {"action": "Nova tvrtka"})


@login_required
def company_edit(request, pk):
    company = get_object_or_404(Company, pk=pk)
    if request.method == "POST":
        try:
            company.name = request.POST["name"]
            company.oib = request.POST["oib"]
            company.address = request.POST.get("address", "")
            company.city = request.POST.get("city", "")
            company.zip_code = request.POST.get("zip_code", "")
            company.iban = request.POST.get("iban", "")
            company.is_vat_registered = "is_vat_registered" in request.POST
            if "logo" in request.FILES:
                company.logo = request.FILES["logo"]
            company.save()
            messages.success(request, f"Tvrtka {company.name} ažurirana.")
            return redirect("companies:list")
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "companies/company_form.html", {"company": company, "action": "Uredi tvrtku"})


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]

# === COMPANY SETTINGS ========================================================

import secrets
import string

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from accounts.models import UserProfile

from .models import CompanyBranch


def _require_company_admin(request):
    """Allow company_admin, project_manager, superadmin."""
    try:
        profile = request.user.profile
    except Exception:
        return None, None
    if not profile.is_company_admin:
        return None, None
    return profile, profile.company


def _require_strict_admin(request):
    """Only company_admin and superadmin — NOT project_manager."""
    try:
        profile = request.user.profile
    except Exception:
        return None, None
    if profile.role not in ('company_admin', 'superadmin', 'tenant_admin') and not profile.user.is_superuser:
        return None, None
    return profile, profile.company


@login_required
def company_settings(request):
    profile, company = _require_company_admin(request)
    if not company:
        messages.error(request, "Nemate pristup postavkama tvrtke.")
        return redirect("/")

    tab = request.GET.get("tab", "info")

    # Tab: info
    if tab == "info" and request.method == "POST":
        company.name = request.POST.get("name", company.name)
        company.oib = request.POST.get("oib", company.oib)
        company.address = request.POST.get("address", "")
        company.city = request.POST.get("city", "")
        company.zip_code = request.POST.get("zip_code", "")
        company.country = request.POST.get("country", company.country)
        company.iban = request.POST.get("iban", "")
        company.phone = request.POST.get("phone", "")
        company.email = request.POST.get("company_email", "")
        company.website_url = request.POST.get("website_url", "")
        company.mobile = request.POST.get("mobile", "")
        company.tax_number = request.POST.get("tax_number", "")
        company.vat_id = request.POST.get("vat_id", "")
        company.business_type = request.POST.get("business_type", company.business_type)
        company.currency = request.POST.get("currency", company.currency)
        company.fiscal_system = request.POST.get("fiscal_system", company.fiscal_system)
        company.pdv_status = request.POST.get("pdv_status", company.pdv_status)
        company.is_vat_registered = bool(request.POST.get("is_vat_registered"))
        if "logo" in request.FILES:
            company.logo = request.FILES["logo"]
        nkd_id = request.POST.get("nkd_code_id", "").strip()
        if nkd_id:
            try:
                from .models import NKDCode
                company.nkd_code = NKDCode.objects.get(pk=nkd_id)
            except Exception:
                pass
        elif "nkd_code_id" in request.POST:
            company.nkd_code = None
        company.save()
        messages.success(request, "Podaci tvrtke su azurirani.")
        return redirect("/companies/settings/?tab=info")

    # Tab: settings
    if tab == "settings" and request.method == "POST":
        # Company model fields
        company.business_type = request.POST.get("business_type", company.business_type)
        company.currency = request.POST.get("currency", company.currency)
        # JSON settings
        s = company.settings or {}
        s["default_tax_pct"] = request.POST.get("default_tax_pct", "25")
        s["invoice_number_format"] = request.POST.get("invoice_number_format", "{YYYY}-{NUM}")
        s["offer_number_format"] = request.POST.get("offer_number_format", "PON-{YYYY}-{NUM}")
        s["email_reply_to"] = request.POST.get("email_reply_to", "")
        s["working_hours"] = request.POST.get("working_hours", "08:00-16:00")
        s["ui_language"] = request.POST.get("ui_language", "hr")
        s["send_invoice_email"] = request.POST.get("send_invoice_email") == "1"
        s["send_offer_email"] = request.POST.get("send_offer_email") == "1"
        company.settings = s
        company.save()
        messages.success(request, "Postavke spremljene.")
        return redirect("/companies/settings/?tab=settings")

    # Tab: fiscal
    if tab == "fiscal" and request.method == "POST":
        company.fiscal_system = request.POST.get("fiscal_system", company.fiscal_system)
        company.pdv_status = request.POST.get("pdv_status", company.pdv_status)
        company.is_vat_registered = request.POST.get("is_vat_registered") == "1"
        company.is_kleinunternehmer = request.POST.get("is_kleinunternehmer") == "1"
        company.vat_id = request.POST.get("vat_id", company.vat_id)
        company.save(update_fields=[
            "fiscal_system", "pdv_status", "is_vat_registered",
            "is_kleinunternehmer", "vat_id",
        ])
        messages.success(request, "Fiskalne postavke su azurirane.")
        return redirect("/companies/settings/?tab=fiscal")

    # Context
    employees = UserProfile.objects.filter(company=company).select_related("user")
    branches = company.branches.all()

    sub = company.subscriptions.filter(is_active=True).first()
    usage = {
        "users": employees.count(),
        "locations": branches.filter(is_active=True).count(),
        "invoices": 0,
    }
    try:
        from invoicing.models import Invoice
        usage["invoices"] = Invoice.objects.filter(company=company).count()
    except Exception:
        pass

    # Fiscal certificates for fiscal tab
    fiscal_certs = []
    try:
        from django.utils import timezone as _tz

        from invoicing.fiscal_models import FiscalCertificate
        fiscal_certs = list(
            FiscalCertificate.objects.filter(company=company).select_related('location').order_by('-uploaded_at')
        )
        _now = _tz.now()
        for c in fiscal_certs:
            c.is_expired = c.valid_until and c.valid_until < _now
    except Exception:
        pass


    # Tab: integrations — API tokeni i vanjske integracije
    if tab == "integrations" and request.method == "POST":
        s = company.settings or {}
        # FINA Info.BIZ token — sprema se enkriptiran u settings JSON
        fina_token = request.POST.get("fina_infobiz_token", "").strip()
        if fina_token:
            s["fina_infobiz_token"] = fina_token
        elif "fina_infobiz_token_clear" in request.POST:
            s.pop("fina_infobiz_token", None)
        company.settings = s
        company.save()
        messages.success(request, "✅ Integracije spremljene.")
        return redirect("/companies/settings/?tab=integrations")

    return render(request, "companies/settings.html", {
        "company": company,
        "tab": tab,
        "fina_token_masked": __import__('partners.fina_infobiz', fromlist=['mask_token']).mask_token(
            (company.settings or {}).get('fina_infobiz_token', '')
        ) if (company.settings or {}).get('fina_infobiz_token') else '',
        "has_fina_token": bool((company.settings or {}).get('fina_infobiz_token')),
        "employees": employees,
        "branches": branches,
        "subscription": sub,
        "usage": usage,
        "fiscal_certs": fiscal_certs,
        "role_choices": [r for r in UserProfile.ROLE_CHOICES if r[0] != "superadmin"] if not getattr(profile, "is_superadmin", False) else UserProfile.ROLE_CHOICES,
        "branch_types": CompanyBranch.BRANCH_TYPES,
        "country_choices": Company.Country.choices,
        "settings_data": company.settings or {},
    })



@login_required
@require_POST
def employee_create(request):
    profile, company = _require_strict_admin(request)
    if not company:
        return JsonResponse({"error": "Forbidden"}, status=403)

    email = request.POST.get("email", "").strip()
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    role = request.POST.get("role", "worker")
    phone = request.POST.get("phone", "").strip()

    # Security: only superadmins can assign superadmin role
    if role == "superadmin" and not getattr(profile, "is_superadmin", False):
        return JsonResponse({"error": "Nemate ovlasti za dodjelu superadmin uloge."}, status=403)

    if not email:
        return JsonResponse({"error": "Email je obavezan."}, status=400)

    from django.contrib.auth.models import User
    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Korisnik s tim emailom vec postoji."}, status=400)

    alphabet = string.ascii_letters + string.digits
    temp_pw = "".join(secrets.choice(alphabet) for _ in range(12))

    base_un = email.split("@")[0].lower().replace(".", "_")[:30]
    username = base_un
    counter = 1
    while User.objects.filter(username=username).exists():
        username = base_un + str(counter)
        counter += 1

    user = User.objects.create_user(
        username=username, email=email, password=temp_pw,
        first_name=first_name, last_name=last_name,
    )
    if role in ("company_admin", "project_manager"):
        user.is_staff = True
        user.save()

    up, created = UserProfile.objects.get_or_create(user=user, defaults={
        "company": company, "role": role, "phone": phone,
        "must_change_password": True,
    })
    if not created:
        up.company = company
        up.role = role
        up.phone = phone
        up.must_change_password = True
        up.save()

    # Sync CompanyMembership
    from accounts.models import CompanyMembership
    CompanyMembership.objects.update_or_create(
        user=user, company=company,
        defaults={"role": role, "is_default": not CompanyMembership.objects.filter(user=user).exclude(company=company).exists()}
    )

    try:
        from django.core.mail import send_mail
        send_mail(
            "Vas pristup - " + company.name,
            "Postovani " + first_name + ",\n\nKreiran je korisnicki racun za LIMIT Connect.\n\n"
            + "Email: " + email + "\nLozinka: " + temp_pw + "\n\n"
            + "Prijavite se na: https://limit-connect.com/login/\n"
            + "Prilikom prve prijave bit cete zamoljeni da promijenite lozinku.\n\n"
            + "Pozdrav,\n" + company.name,
            "noreply@limit-connect.com",
            [email],
            fail_silently=True,
        )
    except Exception:
        pass

    return JsonResponse({"ok": True, "message": "Zaposlenik " + first_name + " " + last_name + " kreiran.", "temp_password": temp_pw})


@login_required
@require_POST
def employee_edit(request, pk):
    profile, company = _require_strict_admin(request)
    if not company:
        return JsonResponse({"error": "Forbidden"}, status=403)

    up = get_object_or_404(UserProfile, pk=pk, company=company)
    user = up.user
    user.first_name = request.POST.get("first_name", user.first_name)
    user.last_name = request.POST.get("last_name", user.last_name)
    user.email = request.POST.get("email", user.email)
    user.save()
    up.phone = request.POST.get("phone", up.phone)
    new_role = request.POST.get("role", up.role)
    # Security: only superadmins can assign superadmin role
    if new_role == "superadmin" and not getattr(profile, "is_superadmin", False):
        return JsonResponse({"error": "Nemate ovlasti za dodjelu superadmin uloge."}, status=403)
    up.role = new_role
    up.save()
    # Sync Django permissions with role
    if new_role in ("company_admin", "project_manager"):
        user.is_staff = True
        user.is_superuser = False
    elif new_role == "superadmin":
        user.is_staff = True
        user.is_superuser = True
    else:
        user.is_staff = False
        user.is_superuser = False
    user.save(update_fields=["is_staff", "is_superuser"])
    return JsonResponse({"ok": True, "message": "Zaposlenik azuriran."})


@login_required
@require_POST
def employee_change_password(request, pk):
    profile, company = _require_strict_admin(request)
    if not company:
        return JsonResponse({"error": "Forbidden"}, status=403)

    up = get_object_or_404(UserProfile, pk=pk, company=company)
    new_pw = request.POST.get("password", "").strip()
    if len(new_pw) < 8:
        return JsonResponse({"error": "Lozinka mora imati najmanje 8 znakova."}, status=400)
    up.user.set_password(new_pw)
    up.user.save()
    up.must_change_password = True
    up.save(update_fields=["must_change_password"])
    return JsonResponse({"ok": True, "message": "Lozinka promijenjena."})


@login_required
@require_POST
def employee_toggle_active(request, pk):
    profile, company = _require_strict_admin(request)
    if not company:
        return JsonResponse({"error": "Forbidden"}, status=403)

    up = get_object_or_404(UserProfile, pk=pk, company=company)
    up.user.is_active = not up.user.is_active
    up.user.save()
    status = "aktivan" if up.user.is_active else "deaktiviran"
    return JsonResponse({"ok": True, "message": "Korisnik " + status + "."})


@login_required
@require_POST
def branch_save(request, pk=None):
    profile, company = _require_company_admin(request)
    if not company:
        return JsonResponse({"error": "Forbidden"}, status=403)

    if pk:
        branch = get_object_or_404(CompanyBranch, pk=pk, parent_company=company)
    else:
        branch = CompanyBranch(parent_company=company)

    branch.name = request.POST.get("name", "")
    branch.branch_code = request.POST.get("branch_code", "")
    branch.branch_type = request.POST.get("branch_type", "other")
    branch.address = request.POST.get("address", "")
    branch.city = request.POST.get("city", "")
    branch.phone = request.POST.get("phone", "")
    branch.email = request.POST.get("email", "")
    branch.save()
    return JsonResponse({"ok": True, "message": "Podruznica spremljena."})


@login_required
@require_POST
def branch_toggle_active(request, pk):
    profile, company = _require_company_admin(request)
    if not company:
        return JsonResponse({"error": "Forbidden"}, status=403)

    branch = get_object_or_404(CompanyBranch, pk=pk, parent_company=company)
    branch.is_active = not branch.is_active
    branch.save(update_fields=["is_active"])
    status = "aktivna" if branch.is_active else "deaktivirana"
    return JsonResponse({"ok": True, "message": "Podruznica " + status + "."})



@login_required
@require_POST
def onboarding_dismiss(request):
    try:
        profile, company = _require_company_admin(request)
    except Exception:
        return JsonResponse({'ok': False}, status=403)
    if not company:
        return JsonResponse({'ok': False}, status=403)
    from .models import OnboardingProgress
    ob, _ = OnboardingProgress.objects.get_or_create(company=company)
    ob.dismissed = True
    ob.save(update_fields=['dismissed', 'updated_at'])
    return JsonResponse({'ok': True})


@login_required
def nkd_search(request):
    from django.db.models import Q
    from django.http import JsonResponse

    from .models import NKDCode
    q = request.GET.get("q", "").strip()
    level = request.GET.get("level", "")
    if not q or len(q) < 2:
        return JsonResponse([], safe=False)
    qs = NKDCode.objects.filter(is_active=True).filter(
        Q(name_hr__icontains=q) | Q(code__icontains=q) | Q(name_en__icontains=q)
    )
    if level:
        qs = qs.filter(level=level)
    results = list(qs.values("id", "code", "level", "name_hr", "name_en", "section")[:20])
    return JsonResponse(results, safe=False)


@login_required
@require_POST
def branch_save_redirect(request, pk=None):
    """Wrapper around branch_save that redirects instead of returning JSON."""
    profile, company = _require_company_admin(request)
    if not company:
        messages.error(request, 'Nemate pristup.')
        return redirect('/companies/settings/?tab=branches')

    if pk:
        from .models import CompanyBranch
        branch = get_object_or_404(CompanyBranch, pk=pk, parent_company=company)
    else:
        from .models import CompanyBranch
        branch = CompanyBranch(parent_company=company)

    branch.name = request.POST.get('name', '').strip()
    branch.branch_code = request.POST.get('branch_code', '').strip()
    branch.branch_type = request.POST.get('branch_type', 'other')
    branch.address = request.POST.get('address', '').strip()
    branch.city = request.POST.get('city', '').strip()
    branch.phone = request.POST.get('phone', '').strip()
    branch.email = request.POST.get('email', '').strip()
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        branch.save()
        if is_ajax:
            from django.http import JsonResponse
            return JsonResponse({'ok': True, 'name': branch.name, 'pk': branch.pk})
        messages.success(request, f'Podružnica {branch.name} spremljena.')
    except Exception as e:
        if is_ajax:
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        messages.error(request, f'Greška: {e}')
    return redirect('/companies/settings/?tab=branches')


@login_required
@require_POST
def branch_toggle_redirect(request, pk):
    """Toggle branch active status and redirect."""
    profile, company = _require_company_admin(request)
    if not company:
        messages.error(request, 'Nemate pristup.')
        return redirect('/companies/settings/?tab=branches')
    from .models import CompanyBranch
    branch = get_object_or_404(CompanyBranch, pk=pk, parent_company=company)
    branch.is_active = not branch.is_active
    branch.save(update_fields=['is_active'])
    status_str = 'aktivirana' if branch.is_active else 'deaktivirana'
    messages.success(request, f'Podružnica {status_str}.')
    return redirect('/companies/settings/?tab=branches')


@login_required
@require_POST
def employee_toggle_redirect(request, pk):
    """Toggle employee active status and redirect (form-friendly)."""
    profile, company = _require_strict_admin(request)
    if not company:
        messages.error(request, 'Nemate pristup.')
        return redirect('/companies/settings/?tab=employees')
    up = get_object_or_404(UserProfile, pk=pk, company=company)
    up.user.is_active = not up.user.is_active
    up.user.save()
    status_str = 'aktiviran' if up.user.is_active else 'deaktiviran'
    name = up.user.get_full_name() or up.user.username
    messages.success(request, f'Korisnik {name} {status_str}.')
    return redirect('/companies/settings/?tab=employees')


@login_required
def tax_rate_list(request):
    from .models import TaxRate
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema konteksta tvrtke.')
        return redirect('/')
    country = getattr(company, 'country', 'HR') or 'HR'

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name = request.POST.get('name', '').strip()
            rate = request.POST.get('rate', '25')
            if name:
                TaxRate.objects.get_or_create(country=country, rate=rate, defaults={'name': name})
                messages.success(request, f'Stopa "{name}" dodana.')
        elif action == 'delete':
            tid = request.POST.get('tax_id')
            TaxRate.objects.filter(pk=tid, country=country).delete()
            messages.success(request, 'Stopa obrisana.')
        elif action == 'edit':
            tid = request.POST.get('tax_id')
            t = TaxRate.objects.filter(pk=tid, country=country).first()
            if t:
                t.name = request.POST.get('name', t.name)
                t.rate = request.POST.get('rate', t.rate)
                t.save()
                messages.success(request, 'Stopa ažurirana.')
        return redirect('companies:tax_rates')

    rates = TaxRate.objects.filter(country=country).order_by('-rate')
    return render(request, 'companies/tax_rates.html', {'rates': rates, 'country': country})



# ── PRETPLATA / SUBSCRIPTION ──────────────────────────────────

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

@login_required
def subscription_view(request):
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company:
        from django.shortcuts import redirect
        return redirect('dashboard')

    from registration.models import CompanySubscription
    sub = CompanySubscription.objects.filter(company=company, is_active=True).first()

    from django.shortcuts import render
    return render(request, 'companies/subscription.html', {
        'company': company,
        'subscription': sub,
    })


@login_required
@require_POST
def subscription_cancel(request):
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema firme'}, status=400)

    from registration.models import CompanySubscription
    sub = CompanySubscription.objects.filter(company=company, is_active=True).first()
    if not sub:
        return JsonResponse({'error': 'Nema aktivne pretplate'}, status=400)

    action = request.POST.get('action', 'cancel')
    if action == 'reactivate':
        sub.reactivate()
        from django.contrib import messages
        messages.success(request, 'Pretplata reaktivirana!')
    else:
        sub.cancel()
        from django.contrib import messages
        messages.success(request, 'Pretplata ce biti otkazana na kraju perioda (%s). Arhiva ostaje dostupna.' % sub.valid_until)

    from django.shortcuts import redirect
    return redirect('companies:subscription')


# ── T&C Consent ──────────────────────────────────────────────────────────────

@login_required
def tc_consent_view(request):
    """GDPR T&C consent – firma mora prihvatiti prije korištenja FINA/KG usluga."""
    from core.company_utils import get_user_company
    from django.utils import timezone

    company = get_user_company(request)
    if not company:
        messages.error(request, 'Niste povezani s firmom.')
        return redirect('dashboard')

    if company.has_signed_tc_consent:
        messages.info(request, 'Uvjeti su već prihvaćeni.')
        return redirect('dashboard')

    if request.method == 'POST':
        if request.POST.get('accept_tc') == 'on':
            company.has_signed_tc_consent = True
            company.tc_consent_signed_at = timezone.now()
            company.tc_consent_version = '1.0'
            company.save(update_fields=[
                'has_signed_tc_consent',
                'tc_consent_signed_at',
                'tc_consent_version',
            ])
            messages.success(request, 'Uvjeti korištenja uspješno prihvaćeni. Hvala!')
            return redirect('dashboard')
        else:
            messages.warning(request, 'Morate označiti polje za prihvaćanje uvjeta.')

    return render(request, 'companies/tc_consent_document.html', {
        'company': company,
    })


# ════════════════════════════════════════════════════════════
# DRON2: Setup Wizard — async profil completiranje
# ════════════════════════════════════════════════════════════

@login_required
def setup_wizard(request):
    """Setup wizard — 5 sekcija, svaka neovisna."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    sections = {
        'company': bool(company.name and not company.is_draft),
        'fiscal': bool(company.oib and len(company.oib) == 11 and not company.oib.startswith('DRAFT')),
        'contact': bool(company.phone or company.email),
        'logo': bool(company.logo) if hasattr(company, 'logo') else False,
        'team': company.users.count() > 1 if hasattr(company, 'users') else False,
    }
    completion = int(sum(sections.values()) / max(len(sections), 1) * 100)

    return render(request, 'companies/setup_wizard.html', {
        'sections': sections,
        'completion': completion,
        'company': company,
        'page_title': 'Postavljanje profila',
    })


@login_required
def setup_wizard_company(request):
    """Sekcija A: Podaci tvrtke (naziv, OIB, adresa)."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    if request.method == 'POST':
        company.name = request.POST.get('name', company.name).strip()
        oib = request.POST.get('oib', '').strip()
        if oib and not oib.startswith('DRAFT'):
            company.oib = oib
        company.address = request.POST.get('address', '').strip()
        company.city = request.POST.get('city', '').strip()
        company.zip_code = request.POST.get('zip_code', '').strip()
        company.country = request.POST.get('country', 'HR')
        company.industry = request.POST.get('industry', 'other')
        company.is_draft = False
        company.save()
        messages.success(request, 'Podaci tvrtke spremljeni.')
        return redirect('companies:setup_wizard')

    return render(request, 'companies/setup_wizard.html', {
        'edit_section': 'company', 'company': company,
        'page_title': 'Podaci tvrtke',
    })


@login_required
def setup_wizard_contact(request):
    """Sekcija B: Kontakt podaci."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    if request.method == 'POST':
        company.phone = request.POST.get('phone', '').strip()
        company.email = request.POST.get('email', '').strip()
        company.website = request.POST.get('website', '').strip()
        company.save(update_fields=['phone', 'email', 'website'])
        messages.success(request, 'Kontakt podaci spremljeni.')
        return redirect('companies:setup_wizard')

    return render(request, 'companies/setup_wizard.html', {
        'edit_section': 'contact', 'company': company,
        'page_title': 'Kontakt',
    })


@login_required
def setup_wizard_fiscal(request):
    """Sekcija C: IBAN + Fiskalizacija."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    if request.method == 'POST':
        oib = request.POST.get('oib', '').strip()
        if oib and len(oib) >= 9:
            company.oib = oib
        iban = request.POST.get('iban', '').strip()
        if iban:
            company.iban = iban
        company.is_draft = False
        company.save()
        messages.success(request, 'Fiskalni podaci spremljeni.')
        return redirect('companies:setup_wizard')

    return render(request, 'companies/setup_wizard.html', {
        'edit_section': 'fiscal', 'company': company,
        'page_title': 'Fiskalizacija',
    })


# ══════════════════════════════════════════════════════════════
# KONJIK STOLOVI — view i API
# ══════════════════════════════════════════════════════════════

@login_required
def konjik_stolovi(request):
    """Upravljanje stolovima Konjik ureda."""
    from companies.models import KonjikStol, Company, CompanyPartnership

    # Pronađi Konjik (firma u kojoj user radi ili je superadmin)
    if request.user.is_superuser:
        konjik = Company.objects.filter(name__icontains='konjik').first()
    else:
        konjik = None
        from accounts.models import CompanyMembership
        for m in CompanyMembership.objects.filter(user=request.user, is_active=True).select_related('company'):
            if KonjikStol.objects.filter(ured=m.company).exists():
                konjik = m.company
                break

    if not konjik:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Nemate pristup upravljanju stolovima.")

    stolovi = KonjikStol.objects.filter(ured=konjik).prefetch_related('komitenti').select_related('referent')

    # Komitenti koji nisu ni na jednom stolu
    assigned_ids = set()
    for s in stolovi:
        assigned_ids.update(s.komitenti.values_list('id', flat=True))

    partner_ids = set(CompanyPartnership.objects.filter(
        partner_company=konjik, valid_until__isnull=True
    ).values_list('managed_company_id', flat=True))

    slobodni = Company.objects.filter(id__in=partner_ids - assigned_ids).order_by('name')

    # Dostupni referenti (osim superadmina)
    from accounts.models import CompanyMembership
    referenti = [
        m.user for m in CompanyMembership.objects.filter(
            company=konjik, is_active=True
        ).select_related('user').exclude(user__is_superuser=True)
    ]

    return render(request, 'companies/stolovi.html', {
        'konjik': konjik,
        'stolovi': stolovi,
        'slobodni': slobodni,
        'slobodni_count': slobodni.count(),
        'referenti': referenti,
        'ukupno_komitenata': len(partner_ids),
        'boje': ['#c9a84c','#22c55e','#3b82f6','#f97316','#ec4899','#8b5cf6','#06b6d4','#ef4444','#84cc16','#64748b'],
    })


@login_required
def konjik_stolovi_api(request):
    """JSON API za CRUD operacije stolova."""
    import json
    from companies.models import KonjikStol, Company
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    data = json.loads(request.body)
    action = data.get('action')

    if request.user.is_superuser:
        konjik = Company.objects.filter(name__icontains='konjik').first()
    else:
        from accounts.models import CompanyMembership
        konjik = None
        for m in CompanyMembership.objects.filter(user=request.user, is_active=True).select_related('company'):
            if KonjikStol.objects.filter(ured=m.company).exists():
                konjik = m.company
                break
    if not konjik:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    # ── Dodaj stol ──
    if action == 'add_stol':
        next_broj = (KonjikStol.objects.filter(ured=konjik).order_by('-broj').values_list('broj', flat=True).first() or 0) + 1
        boje = ['#c9a84c','#22c55e','#3b82f6','#f97316','#ec4899','#8b5cf6','#06b6d4','#ef4444','#84cc16','#64748b']
        boja = boje[(next_broj - 1) % len(boje)]
        stol = KonjikStol.objects.create(
            ured=konjik, broj=next_broj,
            naziv=f'Stol {next_broj}', boja=boja
        )
        return JsonResponse({'ok': True, 'stol_id': stol.id, 'broj': stol.broj, 'naziv': stol.naziv, 'boja': stol.boja})

    # ── Promijeni naziv stola ──
    if action == 'rename_stol':
        stol = KonjikStol.objects.get(id=data['stol_id'], ured=konjik)
        stol.naziv = data.get('naziv', stol.naziv)[:50]
        stol.save(update_fields=['naziv', 'updated_at'])
        return JsonResponse({'ok': True})

    # ── Dodijeli referenta ──
    if action == 'set_referent':
        stol = KonjikStol.objects.get(id=data['stol_id'], ured=konjik)
        uid = data.get('user_id')
        if uid:
            from django.contrib.auth.models import User
            stol.referent = User.objects.get(id=uid)
        else:
            stol.referent = None
        stol.save(update_fields=['referent', 'updated_at'])
        return JsonResponse({'ok': True})

    # ── Dodaj komitenta na stol ──
    if action == 'add_komitent':
        stol = KonjikStol.objects.get(id=data['stol_id'], ured=konjik)
        company = Company.objects.get(id=data['company_id'])
        stol.komitenti.add(company)
        # Automatski kreiraj CompanyMembership za referenta
        if stol.referent:
            from accounts.models import CompanyMembership
            CompanyMembership.objects.get_or_create(
                user=stol.referent, company=company,
                defaults={'role': 'company_admin', 'is_active': True}
            )
        return JsonResponse({'ok': True, 'komitenti_count': stol.komitenti_count})

    # ── Makni komitenta sa stola ──
    if action == 'remove_komitent':
        stol = KonjikStol.objects.get(id=data['stol_id'], ured=konjik)
        company = Company.objects.get(id=data['company_id'])
        stol.komitenti.remove(company)
        return JsonResponse({'ok': True, 'komitenti_count': stol.komitenti_count})

    # ── Obriši stol ──
    if action == 'delete_stol':
        stol = KonjikStol.objects.get(id=data['stol_id'], ured=konjik)
        stol.komitenti.clear()
        stol.delete()
        return JsonResponse({'ok': True})

    return JsonResponse({'error': 'Nepoznata akcija'}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
# WORKSPACE — Radni prostor views
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def workspace_home(request):
    """
    HOME SCREEN radnika — lista klijenata iz njegovog workspace-a.
    Klik na klijenta → switch_company → rad u kontekstu.
    """
    from companies.models import Workspace, Company
    from documents.models import ArhivaEntry
    from django.db.models import Count, Q

    # Pronađi aktivne workspace-e korisnika
    workspaces = Workspace.get_for_user(request.user)

    if not workspaces.exists() and request.user.is_superuser:
        # Superadmin bez workspace-a → admin view
        return redirect('companies:workspace_admin')

    # Ako ima točno 1 workspace, koristi ga. Inače prikaži izbor.
    active_ws_id = request.session.get('active_workspace_id')
    active_ws = None

    if active_ws_id:
        active_ws = workspaces.filter(id=active_ws_id).first()

    if not active_ws and workspaces.count() == 1:
        active_ws = workspaces.first()
        request.session['active_workspace_id'] = active_ws.id

    if not active_ws and workspaces.count() > 1:
        # Prikaži izbor workspace-a
        return render(request, 'companies/workspace_select.html', {
            'workspaces': workspaces,
        })

    if not active_ws:
        # Nema workspace-a — prikaži poruku
        return render(request, 'companies/workspace_empty.html')

    # Dohvati klijente iz aktivnog workspace-a s statistikama
    clients_qs = active_ws.clients.all().order_by('name')
    clients = []
    total_docs = 0
    total_pending = 0

    for c in clients_qs:
        try:
            stats = ArhivaEntry.objects.filter(company=c).aggregate(
                doc_count=Count('id'),
                pending_count=Count('id', filter=Q(is_booked=False))
            )
        except Exception:
            stats = {'doc_count': 0, 'pending_count': 0}
        c.doc_count = stats['doc_count'] or 0
        c.pending_count = stats['pending_count'] or 0
        total_docs += c.doc_count
        total_pending += c.pending_count
        clients.append(c)

    # Ostali workeri na istom workspace-u
    coworkers = active_ws.workers.exclude(id=request.user.id)

    return render(request, 'companies/workspace_home.html', {
        'workspace': active_ws,
        'workspaces': workspaces,
        'clients': clients,
        'coworkers': coworkers,
        'total_docs': total_docs,
        'total_pending': total_pending,
    })


@login_required
def workspace_switch(request, ws_id):
    """Prebaci se na drugi workspace."""
    from companies.models import Workspace
    ws = Workspace.objects.filter(id=ws_id, workers=request.user, is_active=True).first()
    if ws:
        request.session['active_workspace_id'] = ws.id
    return redirect('companies:workspace_home')


@login_required
def workspace_enter_client(request, client_id):
    """Uđi u kontekst klijenta iz workspace-a → switch_company."""
    from companies.models import Workspace, Company
    from accounts.models import CompanyMembership

    # Provjeri da je klijent u nekom od korisnikovih workspace-a
    user_client_ids = set()
    for ws in Workspace.get_for_user(request.user):
        user_client_ids.update(ws.clients.values_list('id', flat=True))

    # Superadmin može svugdje
    if not request.user.is_superuser and client_id not in user_client_ids:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Nemate pristup ovom klijentu.")

    # Osiguraj CompanyMembership
    company = Company.objects.filter(id=client_id).first()
    if not company:
        from django.http import Http404
        raise Http404

    mem, created = CompanyMembership.objects.get_or_create(
        user=request.user, company=company,
        defaults={'role': 'company_admin', 'is_active': True}
    )
    if not mem.is_active:
        mem.is_active = True
        mem.save(update_fields=['is_active'])

    # Switch session
    request.session['active_membership_id'] = mem.id
    request.session['workspace_client_id'] = str(client_id)

    # Redirect na dashboard klijenta ili arhivu
    next_url = request.GET.get('next', '/hr/dashboard/')
    return redirect(next_url)


@login_required
def workspace_admin(request):
    """
    Admin ploča — raspodjela klijenata i radnika na workspace-e.
    Samo za admin/superadmin.
    """
    import json
    from companies.models import Workspace, Company, CompanyPartnership
    from accounts.models import CompanyMembership
    from django.http import JsonResponse

    # Pronađi maticu
    if request.user.is_superuser:
        matica = Company.objects.filter(name__icontains='konjik').first()
        if not matica:
            matica = request.company if hasattr(request, 'company') else None
    else:
        matica = getattr(request, 'company', None)

    if not matica:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Nema matice.")

    # API za CRUD
    if request.method == 'POST' and request.headers.get('Content-Type', '').startswith('application/json'):
        data = json.loads(request.body)
        action = data.get('action')

        if action == 'add_workspace':
            count = Workspace.objects.filter(company=matica).count()
            colors = ['#c9a84c','#22c55e','#3b82f6','#f97316','#ec4899','#8b5cf6','#06b6d4','#ef4444','#84cc16','#64748b']
            ws = Workspace.objects.create(
                company=matica,
                name=data.get('name', f'Prostor {count + 1}'),
                type=data.get('type', 'desk'),
                color=colors[count % len(colors)],
                position=count + 1,
            )
            return JsonResponse({'ok': True, 'id': ws.id, 'name': ws.name})

        if action == 'rename_workspace':
            ws = Workspace.objects.get(id=data['ws_id'], company=matica)
            ws.name = data.get('name', ws.name)[:100]
            ws.save(update_fields=['name', 'updated_at'])
            return JsonResponse({'ok': True})

        if action == 'set_type':
            ws = Workspace.objects.get(id=data['ws_id'], company=matica)
            ws.type = data.get('type', ws.type)
            ws.save(update_fields=['type', 'updated_at'])
            return JsonResponse({'ok': True})

        if action == 'add_worker':
            ws = Workspace.objects.get(id=data['ws_id'], company=matica)
            from django.contrib.auth.models import User
            user = User.objects.get(id=data['user_id'])
            ws.workers.add(user)
            return JsonResponse({'ok': True})

        if action == 'remove_worker':
            ws = Workspace.objects.get(id=data['ws_id'], company=matica)
            ws.workers.remove(data['user_id'])
            return JsonResponse({'ok': True})

        if action == 'add_client':
            ws = Workspace.objects.get(id=data['ws_id'], company=matica)
            company = Company.objects.get(id=data['company_id'])
            ws.clients.add(company)
            return JsonResponse({'ok': True, 'client_count': ws.client_count})

        if action == 'remove_client':
            ws = Workspace.objects.get(id=data['ws_id'], company=matica)
            ws.clients.remove(data['company_id'])
            return JsonResponse({'ok': True, 'client_count': ws.client_count})

        if action == 'delete_workspace':
            ws = Workspace.objects.get(id=data['ws_id'], company=matica)
            ws.clients.clear()
            ws.workers.clear()
            ws.delete()
            return JsonResponse({'ok': True})

        return JsonResponse({'error': 'Unknown action'}, status=400)

    # GET — render admin page
    workspaces = Workspace.objects.filter(
        company=matica
    ).prefetch_related('clients', 'workers').order_by('position')

    # Slobodni klijenti (nisu na nijednom workspace-u)
    assigned_ids = set()
    for ws in workspaces:
        assigned_ids.update(ws.clients.values_list('id', flat=True))

    partner_ids = set(CompanyPartnership.objects.filter(
        partner_company=matica, valid_until__isnull=True
    ).values_list('managed_company_id', flat=True))

    slobodni = Company.objects.filter(id__in=partner_ids - assigned_ids).order_by('name')

    # Dostupni radnici
    radnici = [
        m.user for m in CompanyMembership.objects.filter(
            company=matica, is_active=True
        ).select_related('user').exclude(user__is_superuser=True)
    ]

    return render(request, 'companies/workspace_admin.html', {
        'matica': matica,
        'workspaces': workspaces,
        'slobodni': slobodni,
        'slobodni_count': slobodni.count(),
        'radnici': radnici,
        'ukupno_klijenata': len(partner_ids),
    })
