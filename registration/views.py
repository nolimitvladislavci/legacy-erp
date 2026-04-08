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

        # 3 demo items — quantity=0, realne cijene, jasno oznaceni
        for name, sku, price, cat in [
            ('(Demo) Artikl - uredite ili obrisite', 'DEMO-A1', 1.00, 'product'),
            ('(Demo) Usluga - uredite ili obrisite', 'DEMO-U1', 25.00, 'service'),
            ('(Demo) Materijal - uredite ili obrisite', 'DEMO-M1', 0.50, 'material'),
        ]:
            InventoryItem.objects.get_or_create(
                company=company, sku=sku,
                defaults={'name': name, 'unit_price': price, 'quantity': 0, 'category': cat}
            )

        # Auto-seed porezne stope po zemlji (globalne, ne per-company)
        from companies.models import TaxRate
        country = getattr(company, 'country', 'HR') or 'HR'
        if not TaxRate.objects.filter(country=country).exists():
            if country in ('DE', 'AT'):
                for name, rate in [('PDV 19% (Standard)', 19), ('PDV 7% (Snižena)', 7), ('PDV 0% (Oslobođeno)', 0)]:
                    TaxRate.objects.get_or_create(country=country, rate=rate, defaults={'name': name})
            elif country == 'SI':
                for name, rate in [('DDV 22%', 22), ('DDV 9.5%', 9.5), ('Oproščeno', 0)]:
                    TaxRate.objects.get_or_create(country=country, rate=rate, defaults={'name': name})
            else:  # HR default
                for name, rate in [('PDV 25%', 25), ('PDV 13%', 13), ('PDV 5%', 5), ('Oslobođeno 0%', 0)]:
                    TaxRate.objects.get_or_create(country=country, rate=rate, defaults={'name': name})

        # Mark onboarding steps
        from companies.models import OnboardingProgress
        onb, _ = OnboardingProgress.objects.get_or_create(company=company)
        onb.first_partner_added = True
        onb.first_item_added = True
        onb.save(update_fields=['first_partner_added', 'first_item_added', 'updated_at'])

        # Auto-kreiraj vlasnika kao blagajnika (PIN 1234 — korisnik mijenja)
        try:
            from pos.models import POSCashier
            cashier_name = (user.get_full_name() or user.username).strip()
            cashier, _ = POSCashier.objects.get_or_create(
                company=company, user=user,
                defaults={
                    'name': cashier_name,
                    'can_void': True,
                    'can_discount': True,
                    'max_discount_percent': 100,
                    'is_active': True,
                    'oib': '',
                }
            )
            cashier.set_pin('1234')
            cashier.save(update_fields=['pin_hash'])
        except Exception as _ce:
            logger.warning("POSCashier seed failed: %s", _ce)

        logger.info("Seeded demo data for %s", company.name)
    except Exception as e:
        logger.warning("Demo data seeding failed for %s: %s", company.name, e)




