import re
import logging
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now
from django.views.decorators.http import require_POST

from core.email_tasks import send_email_task

from .constants import PLAN_FEATURES

# forms no longer needed for self-service flow
from .models import CompanyRegistration, CompanySubscription

logger = logging.getLogger(__name__)

# Auto-registration imports
from website.models import CompanyWebsite
from django.utils.text import slugify



def _auto_create_website(company):
    """Auto-create a company website on registration."""
    try:
        if CompanyWebsite.objects.filter(company=company).exists():
            return CompanyWebsite.objects.get(company=company)
        slug_base = slugify(company.name)[:40] or "firma"
        slug = slug_base
        counter = 1
        while CompanyWebsite.objects.filter(slug=slug).exists():
            slug = f"{slug_base}-{counter}"
            counter += 1
        website = CompanyWebsite.objects.create(
            company=company,
            slug=slug,
            site_title=company.name,
            tagline=f"{company.name} - sluzbena web stranica",
            theme="generic",
            is_published=True,
        )
        logger.info("Auto-created website /site/%s/ for %s", slug, company.name)
        return website
    except Exception as e:
        logger.error("Auto website creation failed for %s: %s", company.name, e)
        return None


def _generate_company_email(company):
    """Generate a plus-addressed email for the company."""
    slug = slugify(company.name)[:30] or "firma"
    return f"fina.connect.online+{slug}@gmail.com"




def _seed_demo_data(company, user):
    """Create demo data so new user is not staring at empty screens."""
    try:
        from partners.models import Partner
        from inventory.models import InventoryItem

        # 3 demo partners
        for name, oib, ptype in [
            ('Demo Kupac d.o.o.', 'DEMO-001', 'client'),
            ('Demo Dobavljac j.d.o.o.', 'DEMO-002', 'supplier'),
            ('Demo Partner', 'DEMO-003', 'both'),
        ]:
            Partner.objects.get_or_create(
                company=company, name=name,
                defaults={'oib': oib, 'partner_type': ptype}
            )

        # 3 demo items
        for name, sku, price, cat in [
            ('Primjer artikl 1', 'DEMO-A1', 10.00, 'product'),
            ('Primjer usluga', 'DEMO-U1', 50.00, 'service'),
            ('Primjer materijal', 'DEMO-M1', 5.00, 'material'),
        ]:
            InventoryItem.objects.get_or_create(
                company=company, sku=sku,
                defaults={'name': name, 'unit_price': price, 'quantity': 100, 'category': cat}
            )

        # Mark onboarding steps
        from companies.models import OnboardingProgress
        onb, _ = OnboardingProgress.objects.get_or_create(company=company)
        onb.first_partner_added = True
        onb.first_item_added = True
        onb.save(update_fields=['first_partner_added', 'first_item_added', 'updated_at'])

        logger.info("Seeded demo data for %s", company.name)
    except Exception as e:
        logger.warning("Demo data seeding failed for %s: %s", company.name, e)


def register_step1(request):
    """Step 1: Plan selection (with optional invite code)"""
    # Check for invite code in URL or POST
    invite_code_str = request.GET.get('invite', '') or request.POST.get('invite_code', '')
    if invite_code_str:
        from .models import UmbrellaInviteCode
        try:
            invite = UmbrellaInviteCode.objects.get(code=invite_code_str.strip())
            if invite.is_valid():
                request.session['reg_invite_code'] = invite.code
                request.session['reg_plan'] = invite.plan_slug
                request.session['reg_invite_umbrella'] = str(invite.umbrella_company_id)
                request.session['reg_invite_relation'] = invite.relation_type
                if invite.modules_override:
                    request.session['reg_invite_modules'] = invite.modules_override
                if invite.free_months:
                    request.session['reg_invite_free_months'] = invite.free_months
                from django.contrib import messages as msg
                msg.info(request, 'Pozivni kod prihvacen! Registrirate se pod %s.' % invite.umbrella_company.name)
                return redirect('registration:register_step2')
            else:
                from django.contrib import messages as msg
                msg.warning(request, 'Pozivni kod je istekao ili iskoristen.')
        except UmbrellaInviteCode.DoesNotExist:
            from django.contrib import messages as msg
            msg.error(request, 'Nevazeci pozivni kod.')
    from .models import PricingPlan
    plans = PricingPlan.objects.filter(is_active=True).order_by("sort_order")
    if request.method == "POST":
        plan_slug = request.POST.get("plan", "starter")
        promo_code = request.POST.get("promo_code", "").strip().upper()
        request.session["reg_plan"] = plan_slug
        if promo_code:
            request.session["reg_promo_code"] = promo_code
        elif "reg_promo_code" in request.session:
            del request.session["reg_promo_code"]
        return redirect("registration:register_step2")
    source = request.GET.get("source", "")
    if source:
        request.session["reg_source"] = source
    return render(request, "registration/step1.html", {"step": 1, "plans": plans})


def register_step2(request):
    """Step 2: Company info"""
    if not request.session.get("reg_plan"):
        return redirect("registration:register_step1")
    INDUSTRY_CHOICES = [
        ("it", "IT i softver"),
        ("trade", "Trgovina"),
        ("services", "Usluge"),
        ("gastro", "Ugostiteljstvo"),
        ("construction", "Graditeljstvo"),
        ("health", "Zdravstvo"),
        ("other", "Ostalo"),
    ]
    if request.method == "POST":
        data = {
            "name": request.POST.get("name", "").strip(),
            "oib": request.POST.get("oib", "").strip(),
            "country": request.POST.get("country", "HR"),
            "address": request.POST.get("address", "").strip(),
            "city": request.POST.get("city", "").strip(),
            "zip_code": request.POST.get("zip_code", "").strip(),
            "industry": request.POST.get("industry", "other"),
        }
        errors = {}
        if not data["name"]:
            errors["name"] = "Naziv tvrtke je obavezan."
        if not data["oib"]:
            errors["oib"] = "OIB / Porezni broj je obavezan."
        elif data["country"] == "HR" and not re.match(r'^\d{11}$', data["oib"]):
            errors["oib"] = "Hrvatski OIB mora imati točno 11 znamenki."
        elif data["country"] == "DE" and len(data["oib"]) < 9:
            errors["oib"] = "Unesite valjani porezni broj (min. 9 znakova)."
        if errors:
            return render(request, "registration/step2.html", {
                "step": 2, "data": data, "errors": errors,
                "industries": INDUSTRY_CHOICES,
            })
        request.session["reg_company"] = data
        return redirect("registration:register_step3")
    data = request.session.get("reg_company", {})
    return render(request, "registration/step2.html", {
        "step": 2, "data": data, "errors": {},
        "industries": INDUSTRY_CHOICES,
    })


def register_step3(request):
    """Step 3: Admin user"""
    if not request.session.get("reg_plan") or not request.session.get("reg_company"):
        return redirect("registration:register_step1")
    if request.method == "POST":
        data = {
            "first_name": request.POST.get("first_name", "").strip(),
            "last_name": request.POST.get("last_name", "").strip(),
            "email": request.POST.get("email", "").strip(),
            "phone": request.POST.get("phone", "").strip(),
        }
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")
        errors = {}
        if not data["first_name"]:
            errors["first_name"] = "Ime je obavezno."
        if not data["email"]:
            errors["email"] = "Email je obavezan."
        elif User.objects.filter(email=data["email"]).exists():
            errors["email"] = "Korisnik s ovim emailom vec postoji. <a href='/password-reset/' style='color:#c9a84c;'>Resetirajte lozinku?</a>"
        if len(password1) < 8:
            errors["password1"] = "Lozinka mora imati najmanje 8 znakova."
        elif not any(c.isupper() for c in password1):
            errors["password1"] = "Lozinka mora sadrzavati barem jedno veliko slovo."
        elif not any(c.islower() for c in password1):
            errors["password1"] = "Lozinka mora sadrzavati barem jedno malo slovo."
        elif not any(c.isdigit() for c in password1):
            errors["password1"] = "Lozinka mora sadrzavati barem jednu znamenku."
        if password1 != password2:
            errors["password2"] = "Lozinke se ne podudaraju."
        if errors:
            return render(request, "registration/step3.html", {
                "step": 3, "data": data, "errors": errors,
            })
        request.session["reg_user"] = data
        request.session["reg_password"] = password1
        return redirect("registration:register_step4")
    data = request.session.get("reg_user", {})
    return render(request, "registration/step3.html", {
        "step": 3, "data": data, "errors": {},
    })