def register_step2_combined(request):
    """Step 2 (3-klik): Company + User combined — OIB auto-fill via AJAX."""
    if not request.session.get("reg_plan"):
        return redirect("registration:register_step1")

    INDUSTRY_CHOICES = [
        ("it", "IT i softver"),
        ("trade", "Trgovina"),
        ("services", "Usluge"),
        ("gastro", "Ugostiteljstvo"),
        ("construction", "Graditeljstvo"),
        ("health", "Zdravstvo"),
        ("agriculture", "Poljoprivreda"),
        ("nonprofit", "Udruga / Neprofitno"),
        ("other", "Ostalo"),
    ]

    if request.method == "POST":
        import re as _re
        # Company data
        company_data = {
            "name": request.POST.get("name", "").strip(),
            "oib": request.POST.get("oib", "").strip(),
            "country": request.POST.get("country", "HR"),
            "address": request.POST.get("address", "").strip(),
            "city": request.POST.get("city", "").strip(),
            "zip_code": request.POST.get("zip_code", "").strip(),
            "industry": request.POST.get("industry", "other"),
        }
        # User data
        user_data = {
            "first_name": request.POST.get("first_name", "").strip(),
            "last_name": request.POST.get("last_name", "").strip(),
            "email": request.POST.get("email", "").strip(),
            "phone": request.POST.get("phone", "").strip(),
        }
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")

        errors = {}
        # Company validation
        if not company_data["name"]:
            errors["name"] = "Naziv tvrtke je obavezan."
        if not company_data["oib"]:
            errors["oib"] = "OIB / Porezni broj je obavezan."
        elif company_data["country"] == "HR" and not _re.match(r'^\d{11}$', company_data["oib"]):
            errors["oib"] = "Hrvatski OIB mora imati točno 11 znamenki."

        # User validation — first_name auto-fill iz email prefiksa ako prazno
        if not user_data["first_name"] and user_data.get("email"):
            user_data["first_name"] = user_data["email"].split("@")[0].replace(".", " ").title()
        if not user_data["email"]:
            errors["email"] = "Email je obavezan."
        elif User.objects.filter(email=user_data["email"]).exists():
            # Pametna poruka — nudi login ili reset, ne ostavlja korisnika u slijepoj ulici
            existing_user = User.objects.filter(email=user_data["email"]).first()
            has_company = hasattr(existing_user, 'profile') and existing_user.profile.company_id if existing_user else False
            if has_company:
                errors["email"] = (
                    '⚠️ Već imate račun s ovom email adresom. '
                    '<a href="/hr/login/" style="color:#c9a84c;font-weight:700">→ Prijavite se</a> '
                    'ili <a href="/password-reset/" style="color:#c9a84c;">zaboravili ste lozinku?</a>'
                )
            else:
                errors["email"] = (
                    '⚠️ Ova email adresa je zauzeta. '
                    '<a href="/hr/login/" style="color:#c9a84c;font-weight:700">→ Prijavite se</a> '
                    'ili <a href="/password-reset/" style="color:#c9a84c;">resetirajte lozinku</a>.'
                )
        if len(password1) < 8:
            errors["password1"] = "Lozinka mora imati najmanje 8 znakova."
        elif not any(c.isupper() for c in password1):
            errors["password1"] = "Lozinka mora sadržavati barem jedno veliko slovo."
        elif not any(c.isdigit() for c in password1):
            errors["password1"] = "Lozinka mora sadržavati barem jednu znamenku."
        if password1 != password2:
            errors["password2"] = "Lozinke se ne podudaraju."

        if errors:
            return render(request, "registration/step2_combined.html", {
                "step": 2, "company": company_data, "user": user_data,
                "errors": errors, "industries": INDUSTRY_CHOICES,
            })

        request.session["reg_company"] = company_data
        request.session["reg_user"] = user_data
        request.session["reg_password"] = password1
        return redirect("registration:register_step3")

    company_data = request.session.get("reg_company", {})
    user_data = request.session.get("reg_user", {})
    # Pre-fill industry from pricing profile
    profile = request.session.get("reg_profile", "")
    PROFILE_INDUSTRY = {
        "obrtnik": "services", "udruga": "nonprofit", "rental": "services",
        "firma": "services", "racunovodja": "services", "gastro": "gastro",
        "opg": "agriculture",
    }
    if profile and not company_data.get("industry"):
        company_data["industry"] = PROFILE_INDUSTRY.get(profile, "other")
    return render(request, "registration/step2_combined.html", {
        "step": 2, "company": company_data, "user": user_data,
        "errors": {}, "industries": INDUSTRY_CHOICES,
        "profile": profile,
    })


def register_step3_confirm(request):
    """Step 3 (3-klik): Review + T&C + Create — replaces old step4."""
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
        # T&C acceptance check
        if not request.POST.get("tc_accept"):
            messages.error(request, "Morate prihvatiti uvjete korištenja.")
            return render(request, "registration/step3_confirm.html", {
                "step": 3, "plan": plan, "company": company_data,
                "user": user_data, "tc_error": True,
            })
        # Delegate to existing step4 logic via session and redirect
        return register_step4(request)

    return render(request, "registration/step3_confirm.html", {
        "step": 3, "plan": plan, "company": company_data, "user": user_data,
    })


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
    # Auto-select plan from URL param (from landing/pricing page "Odaberi" buttons)
    plan_param = request.GET.get("plan", "")
    if plan_param and plans.filter(slug=plan_param).exists():
        request.session["reg_plan"] = plan_param
        # Profile from pricing page (obrtnik, udruga, gastro, etc.)
        profile_param = request.GET.get("profile", "")
        if profile_param:
            request.session["reg_profile"] = profile_param
        source = request.GET.get("source", "")
        if source:
            request.session["reg_source"] = source
        return redirect("registration:register_step2")
    source = request.GET.get("source", "")
    if source:
        request.session["reg_source"] = source
    pet_name = request.GET.get('pet', '') or request.session.get('memio_pet', '')
    if pet_name:
        request.session['memio_pet'] = pet_name
    source = request.GET.get("source", "") or request.session.get("reg_source", "")
    return render(request, "registration/step1.html", {
        "step": 1, "plans": plans, "pet_name": pet_name, "source": source,
    })


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
        from django.db import transaction

        from accounts.models import UserProfile
        from companies.models import Company

        try:
          with transaction.atomic():
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
            for key in ["reg_plan", "reg_company", "reg_user", "reg_password", "reg_promo_code", "reg_source", "reg_profile", "reg_invite_code", "reg_invite_umbrella", "reg_invite_relation", "reg_invite_modules", "reg_invite_free_months"]:
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

            if plan.price_monthly > 0:
                messages.success(request, "Dobrodosli u LIMIT Connect! Vas trial traje do {}.".format(trial_end.strftime("%d.%m.%Y")))
            else:
                messages.success(request, "Dobrodosli u LIMIT Connect! Vas besplatni plan je aktiviran.")

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
        btype_map = {'doo': 'doo', 'jdoo': 'jdoo', 'obrt': 'obrt', 'dd': 'dd', 'sp': 'other', 'eu': 'other', 'udruga': 'udruga', 'zadruga': 'zadruga', 'ustanova': 'ustanova', 'opg': 'opg', 'gmbh': 'gmbh', 'ag': 'ag', 'einzelunternehmen': 'einzelunternehmen', 'other': 'other'}
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
    """Agent referral dashboard 10/10 — KPI, QR, ghost firme, komisija."""
    from registration.models import SalesLead
    from companies.models import Company
    from decimal import Decimal
    import qrcode, io, base64

    leads = SalesLead.objects.filter(agent=request.user).select_related('company').order_by('-created_at')

    # Ghost firme (Company bez korisnika)
    ghost_companies = Company.objects.filter(
        users__isnull=True,
    ).order_by('name')[:50]

    # Komisija
    plan_prices = {'micro': 8, 'starter': 18, 'professional': 58, 'enterprise': 158}
    active_leads = leads.filter(status='active')
    monthly_revenue = sum(plan_prices.get(l.plan, 29) for l in active_leads)
    commission_rate = Decimal('0.15')
    monthly_commission = Decimal(str(monthly_revenue)) * commission_rate

    # Ref kod i invite URL
    ref_code = f'REF-{request.user.username.upper()[:8]}'
    invite_url = request.build_absolute_uri(f'/pocni/?ref={ref_code}')

    # QR kod (base64 PNG)
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(invite_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill='black', back_color='white')
    buffer = io.BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_b64 = base64.b64encode(buffer.getvalue()).decode()

    stats = {
        'total': leads.count(),
        'active': active_leads.count(),
        'ghost': ghost_companies.count(),
        'signed': leads.filter(status='signed').count(),
        'monthly_revenue': monthly_revenue,
        'monthly_commission': float(monthly_commission),
        'yearly_commission': float(monthly_commission * 12),
    }

    bulk_msg = (
        f"Pozivam vas na LIMIT Connect — ERP za upravljanje poslovanjem. "
        f"14 dana besplatno: {invite_url}"
    )

    # Ambassador detection
    is_ambassador = leads.filter(is_disability_ambassador=True).exists() or                     SalesLead.objects.filter(agent=request.user, is_disability_ambassador=True).exists()

    return render(request, 'registration/agent_dashboard_v2.html', {
        'leads': leads[:30],
        'ghost_companies': ghost_companies,
        'stats': stats,
        'ref_code': ref_code,
        'invite_url': invite_url,
        'qr_b64': qr_b64,
        'bulk_msg': bulk_msg,
        'is_ambassador': is_ambassador,
        'page_title': 'Moji klijenti',
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
            from accounts.models import UserProfile
            has_owner = UserProfile.objects.filter(company=company).exists()
            return JsonResponse({
                'found': True,
                'source': 'internal',
                'name': company.name,
                'address': company.address or '',
                'city': getattr(company, 'city', '') or '',
                'zip_code': getattr(company, 'zip_code', '') or '',
                'legal_form': company.business_type,
                'existing': True,
                'has_owner': has_owner,
                'can_claim': not has_owner,
                'claim_url': f'/firma/preuzmi/{company.id}/' if not has_owner else '',
                'message': (
                    'Ova firma već ima administratora u sustavu. Kontaktirajte podršku.'
                    if has_owner else
                    'Ova firma je u sustavu. Možete zatražiti pristup vlastitim podacima.'
                ),
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


# ════════════════════════════════════════════════════════════════════
# Claim Your Business — views
# ════════════════════════════════════════════════════════════════════

def claim_company_form(request, company_id):
    """GET /firma/preuzmi/<uuid>/ — vlasnik traži pristup ghost firmi."""
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanyClaimRequest

    company = get_object_or_404(Company, id=company_id)

    if UserProfile.objects.filter(company=company).exists():
        messages.warning(request, 'Ova firma već ima aktivnog administratora.')
        return redirect('home')

    pending = CompanyClaimRequest.objects.filter(company=company, status='pending').exists()

    # Statistika za prikaz
    stats = {
        'invoices': 0, 'partners': 0, 'journals': 0,
    }
    try:
        from invoicing.models import Invoice
        stats['invoices'] = Invoice.objects.filter(company=company).count()
    except Exception:
        pass
    try:
        from partners.models import Partner
        stats['partners'] = Partner.objects.filter(company=company).count()
    except Exception:
        pass
    try:
        from konto.models import JournalEntry
        stats['journals'] = JournalEntry.objects.filter(company=company).count()
    except Exception:
        pass

    return render(request, 'registration/claim_company.html', {
        'company': company,
        'pending': pending,
        'stats': stats,
    })


def submit_claim(request, company_id):
    """POST /firma/preuzmi/<uuid>/submit/ — kreira ClaimRequest."""
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanyClaimRequest
    from django.utils import timezone

    if request.method != 'POST':
        return redirect('claim_company', company_id=company_id)

    company = get_object_or_404(Company, id=company_id)

    if UserProfile.objects.filter(company=company).exists():
        return JsonResponse({'error': 'Firma već ima administratora.'}, status=400)

    email = request.POST.get('email', '').strip()
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    phone = request.POST.get('phone', '').strip()

    if not email or not first_name:
        messages.error(request, 'Email i ime su obavezni.')
        return redirect('claim_company', company_id=company_id)

    if CompanyClaimRequest.objects.filter(email=email, company=company, status='pending').exists():
        messages.info(request, 'Vaš zahtjev je već poslan. Čekajte odobrenje.')
        return redirect('claim_company', company_id=company_id)

    claim = CompanyClaimRequest.objects.create(
        company=company,
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        oib_confirmed=True,
        token_expires=timezone.now() + timezone.timedelta(days=7),
        ip_address=request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR'),
    )

    # WhatsApp obavijest
    try:
        from core.whatsapp import send_text
        approve_url = f'https://limit-connect.com/hr/firma/odobri/{claim.id}/'
        send_text(
            phone='+385921104615',
            message=(
                f'📋 ZAHTJEV ZA PRISTUP\n'
                f'Firma: {company.name}\n'
                f'OIB: {company.oib}\n'
                f'Kontakt: {first_name} {last_name} | {email}\n'
                f'\n✅ Odobri: {approve_url}'
            ),
        )
    except Exception:
        pass

    messages.success(request,
        f'Zahtjev je poslan! Administrator će vas kontaktirati u roku 24 sata. '
        f'Login podaci bit će poslani na {email}.'
    )
    return render(request, 'registration/claim_success.html', {'company': company, 'email': email})


def activate_via_invite(request, token):
    """GET/POST /firma/aktiviraj/<token>/ — vlasnik klikne invite link."""
    from registration.models import CompanyClaimRequest

    claim = get_object_or_404(CompanyClaimRequest, verify_token=token)

    if not claim.is_token_valid:
        messages.error(request, 'Link je istekao ili nevažeći.')
        return redirect('home')

    if request.method == 'POST':
        password = request.POST.get('password1', '')
        if len(password) < 8:
            messages.error(request, 'Lozinka mora imati najmanje 8 znakova.')
            return render(request, 'registration/activate_invite.html', {'claim': claim})

        user, _ = claim.approve(reviewed_by=None)
        user.set_password(password)
        user.save()

        from django.contrib.auth import login
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Dobrodošli! Pristupili ste firmi {claim.company.name}.')
        return redirect('dashboard')

    return render(request, 'registration/activate_invite.html', {
        'claim': claim,
        'company': claim.company,
    })


@login_required
def approve_claim(request, claim_id):
    """GET/POST /firma/odobri/<uuid>/ — Marija odobrava/odbija."""
    from registration.models import CompanyClaimRequest

    claim = get_object_or_404(CompanyClaimRequest, id=claim_id, status='pending')

    if not (request.user.is_superuser or request.user.is_staff):
        try:
            if request.user.profile.company != claim.company.umbrella_parent:
                return HttpResponseForbidden('Nemate ovlast.')
        except Exception:
            return HttpResponseForbidden()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            user, temp_password = claim.approve(reviewed_by=request.user)

            # Email s login podacima
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                send_mail(
                    f'Pristup LIMIT Connect — {claim.company.name}',
                    f'Poštovani {claim.first_name},\n\n'
                    f'Vaš pristup firmi {claim.company.name} je odobren.\n\n'
                    f'Prijava: https://limit-connect.com/hr/login/\n'
                    f'Korisničko ime: {user.username}\n'
                    f'Privremena lozinka: {temp_password}\n\n'
                    f'Molimo promijenite lozinku pri prvoj prijavi.',
                    settings.DEFAULT_FROM_EMAIL,
                    [claim.email],
                    fail_silently=True,
                )
            except Exception:
                pass

            messages.success(request,
                f'✅ Odobreno! {claim.first_name} može se prijaviti. '
                f'Korisnik: {user.username} | Lozinka: {temp_password}')
            return redirect('pending_claims')

        elif action == 'reject':
            from django.utils import timezone
            claim.status = 'rejected'
            claim.reviewed_by = request.user
            claim.reviewed_at = timezone.now()
            claim.reject_reason = request.POST.get('reason', '')
            claim.save()
            messages.warning(request, 'Zahtjev odbijen.')
            return redirect('pending_claims')

    # Stats za firmu
    stats = {}
    try:
        from invoicing.models import Invoice
        stats['invoices'] = Invoice.objects.filter(company=claim.company).count()
        from partners.models import Partner
        stats['partners'] = Partner.objects.filter(company=claim.company).count()
    except Exception:
        pass

    return render(request, 'registration/approve_claim.html', {'claim': claim, 'stats': stats})


@login_required
def pending_claims(request):
    """GET /firma/zahtjevi/ — lista pending zahtjeva."""
    from registration.models import CompanyClaimRequest

    if not (request.user.is_superuser or request.user.is_staff):
        try:
            user_co = request.user.profile.company
            claims = CompanyClaimRequest.objects.filter(
                status='pending',
                company__umbrella_parent=user_co,
            ).select_related('company')
        except Exception:
            claims = CompanyClaimRequest.objects.none()
    else:
        claims = CompanyClaimRequest.objects.filter(
            status='pending'
        ).select_related('company')

    recent_approved = CompanyClaimRequest.objects.filter(
        status='approved'
    ).select_related('company', 'created_user').order_by('-reviewed_at')[:10]

    return render(request, 'registration/pending_claims.html', {
        'claims': claims,
        'recent_approved': recent_approved,
    })


@login_required
def send_company_invite(request, company_id):
    """POST /posrednik/invite/<uuid>/ — Marija šalje invite link."""
    from companies.models import Company
    from registration.models import CompanyClaimRequest
    from django.utils import timezone

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    company = get_object_or_404(Company, id=company_id)

    if not request.user.is_superuser:
        try:
            user_co = request.user.profile.company
            if company.umbrella_parent != user_co and company != user_co:
                return HttpResponseForbidden()
        except Exception:
            return HttpResponseForbidden()

    claim = CompanyClaimRequest.objects.create(
        company=company,
        email=request.POST.get('email', ''),
        first_name=request.POST.get('first_name', 'Vlasnik'),
        last_name=request.POST.get('last_name', ''),
        phone=request.POST.get('phone', ''),
        oib_confirmed=True,
        role_claimed='company_admin',
        token_expires=timezone.now() + timezone.timedelta(days=30),
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    invite_url = f'https://limit-connect.com/firma/aktiviraj/{claim.verify_token}/'

    # WhatsApp ako ima broj
    phone = request.POST.get('phone', '')
    if phone:
        try:
            from core.whatsapp import send_text
            send_text(
                phone=phone,
                message=(
                    f'Pozdrav! Vaša firma *{company.name}* je u LIMIT Connect sustavu.\n\n'
                    f'Aktivirajte pristup ovdje:\n{invite_url}\n\n'
                    f'Link vrijedi 30 dana.'
                ),
            )
        except Exception:
            pass

    return JsonResponse({
        'ok': True,
        'invite_url': invite_url,
        'claim_id': str(claim.id),
    })


# ════════════════════════════════════════════════════════════
# DRON2: Quick Registration — 3 polja, odmah u platformu
# ════════════════════════════════════════════════════════════

def register_quick(request):
    """Step 2 (DRON2): Samo ime, email, lozinka. Company = draft placeholder."""
    if not request.session.get("reg_plan"):
        return redirect("registration:register_step1")

    if request.method == "POST":
        import uuid
        from django.contrib.auth import login
        from django.db import transaction
        from accounts.models import UserProfile
        from companies.models import Company

        first_name = request.POST.get("first_name", "").strip()
        email = request.POST.get("email", "").strip()
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")

        errors = {}
        if not first_name:
            errors["first_name"] = "Unesite ime."
        if not email:
            errors["email"] = "Email je obavezan."
        elif User.objects.filter(email=email).exists():
            errors["email"] = (
                'Već imate račun. '
                '<a href="/hr/login/" style="color:#c9a84c;font-weight:700">Prijavite se →</a>'
            )
        if len(password1) < 8:
            errors["password1"] = "Lozinka mora imati min. 8 znakova."
        if password1 != password2:
            errors["password2"] = "Lozinke se ne podudaraju."

        if errors:
            return render(request, "registration/step2_quick.html", {
                "step": 2, "errors": errors,
                "first_name": first_name, "email": email,
            })

        plan_slug = request.session.get("reg_plan", "starter")

        with transaction.atomic():
            username = email.split("@")[0].replace(".", "_")[:20] + uuid.uuid4().hex[:4]
            user = User.objects.create_user(
                username=username, email=email, password=password1,
                first_name=first_name,
            )
            # Draft company — nepotpuna, popunjava se u wizardu
            draft_oib = f"DRAFT{uuid.uuid4().hex[:5].upper()}"[:11]
            company = Company.objects.create(
                name=f"Firma korisnika {first_name}",
                oib=draft_oib,
                country="HR",
                is_draft=True,
                has_signed_tc_consent=True,
                tc_consent_version="v1.0-2026",
                tc_consent_signed_at=__import__("django.utils.timezone", fromlist=["timezone"]).now(),
            )
            UserProfile.objects.create(
                user=user, company=company, role="company_admin",
                totp_enabled=False,
            )
            # Subscription
            try:
                from registration.models import PricingPlan
                plan = PricingPlan.objects.filter(slug=plan_slug, is_active=True).first()
                if plan:
                    from companies.models import Subscription
                    from django.utils import timezone as _tz
                    from datetime import timedelta
                    Subscription.objects.create(
                        company=company, plan=plan,
                        started_at=_tz.now(),
                        expires_at=_tz.now() + timedelta(days=plan.trial_days or 14),
                        is_active=True,
                    )
            except Exception:
                pass

        login(request, user)
        # Clear registration session
        for key in list(request.session.keys()):
            if key.startswith("reg_"):
                del request.session[key]
        return redirect("companies:setup_wizard")

    return render(request, "registration/step2_quick.html", {
        "step": 2, "errors": {},
    })


@require_GET
def api_plan_suggest(request):
    """
    GET /registration/api/plan-suggest/?name=OPG+Kruljac&nkd=01.1
    Vraca: {"plan": "starter", "reason": "...", "confidence": "ai|keyword"}
    """
    from django.http import JsonResponse
    from registration.borg_advisor import recommend_plan_by_keyword

    name = request.GET.get('name', '').strip()
    nkd = request.GET.get('nkd', '').strip()

    if not name:
        return JsonResponse({'plan': 'professional', 'reason': '', 'confidence': 'default'})

    result = recommend_plan_by_keyword(name, nkd)
    return JsonResponse(result)


def distributor_apply(request):
    """Javna forma — /postani-distributer/."""
    from registration.models import DistributorApplication

    if request.method == 'POST':
        try:
            app = DistributorApplication.objects.create(
                company_name=request.POST.get('company_name', '').strip(),
                oib=request.POST.get('oib', '').strip(),
                contact_name=request.POST.get('contact_name', '').strip(),
                email=request.POST.get('email', '').strip(),
                phone=request.POST.get('phone', '').strip(),
                city=request.POST.get('city', '').strip(),
                country=request.POST.get('country', 'HR'),
                existing_clients=request.POST.get('existing_clients', 0) or 0,
                target_segment=request.POST.get('target_segment', '').strip(),
                motivation=request.POST.get('motivation', '').strip(),
                website=request.POST.get('website', '').strip() or '',
            )
            messages.success(request, 'Prijava zaprimljena! Kontaktirat ćemo vas u roku 48h.')
            return redirect('distributor_apply')
        except Exception as e:
            messages.error(request, f'Greška: {e}')

    return render(request, 'registration/distributor_apply.html', {
        'page_title': 'Postani distributer',
    })


def register_trikey(request):
    """TriKey registracija — OIB → Sudski registar auto-fill → email → PIN setup → dashboard.
    Alternativni flow koji zamjenjuje step2+step3 u jedan ekran."""
    if not request.session.get("reg_plan"):
        return redirect("registration:register_step1")

    if request.method == "POST":
        import uuid
        from datetime import timedelta
        from django.contrib.auth import login as auth_login
        from django.db import transaction as db_transaction
        from accounts.models import UserProfile
        from accounts.trikey import TriKeyProfile, generate_pin
        from companies.models import Company
        from .models import PricingPlan, CompanySubscription

        oib = request.POST.get("oib", "").strip()
        company_name = request.POST.get("company_name", "").strip()
        address = request.POST.get("address", "").strip()
        city = request.POST.get("city", "").strip()
        zip_code = request.POST.get("zip_code", "").strip()
        country = request.POST.get("country", "HR")
        email = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        pin = request.POST.get("pin", "").strip()
        password1 = request.POST.get("password1", "")

        errors = {}
        if not oib:
            errors["oib"] = "OIB je obavezan."
        elif country == "HR" and (len(oib) != 11 or not oib.isdigit()):
            errors["oib"] = "Hrvatski OIB mora imati 11 znamenki."
        if not company_name:
            errors["company_name"] = "Naziv firme je obavezan."
        if not email:
            errors["email"] = "Email je obavezan."
        elif User.objects.filter(email=email).exists():
            errors["email"] = 'Već imate račun. <a href="/hr/login/" style="color:#c9a84c">Prijavite se →</a>'
        if len(password1) < 8:
            errors["password1"] = "Lozinka mora imati min. 8 znakova."
        if pin and (len(pin) != 6 or not pin.isdigit()):
            errors["pin"] = "PIN mora biti točno 6 znamenki."

        if errors:
            return render(request, "registration/trikey_register.html", {
                "step": 2, "errors": errors,
                "oib": oib, "company_name": company_name, "address": address,
                "city": city, "zip_code": zip_code, "country": country,
                "email": email, "first_name": first_name, "last_name": last_name,
            })

        plan_slug = request.session.get("reg_plan", "starter")
        plan = PricingPlan.objects.filter(slug=plan_slug, is_active=True).first()

        try:
            with db_transaction.atomic():
                # Create user
                base_un = email.split("@")[0].lower().replace(".", "_")[:30]
                username = base_un
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_un}{counter}"
                    counter += 1
                user = User.objects.create_user(
                    username=username, email=email, password=password1,
                    first_name=first_name or email.split("@")[0].title(),
                    last_name=last_name,
                )

                # Create company
                company_fields = [f.name for f in Company._meta.get_fields()]
                kw = {"name": company_name, "oib": oib}
                if "country" in company_fields: kw["country"] = country
                if "address" in company_fields: kw["address"] = f"{address}, {zip_code} {city}".strip(", ")
                if "business_type" in company_fields: kw["business_type"] = "doo"
                company = Company.objects.create(**kw)

                # Profile
                UserProfile.objects.create(user=user, company=company, role="company_admin")

                # TriKey — set PIN
                trikey = TriKeyProfile.objects.create(user=user)
                if not pin:
                    pin = generate_pin()
                trikey.set_pin(pin)

                # Subscription
                trial_end = now().date() + timedelta(days=14)
                if plan:
                    CompanySubscription.objects.create(
                        company=company, plan=plan_slug, pricing_plan=plan,
                        valid_from=now().date(), trial_ends=trial_end,
                        billing_cycle="monthly", monthly_fee=plan.price_monthly, is_active=True,
                    )

                # Seed demo data
                _seed_demo_data(company, user)
                _auto_create_website(company)

                # Login
                auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")

                # Send PIN via email
                from django.core.mail import send_mail
                send_mail(
                    subject="LIMIT Connect — Vaš TriKey PIN",
                    message=f"Dobrodošli u LIMIT Connect!\n\nVaš PIN za brzu prijavu: {pin}\n\nPromijenite ga u Postavke → TriKey.\n\nhttps://limit-connect.com",
                    from_email=None, recipient_list=[email], fail_silently=True,
                )

                # Clean session
                for key in ["reg_plan", "reg_company", "reg_user", "reg_password",
                            "reg_promo_code", "reg_source", "reg_profile"]:
                    request.session.pop(key, None)

                messages.success(request, f"Dobrodošli! Vaš PIN: {pin} — zapišite ga ili provjerite email.")
                return redirect("dashboard")
        except Exception as e:
            logger.exception("TriKey registration error")
            messages.error(request, f"Greška: {e}")

    return render(request, "registration/trikey_register.html", {
        "step": 2, "errors": {},
        "country": "HR",
    })