def register_step4(request):
    """Step 4: Review + auto-create"""
    plan_slug = request.session.get("reg_plan")
    company_data = request.session.get("reg_company")
    user_data = request.session.get("reg_user")
    if not plan_slug or not company_data or not user_data:
        return redirect("registration:register_step1")

    from .models import PricingPlan
    plan = PricingPlan.objects.filter(slug=plan_slug, is_active=True).first()
    if not plan:
        messages.error(request, "Odabrani plan nije dostupan.")
        return redirect("registration:register_step1")

    if request.method == "POST":
        from datetime import timedelta

        from django.contrib.auth import login

        from accounts.models import UserProfile
        from companies.models import Company

        try:
            # Create user
            email = user_data["email"]
            base_un = email.split("@")[0].lower().replace(".", "_")[:30]
            username = base_un
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_un}{counter}"
                counter += 1
            password = request.session.get("reg_password", "")
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=user_data.get("first_name", ""),
                last_name=user_data.get("last_name", ""),
            )

            # Create company
            country_code = company_data.get("country", "HR")
            company_fields = [f.name for f in Company._meta.get_fields()]
            company_kwargs = {"name": company_data["name"], "oib": company_data["oib"]}
            if "country" in company_fields:
                company_kwargs["country"] = country_code
            if "address" in company_fields:
                addr = company_data.get("address", "")
                city = company_data.get("city", "")
                zip_code = company_data.get("zip_code", "")
                company_kwargs["address"] = f"{addr}, {zip_code} {city}".strip(", ")
            if "business_type" in company_fields:
                company_kwargs["business_type"] = "doo"
            company = Company.objects.create(**company_kwargs)

            # Create profile
            UserProfile.objects.create(user=user, company=company, role="company_admin")
            # Create RBAC role for permissions
            try:
                from permissions.models import Role, UserRole
                admin_role = Role.objects.get(role_type='company_admin')
                UserRole.objects.get_or_create(
                    user=user, role=admin_role, company=company,
                    defaults={"is_primary": True}
                )
            except Exception:
                pass

            # Link to umbrella if invite code was used
            invite_code_str = request.session.get('reg_invite_code', '')
            umbrella_id = request.session.get('reg_invite_umbrella', '')
            if invite_code_str and umbrella_id:
                try:
                    from registration.models import UmbrellaInviteCode
                    invite = UmbrellaInviteCode.objects.get(code=invite_code_str)
                    company.umbrella_parent_id = umbrella_id
                    company.umbrella_relation = request.session.get('reg_invite_relation', 'client')
                    company.save(update_fields=['umbrella_parent_id', 'umbrella_relation'])
                    invite.times_used += 1
                    invite.save(update_fields=['times_used'])
                except Exception:
                    pass

            # Create subscription
            trial_end = now().date() + timedelta(days=14)
            subscription = CompanySubscription.objects.create(
                company=company,
                plan=plan_slug,
                pricing_plan=plan,
                valid_from=now().date(),
                trial_ends=trial_end,
                billing_cycle="monthly",
                monthly_fee=plan.price_monthly,
                is_active=True,
            )

            # Try seed konto chart
            try:
                from django.core.management import call_command
                call_command("seed_konto_chart", company_id=company.pk)
            except Exception:
                pass

            # Try assign RBAC role
            try:
                from permissions.services import PermissionManager
                PermissionManager.assign_role(user, "company_admin", company)
            except Exception:
                pass

            # Apply invite code free months + modules
            invite_free = request.session.get('reg_invite_free_months', 0)
            if invite_free:
                from datetime import timedelta as td2
                if subscription.trial_ends:
                    subscription.trial_ends += td2(days=30 * invite_free)
                else:
                    subscription.trial_ends = now().date() + td2(days=30 * invite_free)
                subscription.save(update_fields=['trial_ends'])
            invite_modules = request.session.get('reg_invite_modules')
            if invite_modules:
                subscription.modules_override = invite_modules
                subscription.save(update_fields=['modules_override'])

            # Apply promo code if present
            promo_code_str = request.session.get("reg_promo_code", "")
            if promo_code_str:
                try:
                    from .models import PromoCode
                    promo = PromoCode.objects.get(code=promo_code_str)
                    if promo.is_valid():
                        success, _msg = promo.apply_to_subscription(subscription)
                        if success:
                            subscription.promo_code = promo
                            subscription.save(update_fields=['promo_code'])
                except Exception:
                    pass

            # Auto-assign grosmarkt modules if source=grosmarkt
            reg_source = request.session.get("reg_source", "")
            if reg_source == "grosmarkt":
                grosmarkt_modules = [
                    "marketplace", "delivery", "invoicing",
                    "partners", "worktime", "pos",
                ]
                subscription.modules_override = grosmarkt_modules
                subscription.save(update_fields=["modules_override"])

            # Cleanup session
            for key in ["reg_plan", "reg_company", "reg_user", "reg_password", "reg_promo_code", "reg_source", "reg_invite_code", "reg_invite_umbrella", "reg_invite_relation", "reg_invite_modules", "reg_invite_free_months"]:
                request.session.pop(key, None)

            # Login and redirect
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")

            # Seed demo data for new companies
            _seed_demo_data(company, user)

            # Auto-create website and generate company email
            website = _auto_create_website(company)
            company_email = _generate_company_email(company)
            if website:
                website_url = f"https://limit-connect.com/site/{website.slug}/"
            else:
                website_url = None

            messages.success(request, "Dobrodosli u LIMIT Connect! Vas trial traje do {}.".format(trial_end.strftime("%d.%m.%Y")))

            # Store info for success page
            request.session["reg_success_website_url"] = website_url or ""
            request.session["reg_success_company_email"] = company_email
            request.session["reg_success_company_name"] = company.name
            request.session["reg_success_plan_name"] = plan.name
            request.session["reg_success_trial_end"] = trial_end.strftime("%d.%m.%Y")

            # Send welcome email
            try:
                send_email_task.delay(
                    subject="[LIMIT Connect] Dobrodosli!",
                    message="Postovani {},\n\nVas racun za {} je kreiran.\nPlan: {}\nTrial do: {}\nVasa web stranica: {}\nVas email za prijem: {}\n\nPrijavite se na: https://limit-connect.com/accounts/login/".format(
                        user.first_name, company.name, plan.name, trial_end,
                        website_url or "N/A", company_email),
                    from_email=None,
                    recipient_list=[email],
                )
            except Exception:
                pass

            return redirect("registration:register_success")

        except Exception as e:
            logger.exception("Self-service registration error")
            messages.error(request, "Greska pri registraciji: {}".format(e))
            return redirect("registration:register_step4")

    return render(request, "registration/step4.html", {
        "step": 4,
        "plan": plan,
        "company": company_data,
        "user": user_data,
    })


def register_success(request):
    context = {
        "website_url": request.session.pop("reg_success_website_url", ""),
        "company_email": request.session.pop("reg_success_company_email", ""),
        "company_name": request.session.pop("reg_success_company_name", ""),
        "plan_name": request.session.pop("reg_success_plan_name", ""),
        "trial_end": request.session.pop("reg_success_trial_end", ""),
    }
    return render(request, "registration/success.html", context)


def upgrade_required(request):
    module = request.GET.get('module', '')
    return render(request, 'registration/upgrade_required.html', {'module': module, 'plans': PLAN_FEATURES})


def is_superadmin(user):
    return user.is_active and user.is_staff


@login_required
@user_passes_test(is_superadmin)
def admin_registration_list(request):
    status_filter = request.GET.get('status', 'pending')
    registrations = CompanyRegistration.objects.all()
    if status_filter in ('pending', 'approved', 'rejected'):
        registrations = registrations.filter(status=status_filter)
    counts = {
        'pending': CompanyRegistration.objects.filter(status='pending').count(),
        'approved': CompanyRegistration.objects.filter(status='approved').count(),
        'rejected': CompanyRegistration.objects.filter(status='rejected').count(),
    }
    return render(request, 'registration/admin_list.html', {
        'registrations': registrations,
        'status_filter': status_filter,
        'counts': counts,
    })


@login_required
@user_passes_test(is_superadmin)
def admin_registration_detail(request, pk):
    reg = get_object_or_404(CompanyRegistration, pk=pk)
    return render(request, 'registration/admin_detail.html', {'reg': reg, 'plans': PLAN_FEATURES})


@login_required
@user_passes_test(is_superadmin)
@require_POST
def admin_approve_registration(request, pk):
    reg = get_object_or_404(CompanyRegistration, pk=pk)
    if reg.status != CompanyRegistration.PENDING:
        messages.warning(request, 'Registration is already {}.'.format(reg.status))
        return redirect('registration:admin_list')
    try:
        from accounts.models import UserProfile
        from companies.models import Company
        company_fields = [f.name for f in Company._meta.get_fields()]
        country_map = {'Croatia': 'HR', 'Germany': 'DE', 'Austria': 'AT', 'Slovenia': 'SI', 'Bosnia': 'BA', 'Serbia': 'RS'}
        country_code = country_map.get(reg.country, 'OTHER')
        btype_map = {'doo': 'doo', 'jdoo': 'jdoo', 'obrt': 'obrt', 'dd': 'dd', 'sp': 'other', 'eu': 'other', 'other': 'other'}
        btype = btype_map.get(reg.business_type, 'other')
        company_kwargs = {'name': reg.name, 'oib': reg.oib}
        if 'country' in company_fields:
            company_kwargs['country'] = country_code
        if 'address' in company_fields:
            company_kwargs['address'] = reg.address
        if 'business_type' in company_fields:
            company_kwargs['business_type'] = btype
        company = Company.objects.create(**company_kwargs)
        base_un = reg.contact_email.split('@')[0].lower().replace('.', '_')[:30]
        username = base_un
        counter = 1
        while User.objects.filter(username=username).exists():
            username = '{}{}'.format(base_un, counter)
            counter += 1
        temp_pw = User.objects.make_random_password(length=12)
        name_parts = reg.contact_name.strip().split(None, 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        user = User.objects.create_user(
            username=username, email=reg.contact_email, password=temp_pw,
            first_name=first_name, last_name=last_name,
        )
        UserProfile.objects.create(user=user, company=company, role='company_admin')
        # Create RBAC role for permissions
        try:
            from permissions.models import Role, UserRole
            admin_role = Role.objects.get(role_type='company_admin')
            UserRole.objects.get_or_create(
                user=user, role=admin_role, company=company,
                defaults={'is_primary': True}
            )
        except Exception:
            pass
        fees = {'starter': Decimal('29.00'), 'business': Decimal('59.00'), 'enterprise': Decimal('99.00')}
        CompanySubscription.objects.create(
            company=company, plan=reg.selected_plan, valid_from=date.today(),
            monthly_fee=fees.get(reg.selected_plan, Decimal('29.00')), is_active=True,
        )
        reg.status = CompanyRegistration.APPROVED
        reg.approved_at = now()
        reg.reviewed_by = request.user
        reg.save()
        _send_approval_email(reg, username, temp_pw)

        # Auto-create website and generate company email
        website = _auto_create_website(company)
        company_email = _generate_company_email(company)

        messages.success(request, 'Approved: {}. Account created for {}.'.format(reg.name, reg.contact_email))
    except Exception as e:
        logger.exception('Error approving registration %s', pk)
        messages.error(request, 'Error during approval: {}'.format(e))
    return redirect('registration:admin_list')


@login_required
@user_passes_test(is_superadmin)
@require_POST
def admin_reject_registration(request, pk):
    reg = get_object_or_404(CompanyRegistration, pk=pk)
    if reg.status != CompanyRegistration.PENDING:
        messages.warning(request, 'Registration is already {}.'.format(reg.status))
        return redirect('registration:admin_list')
    reason = request.POST.get('rejection_reason', '').strip()
    reg.status = CompanyRegistration.REJECTED
    reg.rejection_reason = reason
    reg.reviewed_by = request.user
    reg.save()
    _send_rejection_email(reg, reason)
    messages.warning(request, 'Registration for {} rejected.'.format(reg.name))
    return redirect('registration:admin_list')


def _notify_admins_new_registration(reg):
    try:
        from django.conf import settings
        admin_emails = [email for _, email in getattr(settings, 'ADMINS', [])]
        if not admin_emails:
            admin_emails = [getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@limit-connect.com')]
        send_email_task.delay(
            subject='[LIMIT Connect] New registration: {}'.format(reg.name),
            message='New registration: {}\\nOIB: {}\\nCountry: {}\\nPlan: {}\\nContact: {} <{}>Phone: {}'.format(
                reg.name, reg.oib, reg.country, reg.selected_plan.upper(), reg.contact_name, reg.contact_email, reg.contact_phone),
            from_email=None, recipient_list=admin_emails,
        )
    except Exception:
        logger.exception('Failed to notify admins of new registration')


def _send_approval_email(reg, username, temp_password):
    try:
        send_email_task.delay(
            subject='[LIMIT Connect] Your account has been approved!',
            message='Dear {},\\n\\nAccount for {} approved.\\n\\nUsername: {}\\nPassword: {}\\nPlan: {}\\n\\nLogin: https://limit-connect.com/accounts/login/'.format(
                reg.contact_name, reg.name, username, temp_password, reg.selected_plan.upper()),
            from_email=None, recipient_list=[reg.contact_email],
        )
    except Exception:
        logger.exception('Failed to send approval email')


def _send_rejection_email(reg, reason):
    try:
        reason_text = 'Reason: {}\\n\\n'.format(reason) if reason else ''
        send_email_task.delay(
            subject='[LIMIT Connect] Registration update',
            message='Dear {},\\n\\nYour registration for {} could not be approved.\\n\\n{}Contact: info@limit-connect.com'.format(
                reg.contact_name, reg.name, reason_text),
            from_email=None, recipient_list=[reg.contact_email],
        )
    except Exception:
        logger.exception('Failed to send rejection email')

def api_check_promo(request):
    """API endpoint za provjeru promo koda (AJAX)."""
    from django.http import JsonResponse

    from .models import PromoCode
    code = request.GET.get('code', '').strip().upper()
    if not code:
        return JsonResponse({'valid': False, 'error': 'Unesite kod'})
    try:
        promo = PromoCode.objects.get(code=code)
    except PromoCode.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'Kod ne postoji'})
    if not promo.is_valid():
        return JsonResponse({'valid': False, 'error': 'Kod je istekao ili iskorišten'})
    descriptions = {
        'discount_percent': f'{promo.discount_percent}% popusta na pretplatu',
        'discount_fixed':   f'{promo.discount_amount} EUR popusta',
        'free_months':      f'{promo.free_months} mjesec(i) besplatno',
        'plan_upgrade':     f'Upgrade na {promo.target_plan} plan',
        'full_access':      'Puni pristup svim modulima',
    }
    return JsonResponse({
        'valid': True,
        'type': promo.promo_type,
        'description': descriptions.get(promo.promo_type, promo.name),
    })



# -- Umbrella Invite Code Management --

@login_required
def umbrella_invite_manage(request):
    """Umbrella admin manages invite codes."""
    from .models import UmbrellaInviteCode
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company or not company.is_umbrella:
        from django.contrib import messages as msg
        msg.error(request, 'Samo umbrella tvrtke mogu upravljati pozivnim kodovima.')
        return redirect('/dashboard/')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'create':
            code = UmbrellaInviteCode.generate_code()
            UmbrellaInviteCode.objects.create(
                umbrella_company=company,
                code=code,
                plan_slug=request.POST.get('plan', 'starter'),
                relation_type=request.POST.get('relation', 'client'),
                max_uses=int(request.POST.get('max_uses', 1)),
                free_months=int(request.POST.get('free_months', 1)),
                note=request.POST.get('note', ''),
                created_by=request.user,
            )
            from django.contrib import messages as msg
            msg.success(request, 'Pozivni kod %s kreiran!' % code)
        elif action == 'deactivate':
            code_id = request.POST.get('code_id', '')
            UmbrellaInviteCode.objects.filter(
                id=code_id, umbrella_company=company
            ).update(is_active=False)
            from django.contrib import messages as msg
            msg.info(request, 'Kod deaktiviran.')
        return redirect('registration:umbrella_invites')

    codes = UmbrellaInviteCode.objects.filter(umbrella_company=company)
    return render(request, 'registration/umbrella_invites.html', {
        'codes': codes,
        'company': company,
    })


# ─── Sales Wizard ───────────────────────────────────────────────────

@login_required
def sales_wizard(request):
    """Sales wizard — step-by-step client onboarding."""
    lang = request.GET.get('lang', 'hr')
    from registration.models import SalesLead
    leads = SalesLead.objects.filter(agent=request.user).order_by('-created_at')[:10]

    plans = {
        'micro': {'name': 'Micro', 'price': 8, 'users': 1},
        'starter': {'name': 'Starter', 'price': 18, 'users': 3},
        'professional': {'name': 'Professional', 'price': 58, 'users': 10},
        'enterprise': {'name': 'Enterprise', 'price': 158, 'users': 50},
    }

    ref = request.GET.get('ref', '')

    return render(request, 'registration/sales_wizard.html', {
        'lang': lang, 'plans': plans, 'leads': leads, 'ref': ref,
    })


@login_required
@require_POST
def sales_wizard_submit(request):
    """Submit signed sales lead."""
    import json, base64, os
    from django.http import JsonResponse
    from django.utils import timezone as tz
    from registration.models import SalesLead

    data = json.loads(request.body)

    # ── AI Validation per step ──
    errors = []
    company_name = data.get('company_name', '').strip()
    oib = data.get('oib', '').strip()
    contact_name = data.get('contact_name', '').strip()
    contact_phone = data.get('contact_phone', '').strip()
    country = data.get('country', 'HR')

    if not company_name:
        errors.append('Naziv tvrtke je obavezan' if country != 'DE' else 'Firmenname ist erforderlich')
    if not contact_name:
        errors.append('Ime kontakta je obavezno' if country != 'DE' else 'Kontaktname ist erforderlich')
    if not contact_phone:
        errors.append('Telefon je obavezan' if country != 'DE' else 'Telefonnummer ist erforderlich')
    if country == 'HR' and oib and len(oib) != 11:
        errors.append('OIB mora imati 11 znamenki')
    if country == 'DE' and oib and len(oib) < 10:
        errors.append('Steuernummer ist zu kurz')

    # Duplicate check
    from registration.models import SalesLead
    if oib and SalesLead.objects.filter(oib=oib, status__in=['signed', 'active']).exists():
        errors.append('Klijent s ovim OIB-om vec postoji' if country != 'DE' else 'Kunde mit dieser Steuernummer existiert bereits')
    if company_name and SalesLead.objects.filter(company_name__iexact=company_name, status__in=['signed', 'active']).exists():
        errors.append('Tvrtka s ovim imenom vec postoji' if country != 'DE' else 'Firma mit diesem Namen existiert bereits')

    if errors:
        return JsonResponse({'ok': False, 'errors': errors}, status=400)

    # Audit trail
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')

    # Prepare notes with ref code if present
    notes_text = data.get('notes', '')
    ref_code_val = data.get('ref_code', '')
    if ref_code_val:
        notes_text = 'REF: %s | %s' % (ref_code_val, notes_text)

    lead = SalesLead.objects.create(
        company_name=data.get('company_name', ''),
        oib=data.get('oib', ''),
        contact_name=data.get('contact_name', ''),
        contact_email=data.get('contact_email', ''),
        contact_phone=data.get('contact_phone', ''),
        address=data.get('address', ''),
        city=data.get('city', ''),
        country=data.get('country', 'HR'),
        business_type=data.get('business_type', 'obrt'),
        plan=data.get('plan', 'professional'),
        modules=data.get('modules', []),
        signature_b64=data.get('signature', ''),
        signed_at=tz.now() if data.get('signature') else None,
        signed_by=data.get('contact_name', ''),
        status='signed' if data.get('signature') else 'draft',
        agent=request.user,
        notes=notes_text,
        ref_code=ref_code_val,
    )

    if data.get('signature'):
        sig_dir = '/var/www/fina-connect/media/signatures'
        os.makedirs(sig_dir, exist_ok=True)
        sig_data = data['signature']
        if ',' in sig_data:
            sig_data = sig_data.split(',')[1]
        with open(os.path.join(sig_dir, f'sales_{lead.pk}.png'), 'wb') as f:
            f.write(base64.b64decode(sig_data))

    # Audit trail to superdashboard
    try:
        from superadmin_ai.models import PendingAIAction
        PendingAIAction.objects.create(
            company=None,
            module='sales_wizard',
            action_type='new_lead',
            description='Novi klijent: %s (%s) — plan: %s — agent: %s' % (
                lead.company_name, lead.country, lead.plan, request.user.username,
            ),
            payload={
                'lead_id': lead.pk,
                'company': lead.company_name,
                'oib': lead.oib,
                'country': lead.country,
                'plan': lead.plan,
                'agent': request.user.username,
                'client_ip': client_ip,
                'signed': bool(lead.signature_b64),
            },
            status='pending',
        )
    except Exception:
        pass

    # Email to client
    if lead.contact_email:
        try:
            from django.core.mail import send_mail
            lang_code = data.get('country', 'HR')
            if lang_code == 'DE':
                subject = 'Willkommen bei LIMIT Connect!'
                body = 'Sehr geehrte(r) %s,\n\nIhr LIMIT Connect Konto wird aktiviert.\n\nZugang: https://limit-connect.com\nIhr Berater: %s\n\nBei Fragen: +385 97 609 1655\n\nMit freundlichen Gruessen,\nLIMIT Connect Team' % (lead.contact_name, request.user.get_full_name() or request.user.username)
            else:
                subject = 'Dobrodosli u LIMIT Connect!'
                body = 'Postovani %s,\n\nVas LIMIT Connect racun se aktivira.\n\nPristup: https://limit-connect.com\nVas savjetnik: %s\n\nZa pitanja: +385 97 609 1655\n\nSrdacan pozdrav,\nLIMIT Connect tim' % (lead.contact_name, request.user.get_full_name() or request.user.username)
            send_mail(subject, body, None, [lead.contact_email], fail_silently=True)
        except Exception:
            pass

    # WhatsApp to client
    if lead.contact_phone:
        try:
            from core.whatsapp import send_text
            lang_code2 = data.get('country', 'HR')
            if lang_code2 == 'DE':
                wa_msg = 'Willkommen bei LIMIT Connect, %s! Ihr Konto wird aktiviert. Zugang: limit-connect.com. Berater: %s' % (lead.contact_name, request.user.get_full_name() or request.user.username)
            else:
                wa_msg = 'Dobrodosli u LIMIT Connect, %s! Vas racun se aktivira. Pristup: limit-connect.com. Savjetnik: %s' % (lead.contact_name, request.user.get_full_name() or request.user.username)
            send_text(lead.contact_phone, wa_msg)
        except Exception:
            pass

    return JsonResponse({
        'ok': True,
        'lead_id': lead.pk,
        'message': 'Klijent registriran!' if data.get('country') != 'DE' else 'Kunde registriert!',
    })


@login_required
def agent_dashboard(request):
    """Agent referral dashboard with QR code and commission stats."""
    from registration.models import SalesLead
    from decimal import Decimal

    leads = SalesLead.objects.filter(agent=request.user).order_by('-created_at')

    active = leads.filter(status='active').count()
    signed = leads.filter(status='signed').count()
    draft = leads.filter(status='draft').count()
    total = leads.count()

    # Commission calculation
    plan_prices = {'micro': 8, 'starter': 18, 'professional': 58, 'enterprise': 158}
    monthly_revenue = sum(
        plan_prices.get(l.plan, 0) for l in leads.filter(status='active')
    )
    commission_rate = Decimal('0.15')
    monthly_commission = Decimal(str(monthly_revenue)) * commission_rate

    # Generate unique ref code for this agent
    ref_code = 'REF-%s' % request.user.username.upper()[:8]
    wizard_url = request.build_absolute_uri('/hr/register/sales-wizard/?ref=%s' % ref_code)

    return render(request, 'registration/agent_dashboard.html', {
        'leads': leads[:20],
        'active': active, 'signed': signed, 'draft': draft, 'total': total,
        'monthly_revenue': monthly_revenue,
        'monthly_commission': monthly_commission,
        'ref_code': ref_code,
        'wizard_url': wizard_url,
    })


# ── OIB Auto-Lookup API ─────────────────────────────────────────────
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def api_oib_lookup(request):
    """AJAX endpoint: lookup company by OIB from internal DB or sudski registar.

    GET /registration/api/oib-lookup/?oib=12345678901&country=HR
    Returns JSON: {found, name, address, city, zip_code, legal_form}
    """
    oib = (request.GET.get('oib') or '').strip()
    country = (request.GET.get('country') or 'HR').strip().upper()

    if not oib:
        return JsonResponse({'found': False, 'error': 'OIB prazan'})

    # Validate format
    if country == 'HR' and (len(oib) != 11 or not oib.isdigit()):
        return JsonResponse({'found': False, 'error': 'OIB mora imati 11 znamenki'})

    if country == 'DE' and len(oib) < 8:
        return JsonResponse({'found': False, 'error': 'Porezni broj prekratak'})

    # 1. Check internal database first
    from companies.models import Company
    try:
        company = Company.objects.filter(oib=oib).first()
        if company:
            return JsonResponse({
                'found': True,
                'source': 'internal',
                'name': company.name,
                'address': company.address,
                'city': company.city,
                'zip_code': company.zip_code,
                'legal_form': company.business_type,
                'message': 'Tvrtka je vec u sustavu — kontaktirajte podrsku za pristup.',
                'existing': True,
            })
    except Exception:
        pass

    # 2. Try sudski registar (sudreg) for HR companies
    if country == 'HR':
        result = _lookup_sudreg(oib)
        if result:
            return JsonResponse({
                'found': True,
                'source': 'sudreg',
                'existing': False,
                **result,
            })

    return JsonResponse({'found': False})


def _lookup_sudreg(oib):
    """Try to lookup company in Croatian court register via OIB."""
    import requests as _req

    # Try the open sudski registar API
    try:
        url = 'https://sudreg-api.pravosudje.hr/javni/subjekt_detalji'
        params = {'oib': oib, 'expand_relations': 'false'}
        headers = {'Accept': 'application/json'}
        resp = _req.get(url, params=params, headers=headers, timeout=5)

        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                subj = data[0]
                return {
                    'name': subj.get('tvrtka', subj.get('ime', '')),
                    'address': subj.get('sjediste_adresa', ''),
                    'city': subj.get('sjediste_grad', ''),
                    'zip_code': subj.get('sjediste_posta', ''),
                    'legal_form': subj.get('pravni_oblik', ''),
                }
            elif isinstance(data, dict) and data.get('tvrtka'):
                return {
                    'name': data.get('tvrtka', ''),
                    'address': data.get('sjediste_adresa', ''),
                    'city': data.get('sjediste_grad', ''),
                    'zip_code': data.get('sjediste_posta', ''),
                    'legal_form': data.get('pravni_oblik', ''),
                }
    except Exception as e:
        logger.debug('Sudreg lookup failed for OIB %s: %s', oib[:4], e)

    # Fallback: try FINA / biznet
    try:
        url = 'https://api.data.gov.hr/registar-poslovnih-subjekata/v2/subjekti'
        params = {'oib': oib}
        resp = _req.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', data) if isinstance(data, dict) else data
            if isinstance(items, list) and items:
                subj = items[0]
                return {
                    'name': subj.get('naziv', subj.get('ime', '')),
                    'address': subj.get('adresa', ''),
                    'city': subj.get('mjesto', ''),
                    'zip_code': subj.get('posta', ''),
                    'legal_form': subj.get('oblik', ''),
                }
    except Exception as e:
        logger.debug('Data.gov.hr lookup failed for OIB %s: %s', oib[:4], e)

    return None


def api_name_search(request):
    """
    Pretraga po nazivu — traži u Company + Partner (Marijini komitenti).
    Bruno upiše "Valiant" → nađe u Partner tablici → auto-fill.
    """
    from django.http import JsonResponse
    from companies.models import Company
    from partners.models import Partner
    from django.db.models import Q

    q = request.GET.get('q', '').strip()
    if len(q) < 3:
        return JsonResponse({'results': []})

    seen = set()
    results = []

    # 1. Postojeće firme (Company)
    for r in Company.objects.filter(name__icontains=q).values('name', 'oib', 'address', 'city', 'zip_code')[:4]:
        key = (r['name'], r['oib'] or '')
        if key not in seen:
            seen.add(key)
            results.append({
                'name': r['name'], 'oib': r['oib'] or '',
                'address': r['address'] or '', 'city': r['city'] or '',
                'zip': r['zip_code'] or '', 'source': 'company',
            })

    # 2. Partneri (Marijina baza komitenata) — 33K+ zapisa
    for p in Partner.objects.filter(name__icontains=q).values('name', 'oib', 'address', 'city', 'zip_code').distinct()[:6]:
        key = (p['name'], p['oib'] or '')
        if key not in seen:
            seen.add(key)
            results.append({
                'name': p['name'], 'oib': p['oib'] or '',
                'address': p['address'] or '', 'city': p['city'] or '',
                'zip': p['zip_code'] or '', 'source': 'partner',
            })

    return JsonResponse({'results': results[:8]})
