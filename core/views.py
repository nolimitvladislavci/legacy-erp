from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from django.views.decorators.csrf import csrf_exempt
from permissions.decorators import require_role
from .services import get_company_dashboard_stats, get_superadmin_stats


def _get_admin_companies(request):
    """Return companies visible to this admin."""
    from companies.models import Company
    if request.user.is_superuser:
        try:
            if request.user.profile.role == "superadmin":
                return Company.objects.all()
        except Exception:
            return Company.objects.all()
    try:
        return request.user.profile.get_visible_companies()
    except Exception:
        return Company.objects.none()



def _time_periods():
    """Common time period calculations used across dashboards."""
    from django.utils import timezone
    from datetime import timedelta
    today = timezone.now().date()
    return {
        'today': today,
        'week_start': today - timedelta(days=today.weekday()),
        'month_start': today.replace(day=1),
        'now': timezone.now(),
    }


def dashboard_router(request):
    """Preusmjeri ovisno o domeni i statusu prijave"""
    host = request.get_host().split(':')[0]
    # Ako je viskovic domena
    if 'viskovic' in host:
        if request.user.is_authenticated:
            from django.utils.translation import get_language
            _lang = get_language() or 'de'
            _prefix = '/{}'.format(_lang) if _lang != 'de' else ''
            return redirect('https://limit-connect.com{}/dashboard/'.format(_prefix))
        from website.views import homepage
        return homepage(request)
    # Nelogirani -> direktno na login formu
    if not request.user.is_authenticated:
        return redirect('login')

    # Ako je prijavljen - na dashboard prema roli
    if request.user.is_superuser:
        # Ako je superadmin u impersonation modu -> company_dashboard
        if request.session.get('impersonated_company_id') or request.session.get('superadmin_as_company'):
            return redirect('company_dashboard')
        return redirect('superadmin_dashboard')

    # ── Ensure profile exists ──────────
    from accounts.models import UserProfile
    profile, _created = UserProfile.objects.get_or_create(
        user=request.user, defaults={'role': 'worker'}
    )
    if _created:
        logger.info("Auto-created profile for user %s", request.user.username)

    # ── Branch routing: branch users → branch-specific dashboard ──────────
    try:
        branch = profile.branch
        if branch and branch.is_active:
            return redirect(branch.dashboard_url)
    except Exception:
        logger.warning("Branch routing error", exc_info=True)

    # Route by role
    role = profile.role

    if role in ('company_admin', 'project_manager'):
        return redirect('company_dashboard')
    elif role == 'investor' or role == 'partner':
        return redirect('partner_dashboard') # Šaljemo ih oboje u Staklenu sobu
    else:
        # worker / unknown → worker dashboard
        return redirect('worker_dashboard')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        from django.contrib.auth.models import User as AuthUser

        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        remember = request.POST.get('remember')
        errors = []

        if not email:
            errors.append('Email adresa je obavezna.')
        if not password:
            errors.append('Lozinka je obavezna.')

        if not errors:
            try:
                user_obj = AuthUser.objects.filter(email=email).order_by('-last_login').first()
                if user_obj is None:
                    raise AuthUser.DoesNotExist
            except AuthUser.DoesNotExist:
                errors.append('Ne postoji racun s ovom email adresom.')
                return render(request, 'registration/login.html', {
                    'errors': errors, 'email_value': email,
                })

            user = authenticate(request, username=user_obj.username, password=password)
            if user is None:
                errors.append('Pogresna lozinka. Pokusajte ponovo ili resetirajte lozinku.')
                return render(request, 'registration/login.html', {
                    'errors': errors, 'email_value': email,
                })

            if not user.is_active:
                errors.append('Vas racun je deaktiviran. Kontaktirajte administratora.')
                return render(request, 'registration/login.html', {
                    'errors': errors, 'email_value': email,
                })

            # Flush old session to prevent mixing with previous user
            request.session.flush()
            login(request, user)
            if not remember:
                request.session.set_expiry(0)

            # Set language: form choice > profile preference > default
            lang_choice = request.POST.get('language', '').strip()
            try:
                profile_lang = user.profile.preferred_language
            except Exception:
                profile_lang = 'hr'
            lang = lang_choice or profile_lang or 'hr'
            # Save to profile if changed via form
            if lang_choice and lang_choice != profile_lang:
                try:
                    user.profile.preferred_language = lang_choice
                    user.profile.save(update_fields=['preferred_language'])
                except Exception:
                    pass

            host = request.get_host().split(':')[0]
            # Build language-prefixed dashboard URL
            if lang and lang != 'de':
                dash_url = '/{}/dashboard/'.format(lang)
            else:
                dash_url = '/dashboard/'
            if 'viskovic' in host:
                resp = redirect('https://limit-connect.com' + dash_url)
            else:
                next_url = request.GET.get('next', '')
                if next_url and next_url != '/':
                    resp = redirect(next_url)
                else:
                    resp = redirect(dash_url)
            # Set Django language cookie (1 year)
            from django.conf import settings as _s
            resp.set_cookie(
                _s.LANGUAGE_COOKIE_NAME, lang,
                max_age=_s.LANGUAGE_COOKIE_AGE,
                path='/',
                samesite='Lax',
            )
            return resp

        return render(request, 'registration/login.html', {
            'errors': errors, 'email_value': email,
        })

    success_msg = request.GET.get('msg')
    return render(request, 'registration/login.html', {
        'success_msg': success_msg,
    })

def logout_view(request):
    logout(request)
    host = request.get_host().split(':')[0]
    if 'viskovic' in host:
        return redirect('/')
    return redirect('login')

@require_role("superadmin")
@login_required
def superadmin_dashboard(request):
    from django.contrib.auth import get_user_model
    from django.db.models import Sum
    from django.utils import timezone
    User = get_user_model()
    today = timezone.now().date()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()
    superusers = User.objects.filter(is_superuser=True).count()
    recent_users = User.objects.order_by('-date_joined')[:8]

    try:
        from companies.models import Company
        total_companies = Company.objects.count()
        recent_companies = Company.objects.order_by('-id')[:5]
    except Exception:
        total_companies = 0
        recent_companies = []

    try:
        from invoicing.models import Invoice
        total_invoices = Invoice.objects.unscoped().filter(doctype='R').count()
        revenue_total = Invoice.objects.unscoped().filter(doctype='R', status='PAID').aggregate(s=Sum('total'))['s'] or 0
        revenue_month = Invoice.objects.unscoped().filter(doctype='R', status='PAID', date_issued__date__gte=month_start).aggregate(s=Sum('total'))['s'] or 0
        unpaid_total  = Invoice.objects.unscoped().filter(doctype='R', status__in=('UNPAID','OVERDUE')).aggregate(s=Sum('total'))['s'] or 0
        recent_invoices = Invoice.objects.unscoped().order_by('-date_issued')[:8]
    except Exception:
        total_invoices = revenue_total = revenue_month = unpaid_total = 0
        recent_invoices = []

    try:
        from worktime.models import TimeEntry
        total_entries = TimeEntry.objects.count()
        recent_entries = TimeEntry.objects.select_related('user').order_by('-date')[:10]
    except Exception:
        total_entries = 0
        recent_entries = []

    try:
        from projects.models import Project
        total_projects = Project.objects.count()
        active_projects = Project.objects.exclude(status__in=('completed','cancelled')).count()
    except Exception:
        total_projects = 0
        active_projects = 0

    try:
        from pos.models import POSSession
        pos_today = POSSession.objects.filter(opened_at__date=today).count()
        pos_open  = POSSession.objects.filter(status='open').count()
    except Exception:
        pos_today = pos_open = 0

    try:
        from appointments.models import Appointment
        appts_today = Appointment.objects.filter(start_time__date=today).count()
    except Exception:
        appts_today = 0

    context = {
        'total_users': total_users, 'active_users': active_users,
        'staff_users': staff_users, 'superusers': superusers,
        'recent_users': recent_users,
        'total_companies': total_companies, 'recent_companies': recent_companies,
        'total_invoices': total_invoices, 'revenue_total': revenue_total,
        'revenue_month': revenue_month, 'unpaid_total': unpaid_total,
        'recent_invoices': recent_invoices,
        'total_entries': total_entries, 'recent_entries': recent_entries,
        'total_projects': total_projects, 'active_projects': active_projects,
        'pos_today': pos_today, 'pos_open': pos_open,
        'appts_today': appts_today,
        'today': today,
    }
    try:
        from registration.models import CompanyRegistration, CompanySubscription
        context['pending_registrations'] = CompanyRegistration.objects.filter(status='pending').count()
        context['recent_registrations'] = list(CompanyRegistration.objects.order_by('-created_at')[:8])
        context['company_subs'] = list(CompanySubscription.objects.filter(is_active=True).select_related('company').order_by('-created_at')[:10])
        # All companies with active subscription for module management
        from companies.models import Company
        from registration.constants import PLAN_MODULES
        all_modules = list(PLAN_MODULES.get('enterprise', set()))
        all_modules_sorted = sorted(all_modules)
        companies_with_subs = []
        for company in _get_admin_companies(request).order_by('name'):
            sub = company.subscriptions.filter(is_active=True).order_by('-valid_from').first()
            companies_with_subs.append({'company': company, 'sub': sub})
        context['all_companies_subs'] = companies_with_subs
        context['all_modules_sorted'] = all_modules_sorted
        # Promo codes
        try:
            from registration.models import PromoCode
            context['promo_codes'] = list(PromoCode.objects.all().order_by('-created_at')[:50])
        except Exception:
            context['promo_codes'] = []
        # Platform owner
        context['platform_owner'] = Company.objects.filter(is_platform_owner=True).first()
    except Exception as e:
        context['pending_registrations'] = 0
        context['recent_registrations'] = []
        context['company_subs'] = []
        context['all_companies_subs'] = []
        context['all_modules_sorted'] = []
    try:
        from burza.models import ProjectLead
        context['burza_new'] = ProjectLead.objects.filter(status='NOVI_UPIT').count()
    except Exception:
        context['burza_new'] = 0
    try:
        from django.db.models import Sum as _Sum

        from ai_assistant.models import AIUsageLog, Conversation
        context['ai_total_calls']   = AIUsageLog.objects.count()
        context['ai_total_cost']    = AIUsageLog.objects.aggregate(s=_Sum('cost_estimate'))['s'] or 0
        context['ai_conversations'] = Conversation.objects.filter(is_active=True).count()
    except Exception:
        context['ai_total_calls'] = context['ai_total_cost'] = context['ai_conversations'] = 0

    # Financijska odstupanja (parcijalne uplate)
    try:
        from finance.bank_parsers import get_partial_payment_discrepancies
        _co = getattr(getattr(request.user, 'profile', None), 'company', None)
        _disc = get_partial_payment_discrepancies(_co) if _co else []
        context['discrepancy_count'] = len(_disc)
        context['discrepancy_gap_total'] = sum(d['gap'] for d in _disc)
    except Exception:
        context['discrepancy_count'] = 0
        context['discrepancy_gap_total'] = 0
    return render(request, 'dashboards/superadmin.html', context)




@login_required
def umbrella_dashboard(request):
    """Enhanced umbrella dashboard - manage child companies, create new ones, view stats."""
    from companies.models import Company
    from core.company_utils import get_user_company
    from django.contrib.auth import get_user_model
    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import timedelta
    User = get_user_model()

    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nemate dodijeljenu tvrtku.')
        return redirect('dashboard')

    # Superadmin can view any umbrella
    umbrella_id = request.GET.get('umbrella')
    if request.user.is_superuser and umbrella_id:
        try:
            company = Company.objects.get(pk=umbrella_id)
        except Company.DoesNotExist:
            pass

    if not company.is_umbrella and not request.user.is_superuser:
        messages.warning(request, 'Vasa tvrtka nije umbrella tvrtka.')
        return redirect('dashboard')

    children = Company.objects.filter(umbrella_parent=company).order_by('name')
    now = timezone.now()
    month_start = now.date().replace(day=1)

    # Per-child enriched data
    children_data = []
    total_users = 0
    total_revenue = 0
    for child in children:
        user_count = User.objects.filter(profile__company=child).count()
        total_users += user_count

        # Invoice revenue this month
        inv_rev = 0
        try:
            from invoicing.models import Invoice
            inv_rev = Invoice.objects.filter(
                company=child, status='PAID', date_issued__date__gte=month_start
            ).aggregate(s=Sum('total'))['s'] or 0
            inv_rev = float(inv_rev)
        except Exception:
            pass

        # POS revenue this month
        pos_rev = 0
        try:
            from pos.models import POSReceipt
            pos_rev = POSReceipt.objects.filter(
                session__terminal__company=child, status='paid',
                created_at__date__gte=month_start
            ).aggregate(s=Sum('total'))['s'] or 0
            pos_rev = float(pos_rev)
        except Exception:
            pass

        total_revenue += inv_rev + pos_rev

        # Synesis status
        synesis_status = None
        try:
            from synesis.models import SynesisConfig
            cfg = SynesisConfig.objects.filter(company=child).first()
            if cfg:
                synesis_status = {
                    'active': cfg.is_active if hasattr(cfg, 'is_active') else True,
                    'last_sync': getattr(cfg, 'last_sync', None) or getattr(cfg, 'updated_at', None),
                }
        except Exception:
            pass

        # Subscription
        sub_plan = '-'
        try:
            sub = child.subscriptions.filter(is_active=True).order_by('-valid_from').first()
            if sub:
                sub_plan = sub.plan.upper()
        except Exception:
            pass

        children_data.append({
            'company': child,
            'user_count': user_count,
            'inv_revenue': inv_rev,
            'pos_revenue': pos_rev,
            'total_revenue': inv_rev + pos_rev,
            'synesis': synesis_status,
            'plan': sub_plan,
        })

    # Handle POST actions
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_child':
            child_id = request.POST.get('company_id')
            if child_id:
                try:
                    child = Company.objects.get(pk=child_id, umbrella_parent__isnull=True)
                    relation = request.POST.get('relation', 'client')
                    child.umbrella_parent = company
                    child.umbrella_relation = relation
                    child.save(update_fields=['umbrella_parent', 'umbrella_relation'])
                    messages.success(request, '{} dodana kao podtvrtka.'.format(child.name))
                except Company.DoesNotExist:
                    messages.error(request, 'Tvrtka nije pronadjena ili vec ima nadredjenu.')
            return redirect(request.get_full_path())

        elif action == 'remove_child':
            child_id = request.POST.get('company_id')
            if child_id:
                try:
                    child = Company.objects.get(pk=child_id, umbrella_parent=company)
                    child.umbrella_parent = None
                    child.save(update_fields=['umbrella_parent'])
                    messages.success(request, '{} uklonjena iz umbrella.'.format(child.name))
                except Company.DoesNotExist:
                    pass
            return redirect(request.get_full_path())

        elif action == 'create_child':
            name = request.POST.get('name', '').strip()
            oib = request.POST.get('oib', '').strip()
            city = request.POST.get('city', '').strip()
            address = request.POST.get('address', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone', '').strip()

            if not name or not oib:
                messages.error(request, 'Naziv i OIB su obavezni.')
            elif Company.objects.filter(oib=oib).exists():
                messages.error(request, 'Tvrtka s OIB-om {} vec postoji.'.format(oib))
            else:
                relation = request.POST.get('relation', 'client')
                new_child = Company.objects.create(
                    name=name, oib=oib, city=city, address=address,
                    email=email, phone=phone,
                    umbrella_parent=company,
                    umbrella_relation=relation,
                    country=company.country,
                    currency=company.currency,
                    fiscal_system=company.fiscal_system,
                )
                # Create default subscription (free/starter)
                try:
                    from registration.models import CompanySubscription
                    CompanySubscription.objects.create(
                        company=new_child,
                        plan='free',
                        is_active=True,
                    )
                except Exception:
                    pass

                messages.success(request, 'Tvrtka {} kreirana i dodana pod umbrella.'.format(name))
            return redirect(request.get_full_path())

    # Available companies to add (no parent, not self, not already umbrella)
    available = Company.objects.filter(
        umbrella_parent__isnull=True, is_umbrella=False
    ).exclude(pk=company.pk).order_by('name')

    # All umbrellas for superadmin
    all_umbrellas = []
    if request.user.is_superuser:
        all_umbrellas = Company.objects.filter(is_umbrella=True).order_by('name')

    subsidiaries = [cd for cd in children_data if cd['company'].umbrella_relation == 'subsidiary']
    clients = [cd for cd in children_data if cd['company'].umbrella_relation != 'subsidiary']

    # Import partners action
    if request.method == 'POST' and request.POST.get('action') == 'import_partners':
        partner_ids = request.POST.getlist('partner_ids')
        imported = 0
        for pid in partner_ids:
            try:
                partner = Partner.objects.get(id=pid, company=company)
                if partner.oib and Company.objects.filter(oib=partner.oib).exists():
                    continue
                Company.objects.create(
                    name=partner.name,
                    oib=partner.oib or '',
                    city=partner.city or '',
                    address=partner.address or '',
                    zip_code=partner.zip_code or '',
                    umbrella_parent=company,
                    umbrella_relation='client',
                    subscription_plan='free',
                )
                imported += 1
            except Partner.DoesNotExist:
                continue
        if imported:
            from django.contrib import messages as djmsg
            djmsg.success(request, f'Uvezeno {imported} firmi kao klijenti.')
        return redirect('umbrella_dashboard')

    # Available partners for import (have OIB, not already a Company)
    existing_oibs = set(Company.objects.values_list('oib', flat=True))
    existing_oibs.discard('')
    available_partners = Partner.objects.filter(
        company=company
    ).exclude(oib='').exclude(oib__in=existing_oibs).order_by('name')

    return render(request, 'dashboards/umbrella.html', {
        'company': company,
        'children_data': children_data,
        'subsidiaries': subsidiaries,
        'clients': clients,
        'children_count': len(children_data),
        'sub_count': len(subsidiaries),
        'client_count': len(clients),
        'total_users': total_users,
        'total_revenue': total_revenue,
        'available': available,
        'all_umbrellas': all_umbrellas,
        'max_children': company.umbrella_max_children,
        'month_label': now.strftime('%m/%Y'),
        'available_partners': available_partners,
    })



@login_required
def umbrella_switch_company(request, company_id):
    """Umbrella admin switches to view a child company."""
    from companies.models import Company
    user_company = request.user.profile.company
    if not user_company or not user_company.is_umbrella:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Nemate umbrella pristup.")
    try:
        child = Company.objects.get(pk=company_id, umbrella_parent=user_company)
    except Company.DoesNotExist:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Firma nije va\u0161a podru\u017enica/klijent.")
    request.session['umbrella_as_company'] = str(child.pk)
    request.session['umbrella_home_company'] = str(user_company.pk)
    request.session['umbrella_home_name'] = user_company.name
    # B-16: Audit log za umbrella switch
    try:
        from worktime.tracker import track
        track(request.user, 'AUTH', 'UMBRELLA_SWITCH',
              ref=str(child.pk),
              detail='Umbrella switch: %s -> %s' % (user_company.name, child.name),
              company=child)
    except Exception:
        pass
    return redirect('dashboard')


@login_required
def umbrella_switch_back(request):
    """Return to umbrella parent company."""
    for key in ('umbrella_as_company', 'umbrella_home_company', 'umbrella_home_name'):
        request.session.pop(key, None)
    return redirect('umbrella_dashboard')


@login_required
def superadmin_edit_user(request, user_id):
    """Edit any user - superadmin only."""
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    from django.contrib.auth import get_user_model
    from accounts.models import UserProfile
    from companies.models import Company
    User = get_user_model()

    target = get_object_or_404(User, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=target)
    companies = _get_admin_companies(request).order_by('name')

    if request.method == 'POST':
        # User fields
        target.first_name = request.POST.get('first_name', '').strip()
        target.last_name = request.POST.get('last_name', '').strip()
        target.email = request.POST.get('email', '').strip()
        target.is_active = request.POST.get('is_active') == '1'
        target.is_staff = request.POST.get('is_staff') == '1'
        target.is_superuser = request.POST.get('is_superuser') == '1'

        # Password change
        new_pw = request.POST.get('new_password', '').strip()
        if new_pw:
            target.set_password(new_pw)

        target.save()

        # Auto-notify via WhatsApp/email
        if new_pw:
            try:
                from accounts.password_notify import notify_password_change
                notify_password_change(target, new_pw, changed_by=request.user)
            except Exception:
                pass

        # Profile fields
        profile.role = request.POST.get('role', 'worker')
        company_id = request.POST.get('company', '')
        if company_id:
            try:
                profile.company = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                pass
        else:
            profile.company = None
        profile.phone = request.POST.get('phone', '').strip()
        profile.department = request.POST.get('department', '').strip()
        profile.preferred_language = request.POST.get('preferred_language', 'hr')
        profile.can_view_financials = request.POST.get('can_view_financials') == '1'
        profile.can_approve_timesheets = request.POST.get('can_approve_timesheets') == '1'
        profile.can_upload_photos = request.POST.get('can_upload_photos') == '1'
        profile.save()

        messages.success(request, 'Korisnik {} uspjesno azuriran.'.format(target.username))
        return redirect('superadmin_users')

    return render(request, 'dashboards/superadmin_edit_user.html', {
        'target': target,
        'profile': profile,
        'companies': companies,
        'role_choices': UserProfile.ROLE_CHOICES,
    })


@login_required
def superadmin_users(request):
    """Cross-company user management for superadmins."""
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()

    q = request.GET.get('q', '').strip()
    company_filter = request.GET.get('company', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')

    users = User.objects.select_related('profile', 'profile__company').order_by('-date_joined')

    if q:
        users = users.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) |
            Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    if company_filter:
        users = users.filter(profile__company_id=company_filter)
    if role_filter:
        if role_filter == 'superuser':
            users = users.filter(is_superuser=True)
        elif role_filter == 'staff':
            users = users.filter(is_staff=True, is_superuser=False)
        else:
            users = users.filter(profile__role=role_filter)
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(users, 50)
    page = request.GET.get('page', 1)
    users_page = paginator.get_page(page)

    # Companies for filter dropdown
    from companies.models import Company
    companies = _get_admin_companies(request).order_by('name')

    # Handle POST actions (toggle active, toggle staff)
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        if action and user_id:
            try:
                target = User.objects.get(pk=user_id)
                if action == 'toggle_active':
                    target.is_active = not target.is_active
                    target.save(update_fields=['is_active'])
                    messages.success(request, '{} je sada {}'.format(
                        target.username, 'aktivan' if target.is_active else 'neaktivan'))
                elif action == 'toggle_staff':
                    target.is_staff = not target.is_staff
                    target.save(update_fields=['is_staff'])
                    messages.success(request, '{} staff status: {}'.format(
                        target.username, target.is_staff))
                elif action == 'impersonate_company' and hasattr(target, 'profile') and target.profile.company:
                    return redirect('start_impersonation', company_id=target.profile.company_id)
            except User.DoesNotExist:
                messages.error(request, 'Korisnik nije pronaden.')
            return redirect(request.get_full_path())

    return render(request, 'dashboards/superadmin_users.html', {
        'users_page': users_page,
        'companies': companies,
        'q': q,
        'company_filter': company_filter,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'total_count': paginator.count,
    })


@login_required
def company_dashboard(request):
    import datetime

    from django.db.models import Sum
    from django.utils import timezone

    company = None
    try:
        company = request.user.profile.company
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
    # Umbrella companies go to umbrella dashboard
    if company and company.is_umbrella:
        return redirect("umbrella_dashboard")

    today = timezone.now().date()
    today = timezone.now().date()
    month_start = today.replace(day=1)

    # ── Fakture ──────────────────────────────────────────────────────────────
    try:
        from invoicing.models import Invoice
        inv_qs = Invoice.objects.unscoped()
        if company:
            inv_qs = inv_qs.filter(company=company)

        total_invoiced = inv_qs.filter(
            doctype='R', status__in=('SENT', 'PAID', 'UNPAID', 'OVERDUE')
        ).aggregate(s=Sum('total'))['s'] or 0

        unpaid = inv_qs.filter(
            doctype='R', status__in=('UNPAID', 'OVERDUE')
        ).aggregate(s=Sum('total'))['s'] or 0

        paid_month = inv_qs.filter(
            doctype='R', status='PAID',
            date_issued__date__gte=month_start
        ).aggregate(s=Sum('total'))['s'] or 0

        recent_invoices = inv_qs.filter(doctype='R').order_by('-date_issued')[:8]

        pending_offers = inv_qs.filter(
            doctype='PO', status__in=('DRAFT', 'SENT')
        ).count()
    except Exception:
        total_invoiced = unpaid = paid_month = pending_offers = 0
        recent_invoices = []

    # ── Radni sati ────────────────────────────────────────────────────────────
    try:
        from worktime.models import TimeEntry
        te_qs = TimeEntry.objects.filter(user=request.user)
        hours_week  = te_qs.filter(date__gte=week_start).aggregate(s=Sum('duration'))['s'] or 0
        hours_month = te_qs.filter(date__gte=month_start).aggregate(s=Sum('duration'))['s'] or 0
        recent_entries = te_qs.select_related('project').order_by('-date')[:5]
    except Exception:
        hours_week = hours_month = 0
        recent_entries = []

    # ── Projekti ──────────────────────────────────────────────────────────────
    try:
        from projects.models import Project
        proj_qs = Project.objects.unscoped()
        if company:
            proj_qs = proj_qs.filter(company=company)
        projects = proj_qs.filter(status__in=('active', 'in_progress', 'open')).order_by('-id')[:5]
        total_projects = proj_qs.exclude(status__in=('completed', 'cancelled')).count()
    except Exception:
        projects = []
        total_projects = 0

    # ── Partneri ──────────────────────────────────────────────────────────────
    try:
        from partners.models import Partner
        part_qs = Partner.objects.unscoped()
        if company:
            part_qs = part_qs.filter(company=company)
        total_partners = part_qs.count()
    except Exception:
        total_partners = 0

    # ── Finance ───────────────────────────────────────────────────────────────
    try:
        from finance.models import Transaction
        tx_qs = Transaction.objects.unscoped()
        if company:
            tx_qs = tx_qs.filter(company=company)
        income_month  = tx_qs.filter(direction='income',  date__gte=month_start).aggregate(s=Sum('amount'))['s'] or 0
        expense_month = tx_qs.filter(direction='expense', date__gte=month_start).aggregate(s=Sum('amount'))['s'] or 0
        cashflow_month = income_month - expense_month
    except Exception:
        income_month = expense_month = cashflow_month = 0


    # ── Revenue chart — last 6 months ────────────────────────────────────────
    import json as _json
    revenue_labels = []
    revenue_data   = []
    offers_data    = []
    try:
        from invoicing.models import Invoice as _Inv
        from django.db.models import Sum as _Sum2
        import datetime as _dt2
        _today2 = timezone.now().date()
        for _i in range(5, -1, -1):
            _d = (_today2.replace(day=1) - _dt2.timedelta(days=_i*28)).replace(day=1)
            _next = (_d.replace(day=28) + _dt2.timedelta(days=4)).replace(day=1)
            _label = _d.strftime("%b '%y")
            _rev = _Inv.objects.unscoped().filter(
                company=company, doctype="R", status="PAID",
                date_issued__date__gte=_d, date_issued__date__lt=_next
            ).aggregate(s=_Sum2("total"))["s"] or 0
            _off = _Inv.objects.unscoped().filter(
                company=company, doctype="PO",
                date_issued__date__gte=_d, date_issued__date__lt=_next
            ).aggregate(s=_Sum2("total"))["s"] or 0
            revenue_labels.append(_label)
            revenue_data.append(float(_rev))
            offers_data.append(float(_off))
    except Exception:
        pass

    # ── Overdue / dospjeli računi ─────────────────────────────────────────────
    overdue_invoices = []
    overdue_total = 0
    try:
        from invoicing.models import Invoice as _Inv2
        _ov_qs = _Inv2.objects.unscoped().filter(
            company=company,
            doctype="R",
            status__in=("SENT", "DRAFT", "ACCEPTED"),
            date_due__lt=timezone.now().date(),
        ).order_by("date_due")[:10]
        overdue_invoices = list(_ov_qs)
        overdue_total = sum(float(i.total) for i in overdue_invoices)
    except Exception:
        pass

    context = {
        'company':        company,
        'total_invoiced': total_invoiced,
        'unpaid':         unpaid,
        'paid_month':     paid_month,
        'pending_offers': pending_offers,
        'recent_invoices': recent_invoices,
        'hours_week':     hours_week,
        'hours_month':    hours_month,
        'recent_entries': recent_entries,
        'projects':       projects,
        'total_projects': total_projects,
        'total_partners': total_partners,
        'income_month':   income_month,
        'expense_month':  expense_month,
        'cashflow_month': cashflow_month,
        'today':          today,
        'revenue_labels':  _json.dumps(revenue_labels),
        'revenue_data':    _json.dumps(revenue_data),
        'offers_data':     _json.dumps(offers_data),
        'overdue_invoices': overdue_invoices,
        'overdue_total':   overdue_total,
    }
    try:
        from appointments.models import Appointment
        appt_qs = Appointment.objects.filter(start_time__date=today)
        if company:
            appt_qs = appt_qs.filter(company=company)
        today_appointments = appt_qs.order_by('start_time')[:8]
        total_appointments_month = Appointment.objects.filter(start_time__date__gte=month_start).count()
    except Exception:
        today_appointments = []
        total_appointments_month = 0

    try:
        from pos.models import POSReceipt
        pos_qs = POSReceipt.objects.unscoped()
        pos_revenue_today = pos_qs.filter(created_at__date=today).aggregate(s=Sum('total_amount'))['s'] or 0
        pos_count_today = pos_qs.filter(created_at__date=today).count()
    except Exception:
        pos_revenue_today = pos_count_today = 0

    # ── Worker clock-in status ───────────────────────────────────────────────
    worker_status = []
    workers_online = 0
    workers_total = 0
    try:
        import datetime as _dt

        from django.contrib.auth.models import User as _AU
        from django.db.models import Sum as _Sum

        from worktime.models import TimeEntry as _TE2
        _wk_start = today - _dt.timedelta(days=today.weekday())
        if company:
            from accounts.models import UserProfile as _UP
            _uids = list(_UP.objects.filter(company=company).values_list('user_id', flat=True))
            _users = _AU.objects.filter(id__in=_uids, is_active=True)
        else:
            _users = _AU.objects.filter(is_staff=False, is_active=True)[:20]
        workers_total = _users.count()
        for _wu in _users:
            try:
                _timer = _wu.active_timer
                _clocked = True
                workers_online += 1
                _elapsed = _timer.elapsed_display
                _proj = _timer.project.code if _timer.project else ''
            except Exception:
                _clocked = False; _elapsed = ''; _proj = ''
            _hrs_w = _TE2.objects.filter(user=_wu, date__gte=_wk_start).aggregate(
                s=_Sum('duration'))['s'] or 0
            _fn = _wu.get_full_name() or _wu.username
            _ini = ''.join(p[0].upper() for p in _fn.split()[:2]) or _fn[:2].upper()
            worker_status.append({
                'user_id': _wu.pk, 'name': _fn, 'initials': _ini,
                'is_clocked_in': _clocked,
                'timer_elapsed': _elapsed,
                'timer_project': _proj,
                'hours_week': _hrs_w,
            })
    except Exception as _wse:
        import logging; logging.getLogger(__name__).warning(f'worker_status: {_wse}')

    # ── Pending time entry approvals ─────────────────────────────────────────
    pending_approvals = 0
    pending_entries = []
    try:
        from worktime.models import TimeEntry as _TE3
        _pqs = _TE3.objects.filter(status='PENDING').select_related('user', 'project')
        pending_approvals = _pqs.count()
        pending_entries = list(_pqs.order_by('-date')[:8])
    except Exception:
        logger.warning("Suppressed error", exc_info=True)

    # ── Active interventions ─────────────────────────────────────────────────
    active_interventions = 0
    active_iv_list = []
    try:
        from interventions.models import HitnaIntervencija as _HI
        _ivqs = _HI.objects.exclude(
            status__in=['RIJESENO','ESKALIRANO','FAKTURIRANO']
        ).select_related('assigned_to').order_by('-created_at')
        active_interventions = _ivqs.count()
        active_iv_list = list(_ivqs[:8])
    except Exception:
        logger.warning("Suppressed error", exc_info=True)

    context.update({
        'worker_status':       worker_status,
        'workers_online':      workers_online,
        'workers_total':       workers_total,
        'pending_approvals':   pending_approvals,
        'pending_entries':     pending_entries,
        'active_interventions': active_interventions,
        'active_iv_list':      active_iv_list,
    })

    # -- Onboarding progress
    onboarding = None
    try:
        from companies.models import OnboardingProgress
        if company:
            ob, _ = OnboardingProgress.objects.get_or_create(company=company)
            # Mark profile_completed if company has name + address + OIB
            if not ob.profile_completed:
                if (company.name and company.address and company.oib):
                    ob.profile_completed = True
                    ob.save(update_fields=['profile_completed', 'updated_at'])
            if not ob.dismissed:
                onboarding = ob
                # Redirect new users to wizard if onboarding < 60% complete
                if ob.percent < 60 and not request.GET.get('skip_onboarding'):
                    return redirect('onboarding_wizard')
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
    context['onboarding'] = onboarding

    # -- Fiscal stats widget
    fiscal_stats = {
        'unfiscalized_count': 0,
        'cert_valid': False,
        'cert_expiring_soon': False,
        'days_until_expiry': None,
    }
    try:
        from invoicing.fiscal_models import FiscalCertificate as _FC
        from invoicing.models import Invoice as _Invoice
        if company:
            fiscal_stats['unfiscalized_count'] = _Invoice.objects.filter(
                company=company, is_fiscalized=False,
                status__in=['SENT', 'PAID', 'UNPAID'],
            ).count()
            cert = _FC.objects.filter(company=company, is_active=True).first()
            if cert:
                fiscal_stats['cert_valid'] = getattr(cert, 'is_valid', False)
                fiscal_stats['cert_expiring_soon'] = getattr(cert, 'is_expiring_soon', False)
                fiscal_stats['days_until_expiry'] = getattr(cert, 'days_until_expiry', None)
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
    context['fiscal_stats'] = fiscal_stats


    # ── Inventory / Skladište ──────────────────────────────────────────────────
    inventory_stats = {'total_items': 0, 'low_stock_count': 0, 'stock_value': 0, 'selling_value': 0}
    try:
        from inventory.models import InventoryItem as _II
        if company:
            _items = list(_II.objects.filter(company=company, is_active=True))
            inventory_stats['total_items']     = len(_items)
            inventory_stats['low_stock_count'] = sum(1 for i in _items if i.is_low_stock)
            inventory_stats['stock_value']     = sum(i.stock_value   for i in _items)
            inventory_stats['selling_value']   = sum(i.selling_value for i in _items)
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
    context['inventory_stats'] = inventory_stats

    # ── Work Orders / Radni nalozi ────────────────────────────────────────────
    wo_stats = {'total': 0, 'draft': 0, 'in_progress': 0, 'completed': 0, 'today': 0}
    try:
        from work_orders.models import WorkOrder as _WO
        if company:
            import datetime as _dt
            today = _dt.date.today()
            _all = _WO.objects.filter(company=company)
            wo_stats['total']       = _all.count()
            wo_stats['draft']       = _all.filter(status='draft').count()
            wo_stats['in_progress'] = _all.filter(status='in_progress').count()
            wo_stats['completed']   = _all.filter(status='completed').count()
            wo_stats['today']       = _all.filter(scheduled_date=today).count()
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
    context['wo_stats'] = wo_stats


    # ── Synesis integracija ───────────────────────────────────────────────────
    synesis_cfg = None
    try:
        from synesis.models import SynesisConfig
        if company:
            synesis_cfg = SynesisConfig.objects.filter(company=company).first()
    except Exception:
        pass
    context['synesis_cfg'] = synesis_cfg

    # ── Grosmarkt dokumenti ──────────────────────────────────────────────────
    grosmarkt_stats = {
        'otpremnice_count': 0,
        'otkupni_count': 0,
        'recent_otpremnice': [],
        'recent_otkupni': [],
    }
    try:
        from documents.models import Otpremnica, OtkupniBlok
        grosmarkt_stats['otpremnice_count'] = Otpremnica.objects.count()
        grosmarkt_stats['otkupni_count']    = OtkupniBlok.objects.count()
        grosmarkt_stats['recent_otpremnice'] = list(Otpremnica.objects.order_by('-created_at')[:5])
        grosmarkt_stats['recent_otkupni']   = list(OtkupniBlok.objects.order_by('-created_at')[:5])
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
    context['grosmarkt_stats'] = grosmarkt_stats
    # Bank reconciliation stats
    try:
        from konto.models import BankTransaction
        from django.db.models import Sum
        _unm = BankTransaction.objects.filter(company=company, status='unmatched', transaction_type='inflow')
        context['unmatched_bank_count'] = _unm.count()
        context['unmatched_bank_amount'] = _unm.aggregate(t=Sum('amount'))['t'] or 0
    except Exception:
        context['unmatched_bank_count'] = 0
        context['unmatched_bank_amount'] = 0



    # ── Grosmarkt dokumenti ──────────────────────────────────────────────────
    grosmarkt_stats = {
        'otpremnice_count': 0,
        'otkupni_count': 0,
        'recent_otpremnice': [],
        'recent_otkupni': [],
    }
    try:
        from documents.models import Otpremnica, OtkupniBlok
        grosmarkt_stats['otpremnice_count'] = Otpremnica.objects.count()
        grosmarkt_stats['otkupni_count']    = OtkupniBlok.objects.count()
        grosmarkt_stats['recent_otpremnice'] = list(Otpremnica.objects.order_by('-created_at')[:5])
        grosmarkt_stats['recent_otkupni']   = list(OtkupniBlok.objects.order_by('-created_at')[:5])
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
    context['grosmarkt_stats'] = grosmarkt_stats

    return render(request, 'dashboards/company_admin.html', context)


@login_required
def manager_dashboard(request):
    import datetime

    from django.contrib.auth import get_user_model
    from django.db.models import Sum
    from django.utils import timezone
    User = get_user_model()
    today = timezone.now().date()
    week_start = today - datetime.timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    try:
        from projects.models import Project
        from worktime.models import TimeEntry
        team_entries = TimeEntry.objects.filter(date__gte=week_start).select_related('user','project').order_by('-date')[:20]
        pending_approvals = TimeEntry.objects.filter(status='PENDING').count()
        active_projects = Project.objects.filter(status__in=('active','in_progress','open')).order_by('-id')[:8]
        total_hours_week = TimeEntry.objects.filter(date__gte=week_start).aggregate(s=Sum('duration'))['s'] or 0
        total_hours_month = TimeEntry.objects.filter(date__gte=month_start).aggregate(s=Sum('duration'))['s'] or 0
    except Exception:
        team_entries = []; pending_approvals = 0; active_projects = []
        total_hours_week = total_hours_month = 0

    try:
        from appointments.models import Appointment
        team_appointments_today = Appointment.objects.filter(start_time__date=today).select_related('client','service').order_by('start_time')[:10]
        appts_pending = Appointment.objects.filter(status='scheduled').count()
    except Exception:
        team_appointments_today = []; appts_pending = 0

    team_size = User.objects.filter(is_active=True).count()

    return render(request, 'dashboards/manager.html', {
        'team_entries': team_entries, 'pending_approvals': pending_approvals,
        'active_projects': active_projects, 'today': today,
        'total_hours_week': total_hours_week, 'total_hours_month': total_hours_month,
        'team_appointments_today': team_appointments_today, 'appts_pending': appts_pending,
        'team_size': team_size,
    })
@login_required
def worker_dashboard(request):
    import datetime as dt
    from decimal import Decimal

    from django.db.models import Sum
    from django.utils import timezone

    today = timezone.now().date()
    week_start = today - dt.timedelta(days=today.weekday())
    week_end   = week_start + dt.timedelta(days=6)
    month_start = today.replace(day=1)

    # ── Worktime data ──────────────────────────────────────────────────
    try:
        from worktime.models import Project as WTProject
        from worktime.models import TimeEntry
        hours_today = TimeEntry.objects.filter(user=request.user, date=today).aggregate(
            s=Sum('duration'))['s'] or Decimal('0')
        hours_week  = TimeEntry.objects.filter(user=request.user, date__gte=week_start).aggregate(
            s=Sum('duration'))['s'] or Decimal('0')
        hours_month = TimeEntry.objects.filter(user=request.user, date__gte=month_start).aggregate(
            s=Sum('duration'))['s'] or Decimal('0')
        pending_count = TimeEntry.objects.filter(user=request.user, status='PENDING').count()

        try:
            emp = request.user.employeeprofile
            rate = emp.hourly_rate
            daily_target  = emp.daily_hours
            weekly_target = emp.weekly_hours
        except Exception:
            rate = Decimal('20.00')
            daily_target  = Decimal('8.00')
            weekly_target = Decimal('40.00')

        earnings_month = float(hours_month) * float(rate)

        try:
            active_timer = request.user.active_timer
        except Exception:
            active_timer = None

        # Week bars
        week_days = []
        for i in range(7):
            d = week_start + dt.timedelta(days=i)
            h = TimeEntry.objects.filter(user=request.user, date=d).aggregate(
                s=Sum('duration'))['s'] or Decimal('0')
            week_days.append({
                'date': d,
                'day_name': ['Pon','Uto','Sri','Čet','Pet','Sub','Ned'][i],
                'hours': h,
                'is_today': d == today,
                'percentage': min(100, round(float(h) / float(daily_target) * 100)) if daily_target else 0,
            })

        week_progress = min(100, round(float(hours_week) / float(weekly_target) * 100)) if weekly_target else 0
        recent_entries = TimeEntry.objects.filter(
            user=request.user, date__gte=today - dt.timedelta(days=14)
        ).select_related('project').order_by('-date', '-start_time')[:15]

        active_projects = WTProject.objects.filter(status='ACTIVE').order_by('name')
    except Exception as _e:
        import logging; logging.getLogger(__name__).warning(f'worker_dashboard worktime: {_e}')
        hours_today = hours_week = hours_month = 0
        earnings_month = pending_count = week_progress = 0
        daily_target = weekly_target = 8
        active_timer = None
        week_days = []
        recent_entries = []
        active_projects = []

    # ── Interventions ──────────────────────────────────────────────────
    try:
        from interventions.models import HitnaIntervencija
        STATUS_COLORS = HitnaIntervencija.STATUS_COLORS
        my_interventions = HitnaIntervencija.objects.filter(
            assigned_to=request.user
        ).exclude(status__in=['RIJESENO','ESKALIRANO','FAKTURIRANO']).order_by('-created_at')[:5]
        for iv in my_interventions:
            iv.status_color = STATUS_COLORS.get(iv.status, '#888')
    except Exception:
        my_interventions = []

    return render(request, 'dashboards/worker.html', {
        'hours_today':    hours_today,
        'hours_week':     hours_week,
        'hours_month':    hours_month,
        'earnings_month': earnings_month,
        'hourly_rate':    rate if 'rate' in dir() else 20,
        'daily_target':   daily_target,
        'weekly_target':  weekly_target,
        'week_progress':  week_progress,
        'week_start':     week_start,
        'week_end':       week_end,
        'week_days':      week_days,
        'active_timer':   active_timer,
        'active_projects': active_projects,
        'recent_entries': recent_entries,
        'pending_count':  pending_count,
        'my_interventions': my_interventions,
        'today':          today,
        'revenue_labels':  '[]',
        'revenue_data':    '[]',
        'offers_data':     '[]',
        'overdue_invoices': [],
        'overdue_total':   0,
    })


@login_required
def investor_dashboard(request):
    from django.db.models import Sum
    from django.utils import timezone
    company = None
    try:
        company = request.user.profile.company
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
    today = timezone.now().date()
    year_start = today.replace(month=1, day=1)
    month_start = today.replace(day=1)

    try:
        from invoicing.models import Invoice
        inv_qs = Invoice.objects.unscoped()
        if company:
            inv_qs = inv_qs.filter(company=company)
        revenue_ytd = inv_qs.filter(doctype='R', status='PAID', date_issued__year=today.year).aggregate(s=Sum('total'))['s'] or 0
        revenue_month = inv_qs.filter(doctype='R', status='PAID', date_issued__date__gte=month_start).aggregate(s=Sum('total'))['s'] or 0
        unpaid = inv_qs.filter(doctype='R', status__in=('UNPAID','OVERDUE')).aggregate(s=Sum('total'))['s'] or 0
        recent_invoices = inv_qs.filter(doctype='R').order_by('-date_issued')[:6]
        total_invoices = inv_qs.filter(doctype='R').count()
    except Exception:
        revenue_ytd = revenue_month = unpaid = total_invoices = 0
        recent_invoices = []

    try:
        from finance.models import Transaction
        tx_qs = Transaction.objects.unscoped()
        if company:
            tx_qs = tx_qs.filter(company=company)
        income_ytd   = tx_qs.filter(direction='income',  date__gte=year_start).aggregate(s=Sum('amount'))['s'] or 0
        expense_ytd  = tx_qs.filter(direction='expense', date__gte=year_start).aggregate(s=Sum('amount'))['s'] or 0
        income_month  = tx_qs.filter(direction='income',  date__gte=month_start).aggregate(s=Sum('amount'))['s'] or 0
        expense_month = tx_qs.filter(direction='expense', date__gte=month_start).aggregate(s=Sum('amount'))['s'] or 0
        profit_ytd   = income_ytd - expense_ytd
    except Exception:
        income_ytd = expense_ytd = income_month = expense_month = profit_ytd = 0

    try:
        from projects.models import Project
        proj_qs = Project.objects.unscoped()
        if company:
            proj_qs = proj_qs.filter(company=company)
        projects = proj_qs.order_by('-id')[:8]
        active_count = proj_qs.exclude(status__in=('completed','cancelled')).count()
        completed_count = proj_qs.filter(status='completed').count()
    except Exception:
        projects = []; active_count = completed_count = 0

    return render(request, 'dashboards/investor.html', {
        'company': company, 'today': today,
        'revenue_ytd': revenue_ytd, 'revenue_month': revenue_month,
        'unpaid': unpaid, 'total_invoices': total_invoices,
        'recent_invoices': recent_invoices,
        'income_ytd': income_ytd, 'expense_ytd': expense_ytd,
        'income_month': income_month, 'expense_month': expense_month,
        'profit_ytd': profit_ytd,
        'projects': projects, 'active_count': active_count, 'completed_count': completed_count,
    })
@login_required
def partner_dashboard(request):
    from decimal import Decimal

    from django.db.models import Sum
    from django.utils import timezone

    today = timezone.now().date()

    # 1. Invoices
    try:
        from invoicing.models import Invoice
        my_invoices = Invoice.objects.unscoped().filter(client_email=request.user.email).order_by('-date_issued')[:10]
        unpaid_count = my_invoices.filter(status__in=('UNPAID','OVERDUE')).count()
    except Exception:
        my_invoices = []
        unpaid_count = 0

    # 2. Appointments
    try:
        from appointments.models import Appointment
        from partners.models import Partner
        partner_obj = Partner.objects.filter(email=request.user.email).first()
        if partner_obj:
            my_appointments = Appointment.objects.filter(client=partner_obj).order_by('-start_time')[:6]
        else:
            my_appointments = []
    except Exception:
        my_appointments = []

    # 3. Documents
    try:
        from documents.models import Document
        my_docs = Document.objects.unscoped().filter(client_email=request.user.email).order_by('-created_at')[:5]
    except Exception:
        my_docs = []

    # 4. Live Tracking (Burza & Worktime) - MAX SIGURNOST OD CRASHA
    total_budget = Decimal('0')
    total_cost = Decimal('0')
    used_percentage = 0
    time_entries = []
    site_photos = []

    try:
        from burza.models import ProjectLead
        from worktime.models import TimeEntry

        my_leads = ProjectLead.objects.filter(contact_email=request.user.email)

        for lead in my_leads:
            if lead.budget_to:
                total_budget += Decimal(str(lead.budget_to))

        time_entries = TimeEntry.objects.filter(project_lead__in=my_leads).select_related('user').order_by('-date', '-start_time')[:15]

        from worktime.models import ProjectPhoto
        site_photos = ProjectPhoto.objects.filter(project_lead__in=my_leads).select_related('user').order_by('-created_at')[:8]

        agg = TimeEntry.objects.filter(project_lead__in=my_leads).aggregate(total=Sum('billing_amount'))
        if agg and agg['total']:
            total_cost = Decimal(str(agg['total']))

        if total_budget > 0:
            used_percentage = int((total_cost / total_budget) * 100)
            if used_percentage > 100:
                used_percentage = 100

    except Exception as e:
        print(f"Partner Dashboard Tracking Error: {e}")

    return render(request, 'dashboards/partner.html', {
        'my_invoices': my_invoices,
        'unpaid_count': unpaid_count,
        'my_appointments': my_appointments,
        'my_docs': my_docs,
        'total_budget': total_budget,
        'total_cost': total_cost,
        'used_percentage': used_percentage,
        'time_entries': time_entries,
        'site_photos': site_photos,
    })
def health_check(request):
    """Endpoint za monitoring – vraća JSON status svih servisa"""
    from django.db import connection
    from django.http import JsonResponse
    status = {"status": "ok", "services": {}}
    # DB
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        status["services"]["database"] = "ok"
    except Exception as e:
        status["services"]["database"] = f"error: {e}"
        status["status"] = "degraded"
    # Cache
    try:
        from django.core.cache import cache
        cache.set("health_check", "1", 10)
        val = cache.get("health_check")
        status["services"]["cache"] = "ok" if val == "1" else "miss"
    except Exception as e:
        status["services"]["cache"] = f"error: {e}"
    # Gunicorn workers
    try:
        import psutil
        workers = [p for p in psutil.process_iter(["name", "cmdline"])
                   if "gunicorn" in " ".join(p.info.get("cmdline", []))]
        status["services"]["workers"] = len(workers)
    except Exception:
        status["services"]["workers"] = "unknown"
    return JsonResponse(status)

def whatsapp_health(request):
    """API endpoint for WhatsApp gateway health status."""
    from django.conf import settings
    from django.http import JsonResponse

    from core.whatsapp import is_gateway_healthy

    enabled = getattr(settings, 'WAHA_ENABLED', False)
    if not enabled:
        return JsonResponse({'status': 'disabled', 'healthy': False})

    healthy = is_gateway_healthy()
    return JsonResponse({
        'status': 'healthy' if healthy else 'unhealthy',
        'healthy': healthy,
        'gateway_url': 'internal',
        'session': settings.WAHA_SESSION_NAME,
    })


@require_role("superadmin")
@login_required
def update_company_modules(request, subscription_id):
    """Superadmin: toggle individual modules per company subscription."""
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    from registration.models import CompanySubscription
    try:
        sub = CompanySubscription.objects.get(id=subscription_id)
    except CompanySubscription.DoesNotExist:
        from django.http import Http404
        raise Http404
    if request.method == 'POST':
        selected = request.POST.getlist('modules')
        # None means "use plan defaults"; empty list means "no modules"
        # Use override only when different from plan defaults
        from registration.constants import PLAN_MODULES
        plan_defaults = PLAN_MODULES.get(sub.plan, set())
        if set(selected) == plan_defaults:
            sub.modules_override = None   # back to plan defaults
        else:
            sub.modules_override = sorted(selected)
        sub.save()
    return redirect('superadmin_dashboard')


@require_role("superadmin")
@login_required
def start_impersonation(request, company_id):
    """Superadmin/tenant_admin begins impersonating a company."""
    is_su = request.user.is_superuser
    is_ta = False
    try:
        is_ta = request.user.profile.role == 'tenant_admin'
    except Exception:
        pass
    if not is_su and not is_ta:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    # Tenant admin can only impersonate visible companies
    if is_ta and not is_su:
        visible = request.user.profile.get_visible_companies()
        if not visible.filter(id=company_id).exists():
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Nemate pristup ovoj tvrtki.")
    import time

    from django.shortcuts import get_object_or_404

    from accounts.models import ImpersonationLog
    from companies.models import Company

    company = get_object_or_404(Company, id=company_id)

    # Resolve real IP
    x_fwd = request.META.get('HTTP_X_FORWARDED_FOR')
    ip = x_fwd.split(',')[0].strip() if x_fwd else request.META.get('REMOTE_ADDR')

    # Close any existing session first
    old_log = request.session.get('impersonation_log_id')
    if old_log:
        from django.utils import timezone
        ImpersonationLog.objects.filter(id=old_log).update(ended_at=timezone.now())

    log = ImpersonationLog.objects.create(
        superadmin=request.user,
        company=company,
        ip_address=ip,
    )
    request.session['impersonated_company_id'] = str(company.id)
    request.session['impersonation_started_at'] = int(time.time())
    request.session['impersonation_log_id'] = log.id

    messages.success(request, f'Pristupate kao tvrtka: {company.name}')
    return redirect('company_dashboard')


@login_required
def stop_impersonation(request):
    """Superadmin ends the impersonation session."""
    from django.utils import timezone
    log_id = request.session.get('impersonation_log_id')
    if log_id:
        from accounts.models import ImpersonationLog
        ImpersonationLog.objects.filter(id=log_id).update(ended_at=timezone.now())
    for key in ('impersonated_company_id', 'impersonation_started_at', 'impersonation_log_id'):
        request.session.pop(key, None)
    messages.info(request, 'Impersonacija završena. Vraćeni ste u superadmin prikaz.')
    return redirect('superadmin_dashboard')


@require_role("superadmin")
@login_required
def superadmin_companies(request):
    """List all companies; create new ones; change plans; start impersonation."""
    if not request.user.is_superuser:
        return redirect('dashboard')

    import datetime as _dt
    from decimal import Decimal

    from django.contrib.auth import get_user_model
    from django.db.models import Max

    from companies.models import Company
    from registration.constants import PLAN_PRICES
    from registration.models import CompanyRegistration, CompanySubscription
    User = get_user_model()

    error = None

    # ── Inline plan change ────────────────────────────────────────
    if request.method == 'POST' and request.POST.get('action') == 'change_plan':
        company_id = request.POST.get('company_id', '').strip()
        new_plan   = request.POST.get('plan', '').strip()
        if new_plan in ('starter', 'business', 'enterprise') and company_id:
            try:
                company = Company.objects.get(id=company_id)
                sub = company.subscriptions.filter(is_active=True).order_by('-valid_from').first()
                if sub:
                    sub.plan        = new_plan
                    sub.monthly_fee = Decimal(PLAN_PRICES.get(new_plan, '0'))
                    sub.save(update_fields=['plan', 'monthly_fee'])
                else:
                    CompanySubscription.objects.create(
                        company     = company,
                        plan        = new_plan,
                        valid_from  = _dt.date.today(),
                        monthly_fee = Decimal(PLAN_PRICES.get(new_plan, '0')),
                        is_active   = True,
                    )
                messages.success(request, f'Plan za "{company.name}" promijenjen u {new_plan.upper()}.')
            except Company.DoesNotExist:
                error = 'Tvrtka nije pronađena.'
        else:
            error = 'Nevažeći plan.'
        return redirect('superadmin_companies')

    # ── Create new company ────────────────────────────────────────
    if request.method == 'POST' and request.POST.get('action') == 'create':
        name = request.POST.get('name', '').strip()
        oib  = request.POST.get('oib',  '').strip()
        if not name or not oib:
            error = 'Naziv i OIB su obavezni.'
        elif Company.objects.filter(oib=oib).exists():
            error = f'Tvrtka s OIB-om {oib} već postoji.'
        else:
            company = Company.objects.create(
                name          = name,
                oib           = oib,
                address       = request.POST.get('address', ''),
                city          = request.POST.get('city', ''),
                zip_code      = request.POST.get('zip_code', ''),
                country       = request.POST.get('country', 'HR'),
                business_type = request.POST.get('business_type', 'doo'),
            )
            plan = request.POST.get('plan', '')
            if plan in ('starter', 'business', 'enterprise'):
                CompanySubscription.objects.create(
                    company     = company,
                    plan        = plan,
                    valid_from  = _dt.date.today(),
                    monthly_fee = Decimal(PLAN_PRICES.get(plan, '0')),
                    is_active   = True,
                )
            messages.success(request, f'Tvrtka "{name}" uspješno kreirana.')
            return redirect('superadmin_companies')

    # ── Build company table ───────────────────────────────────────
    rows = []
    for c in _get_admin_companies(request).order_by('name'):
        sub        = c.subscriptions.filter(is_active=True).order_by('-valid_from').first()
        user_count = User.objects.filter(profile__company=c, is_active=True).count()
        last_login = User.objects.filter(
            profile__company=c, is_active=True
        ).aggregate(Max('last_login'))['last_login__max']
        rows.append({
            'company':    c,
            'sub':        sub,
            'user_count': user_count,
            'last_login': last_login,
            'valid_until': sub.valid_until if sub else None,
        })

    from accounts.models import ImpersonationLog
    recent_logs = ImpersonationLog.objects.select_related(
        'superadmin', 'company').order_by('-started_at')[:20]

    pending_reg_count = CompanyRegistration.objects.filter(status='pending').count()

    return render(request, 'dashboards/superadmin_companies.html', {
        'rows':              rows,
        'error':             error,
        'recent_logs':       recent_logs,
        'pending_reg_count': pending_reg_count,
    })


# ── SUPERADMIN: BRANCH MANAGEMENT ─────────────────────────────────────────────

@require_role("superadmin")
@login_required
def superadmin_company_branches(request, company_id):
    """Add, edit and remove branches for a specific company."""
    if not (request.user.is_superuser or request.user.is_staff):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    from django.contrib import messages as _msg
    from django.shortcuts import get_object_or_404

    from companies.models import Company, CompanyBranch

    company = get_object_or_404(Company, pk=company_id)
    branches = CompanyBranch.objects.filter(umbrella_parent=company).order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            name        = request.POST.get('name', '').strip()
            branch_type = request.POST.get('branch_type', 'other')
            address     = request.POST.get('address', '').strip()
            city        = request.POST.get('city', '').strip()
            phone       = request.POST.get('phone', '').strip()
            email       = request.POST.get('email', '').strip()
            branch_code = request.POST.get('branch_code', '').strip()
            modules_raw = request.POST.getlist('active_modules')

            if not name:
                _msg.error(request, 'Naziv podružnice je obavezan.')
            else:
                try:
                    CompanyBranch.objects.create(
                        umbrella_parent=company,
                        name=name,
                        branch_type=branch_type,
                        address=address,
                        city=city,
                        phone=phone,
                        email=email,
                        branch_code=branch_code,
                        active_modules=modules_raw,
                    )
                    _msg.success(request, f'Podružnica "{name}" kreirana.')
                except Exception as e:
                    _msg.error(request, f'Greška: {e}')

        elif action == 'toggle':
            branch_id = request.POST.get('branch_id')
            try:
                b = CompanyBranch.objects.get(pk=branch_id, umbrella_parent=company)
                b.is_active = not b.is_active
                b.save()
                _msg.success(request, f'{"Aktivirana" if b.is_active else "Deaktivirana"}: {b.name}')
            except CompanyBranch.DoesNotExist:
                _msg.error(request, 'Podružnica nije pronađena.')

        elif action == 'delete':
            branch_id = request.POST.get('branch_id')
            try:
                b = CompanyBranch.objects.get(pk=branch_id, umbrella_parent=company)
                name = b.name
                b.delete()
                _msg.success(request, f'Podružnica "{name}" izbrisana.')
            except CompanyBranch.DoesNotExist:
                _msg.error(request, 'Podružnica nije pronađena.')

        elif action == 'update_modules':
            branch_id   = request.POST.get('branch_id')
            modules_raw = request.POST.getlist('active_modules')
            try:
                b = CompanyBranch.objects.get(pk=branch_id, umbrella_parent=company)
                b.active_modules = modules_raw
                b.save()
                _msg.success(request, f'Moduli ažurirani za {b.name}.')
            except CompanyBranch.DoesNotExist:
                _msg.error(request, 'Podružnica nije pronađena.')

        return redirect('superadmin_company_branches', company_id=company_id)

    # All available modules for checkbox list
    ALL_MODULES = [
        ('invoicing',   'Fakturiranje'),
        ('pos',         'POS blagajna'),
        ('inventory',   'Zalihe'),
        ('appointments','Termini'),
        ('projects',    'Projekti'),
        ('worktime',    'Radni sati'),
        ('partners',    'Partneri'),
        ('documents',   'Dokumenti'),
        ('finance',     'Financije'),
        ('calculator',  'Kalkulator'),
        ('fitness',     'Fitness'),
        ('rental',      'Najam'),
        ('webshop',     'Webshop'),
        ('assessment',  'Procjene'),
        ('interventions','Intervencije'),
    ]

    return render(request, 'dashboards/company_branches.html', {
        'company':     company,
        'branches':    branches,
        'all_modules': ALL_MODULES,
        'branch_types': CompanyBranch.BRANCH_TYPES,
    })

@login_required
def superadmin_create_promo(request):
    """Superadmin kreiranje promo koda."""
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    if request.method == 'POST':
        try:
            from decimal import Decimal

            from registration.models import PromoCode
            PromoCode.objects.create(
                code=request.POST.get('code', '').upper().strip(),
                name=request.POST.get('name', '').strip(),
                promo_type=request.POST.get('promo_type', 'free_months'),
                discount_percent=int(request.POST.get('discount_percent') or 0),
                discount_amount=Decimal(request.POST.get('discount_amount') or '0'),
                free_months=int(request.POST.get('free_months') or 0),
                target_plan=request.POST.get('target_plan', '').strip(),
                max_uses=int(request.POST.get('max_uses') or 0),
                is_active=True,
            )
            messages.success(request, 'Promo kod kreiran.')
        except Exception as e:
            logger.exception("Unexpected error", exc_info=True)
            messages.error(request, f'Greška: {e}')
    return redirect('superadmin_dashboard')



def impressum(request):
    host = request.get_host().split(":")[0]
    if "viskovic" in host:
        return render(request, "legal/impressum_de.html")
    return render(request, "legal/impressum_hr.html")

def datenschutz(request):
    host = request.get_host().split(":")[0]
    if "viskovic" in host:
        return render(request, "legal/datenschutz_de.html")
    return render(request, "legal/privatnost_hr.html")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 12: Control Tower — Live Telemetry Dashboard
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(lambda u: u.is_superuser)
def control_tower_view(request):
    """Renders the Control Tower dashboard page with full context."""
    from django.utils import timezone
    import datetime

    user = request.user
    now = timezone.now()
    today = now.date()

    # ── User info ──
    profile = getattr(user, 'profile', None)
    role = getattr(profile, 'role', 'superadmin' if user.is_superuser else 'user')
    company = getattr(profile, 'company', None)

    # ── Company info ──
    company_data = None
    if company:
        company_data = {
            'name': company.name,
            'oib': getattr(company, 'oib', ''),
            'address': getattr(company, 'address', ''),
            'city': getattr(company, 'city', ''),
            'plan': getattr(company, 'plan', 'standard'),
            'created': getattr(company, 'created_at', None),
        }

    # If superadmin and no company, get platform-wide stats
    if user.is_superuser and not company:
        try:
            from companies.models import Company
            company_data = {
                'name': 'PLATFORMA (sve tvrtke)',
                'oib': '',
                'address': '',
                'city': '',
                'plan': 'superadmin',
                'total_companies': Company.objects.count(),
            }
        except Exception:
            company_data = {'name': 'PLATFORMA', 'plan': 'superadmin'}

    # ── Recent activity (last 10 admin actions) ──
    recent_actions = []
    try:
        from django.contrib.admin.models import LogEntry
        entries = LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:10]
        for e in entries:
            recent_actions.append({
                'user': e.user.get_full_name() or e.user.username,
                'action': e.get_action_flag_display(),
                'object': str(e.object_repr)[:50],
                'model': e.content_type.model if e.content_type else '?',
                'time': e.action_time,
            })
    except Exception:
        pass

    # ── System info ──
    import django
    import platform
    system_info = {
        'django_version': django.get_version(),
        'python_version': platform.python_version(),
        'server_time': now,
        'server_date': today,
    }

    # DB size
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
            system_info['db_size'] = cursor.fetchone()[0]
    except Exception:
        system_info['db_size'] = 'N/A'

    # Uptime (Linux)
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            system_info['uptime'] = f'{days}d {hours}h'
    except Exception:
        system_info['uptime'] = 'N/A'

    # Disk usage
    try:
        import shutil
        total, used, free = shutil.disk_usage('/')
        system_info['disk_total'] = f'{total // (1024**3)} GB'
        system_info['disk_used'] = f'{used // (1024**3)} GB'
        system_info['disk_free'] = f'{free // (1024**3)} GB'
        system_info['disk_pct'] = round(used / total * 100, 1)
    except Exception:
        system_info['disk_pct'] = 0

    # ── AI Process Hints ──
    ai_hints = []
    if company:
        try:
            from core.services.ai_hints import generate_hints
            ai_hints = generate_hints(company, user=user)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'AI hints: {e}')

    # ── Module counters for drill-down ──
    drill_down = {}
    if company:
        try:
            from companies.module_registry import MODULES
            from django.apps import apps
            for m in MODULES:
                cm = m.get('counter_model')
                if cm:
                    try:
                        app_label, model_name = cm.split('.')
                        Model = apps.get_model(app_label, model_name)
                        drill_down[m['id']] = {
                            'name': m['name'],
                            'icon': m['icon'],
                            'url': m['url'],
                            'count': Model.objects.filter(company=company).count(),
                        }
                    except Exception:
                        pass
        except Exception:
            pass

    context = {
        'ai_hints': ai_hints,
        'drill_down': drill_down,
        'ct_user': {
            'username': user.username,
            'full_name': user.get_full_name() or user.username,
            'email': user.email,
            'role': role,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'last_login': user.last_login,
            'date_joined': user.date_joined,
        },
        'ct_company': company_data,
        'recent_actions': recent_actions,
        'system_info': system_info,
    }
    return render(request, 'dashboards/control_tower.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def control_tower_api(request):
    """
    GET /superadmin/api/telemetry/
    Returns live platform metrics as JSON — polled every 15s by frontend.
    Uses ORM aggregates to eliminate N+1 queries.
    """
    from django.db.models import Count, Sum, Q
    from django.utils import timezone
    from django.http import JsonResponse
    import datetime

    now = timezone.now()
    today = now.date()
    month_start = today.replace(day=1)

    data = {}

    # ── Users ────────────────────────────────────────────────────────────
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_agg = User.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            staff=Count('id', filter=Q(is_staff=True)),
            superusers=Count('id', filter=Q(is_superuser=True)),
        )
        data['users'] = user_agg
    except Exception:
        data['users'] = {'total': 0, 'active': 0, 'staff': 0, 'superusers': 0}

    # ── Companies ────────────────────────────────────────────────────────
    try:
        from companies.models import Company
        data['companies'] = {'total': Company.objects.count()}
    except Exception:
        data['companies'] = {'total': 0}

    # ── Invoices ─────────────────────────────────────────────────────────
    try:
        from invoicing.models import Invoice
        inv_agg = Invoice.objects.unscoped().filter(doctype='R').aggregate(
            total=Count('id'),
            paid_revenue=Sum('total', filter=Q(status='PAID')),
            month_revenue=Sum('total', filter=Q(status='PAID', date_issued__date__gte=month_start)),
            unpaid=Sum('total', filter=Q(status__in=('UNPAID', 'OVERDUE'))),
            draft_count=Count('id', filter=Q(status='DRAFT')),
            overdue_count=Count('id', filter=Q(status='OVERDUE')),
        )
        data['invoices'] = {
            'total': inv_agg['total'] or 0,
            'paid_revenue': float(inv_agg['paid_revenue'] or 0),
            'month_revenue': float(inv_agg['month_revenue'] or 0),
            'unpaid': float(inv_agg['unpaid'] or 0),
            'draft_count': inv_agg['draft_count'] or 0,
            'overdue_count': inv_agg['overdue_count'] or 0,
        }
    except Exception:
        data['invoices'] = {'total': 0, 'paid_revenue': 0, 'month_revenue': 0,
                            'unpaid': 0, 'draft_count': 0, 'overdue_count': 0}

    # ── POS ──────────────────────────────────────────────────────────────
    try:
        from pos.models import POSSession
        pos_agg = POSSession.objects.aggregate(
            today=Count('id', filter=Q(opened_at__date=today)),
            open_now=Count('id', filter=Q(status='open')),
        )
        data['pos'] = pos_agg
    except Exception:
        data['pos'] = {'today': 0, 'open_now': 0}

    # ── Appointments ─────────────────────────────────────────────────────
    try:
        from appointments.models import Appointment
        appt_agg = Appointment.objects.aggregate(
            today=Count('id', filter=Q(start_time__date=today)),
            total=Count('id'),
        )
        data['appointments'] = appt_agg
    except Exception:
        data['appointments'] = {'today': 0, 'total': 0}

    # ── Delivery / Logistics ─────────────────────────────────────────────
    try:
        from delivery.models import ConsolidatedDelivery
        del_agg = ConsolidatedDelivery.objects.aggregate(
            in_transit=Count('id', filter=Q(status='in_transit')),
            total=Count('id'),
        )
        data['deliveries'] = del_agg
    except Exception:
        data['deliveries'] = {'in_transit': 0, 'total': 0}

    # ── HACCP Incidents (delivery.models.HACCPIncident) ──────────────────
    try:
        from delivery.models import HACCPIncident
        haccp_agg = HACCPIncident.objects.aggregate(
            total=Count('id'),
            unresolved=Count('id', filter=Q(is_resolved=False)),
            critical=Count('id', filter=Q(is_resolved=False, severity='critical')),
        )
        data['haccp'] = haccp_agg
    except Exception:
        data['haccp'] = {'total': 0, 'unresolved': 0, 'critical': 0}

    # ── Inventory — Blind Count / Quarantine ─────────────────────────────
    try:
        from inventory.models import StockBatch, InventoryCountLog
        inv_agg2 = StockBatch.objects.aggregate(
            quarantined=Count('id', filter=Q(quarantine_status='quarantine')),
            total_batches=Count('id'),
        )
        count_today = InventoryCountLog.objects.filter(counted_at__date=today).count()
        theft_alerts = InventoryCountLog.objects.filter(
            result='theft_alert', counted_at__date__gte=month_start
        ).count()
        data['inventory'] = {
            'quarantined_batches': inv_agg2['quarantined'] or 0,
            'total_batches': inv_agg2['total_batches'] or 0,
            'counts_today': count_today,
            'theft_alerts_month': theft_alerts,
        }
    except Exception:
        data['inventory'] = {'quarantined_batches': 0, 'total_batches': 0,
                             'counts_today': 0, 'theft_alerts_month': 0}

    # ── Worktime ─────────────────────────────────────────────────────────
    try:
        from worktime.models import TimeEntry
        wt_agg = TimeEntry.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='PENDING')),
            today=Count('id', filter=Q(date=today)),
            compliance_issues=Count('id', filter=~Q(compliance_note='')),
        )
        data['worktime'] = wt_agg
    except Exception:
        data['worktime'] = {'total': 0, 'pending': 0, 'today': 0, 'compliance_issues': 0}

    # ── Webshop ──────────────────────────────────────────────────────────
    try:
        from webshop.models import Product, Order
        ws_agg = Product.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            food=Count('id', filter=Q(category='FOOD')),
            optics=Count('id', filter=Q(category='OPTICS')),
        )
        orders_pending = Order.objects.filter(status='pending').count()
        data['webshop'] = {**ws_agg, 'orders_pending': orders_pending}
    except Exception:
        data['webshop'] = {'total': 0, 'active': 0, 'food': 0, 'optics': 0, 'orders_pending': 0}

    # ── AI Assistant ─────────────────────────────────────────────────────
    try:
        from ai_assistant.models import AIUsageLog, Conversation
        ai_agg = AIUsageLog.objects.aggregate(
            total_calls=Count('id'),
            total_cost=Sum('cost_estimate'),
        )
        ai_convos = Conversation.objects.filter(is_active=True).count()
        data['ai'] = {
            'total_calls': ai_agg['total_calls'] or 0,
            'total_cost': float(ai_agg['total_cost'] or 0),
            'active_conversations': ai_convos,
        }
    except Exception:
        data['ai'] = {'total_calls': 0, 'total_cost': 0, 'active_conversations': 0}

    # ── Burza ────────────────────────────────────────────────────────────
    try:
        from burza.models import ProjectLead
        latest = list(ProjectLead.objects.filter(status='NOVI_UPIT').order_by('-created_at')[:3].values('pk','title','contact_name','created_at'))
        for l in latest:
            l['created_at'] = l['created_at'].strftime('%d.%m %H:%M')
            l['title'] = l['title'][:35]
        data['burza'] = {
            'new_leads': ProjectLead.objects.filter(status='NOVI_UPIT').count(),
            'public':    ProjectLead.objects.filter(status='NA_BURZI').count(),
            'latest':    latest,
        }
    except Exception:
        data['burza'] = {'new_leads': 0}

    # ── Registration ─────────────────────────────────────────────────────
    try:
        from registration.models import CompanyRegistration
        data['registrations'] = {
            'pending': CompanyRegistration.objects.filter(status='pending').count()
        }
    except Exception:
        data['registrations'] = {'pending': 0}


    # ── Financial Radar (V3) ─────────────────────────────────────────────
    try:
        from konto.models import BankAccount, BankTransaction
        from invoicing.models import Invoice
        from finance.bank_parsers import get_partial_payment_discrepancies
        import datetime as _dt

        _co = None
        try:
            from companies.models import Company as _Comp
            _co = _Comp.objects.first()
        except Exception:
            pass

        disc = get_partial_payment_discrepancies(_co) if _co else []
        gap_total = float(sum(d['gap'] for d in disc))

        cash_now = float(
            BankAccount.objects.filter(is_active=True).aggregate(
                t=Sum('current_balance'))['t'] or 0
        )

        next_7 = today + _dt.timedelta(days=7)
        expected_inflows = float(
            Invoice.objects.unscoped().filter(
                doctype='R', status__in=('SENT', 'UNPAID'),
                date_due__gte=today, date_due__lte=next_7,
            ).aggregate(t=Sum('total'))['t'] or 0
        )
        overdue_outflows = float(
            Invoice.objects.unscoped().filter(
                doctype='R', status='OVERDUE',
            ).aggregate(t=Sum('total'))['t'] or 0
        )
        forecast_7d = cash_now + expected_inflows - overdue_outflows

        from konto.models import KontoAccount
        revenue_total = float(
            KontoAccount.objects.filter(
                account_type='income', is_active=True,
            ).aggregate(t=Sum('ledgerline_entries__amount'))['t'] or 0
        )
        expense_total = float(
            KontoAccount.objects.filter(
                account_type='expense', is_active=True,
            ).aggregate(t=Sum('ledgerline_entries__amount'))['t'] or 0
        )
        margin_pct = round(
            ((revenue_total - expense_total) / revenue_total * 100)
            if revenue_total > 0 else 0, 1
        )

        data['finance_radar'] = {
            'gap_count': len(disc),
            'gap_total': gap_total,
            'cash_now': cash_now,
            'expected_inflows_7d': expected_inflows,
            'overdue_outflows': overdue_outflows,
            'forecast_7d': forecast_7d,
            'revenue_total': revenue_total,
            'expense_total': expense_total,
            'margin_pct': margin_pct,
        }
    except Exception:
        data['finance_radar'] = {
            'gap_count': 0, 'gap_total': 0, 'cash_now': 0,
            'expected_inflows_7d': 0, 'overdue_outflows': 0,
            'forecast_7d': 0, 'revenue_total': 0, 'expense_total': 0,
            'margin_pct': 0,
        }

    # ── HelpDesk ─────────────────────────────────────────────────────────
    try:
        from helpdesk.models import Ticket
        from django.utils import timezone as tz
        hd_qs = Ticket.objects.all()
        open_statuses = ['open ', 'in_progress', 'waiting_client', 'waiting_internal']
        closed_statuses = ['resolved', 'closed']
        open_qs = hd_qs.filter(status__in=open_statuses)
        data['helpdesk'] = {
            'open ': open_qs.count(),
            'urgent': open_qs.filter(priority__in=['urgent', 'critical']).count(),
            'overdue': sum(1 for t in open_qs.select_related() if t.is_overdue),
            'resolved_today': hd_qs.filter(
                status__in=closed_statuses,
                updated_at__date=today
            ).count(),
            'unassigned': open_qs.filter(assigned_to__isnull=True).count(),
        }
    except Exception as e:
        data['helpdesk'] = {'open ': 0, 'urgent': 0, 'overdue': 0, 'resolved_today': 0, 'unassigned': 0}

    data['timestamp'] = now.isoformat()

    # ── Arhiva / AI Inbox ────────────────────────────────────────────────
    try:
        from documents.models import ArhivaEntry
        from django.db.models import Sum as _Sum
        arhiva_total = ArhivaEntry.objects.count()
        ai_pending = ArhivaEntry.objects.filter(is_booked=False).exclude(
            ai_proposal__isnull=True).exclude(ai_proposal={}).count()
        year_invoices = ArhivaEntry.objects.filter(
            source_type='invoice_out', doc_date__year=today.year
        ).aggregate(total=_Sum('amount'))['total'] or 0
        recent_5 = list(ArhivaEntry.objects.order_by('-archived_at')[:5].values(
            'id', 'doc_number', 'partner_name', 'amount', 'source_type', 'archived_at'
        ))
        for r in recent_5:
            r['amount'] = float(r['amount']) if r['amount'] else 0
            r['archived_at'] = r['archived_at'].isoformat() if r['archived_at'] else None
        data['arhiva'] = {
            'total': arhiva_total,
            'ai_pending': ai_pending,
            'year_invoice_total': float(year_invoices),
            'recent': recent_5,
        }
    except Exception:
        data['arhiva'] = {'total': 0, 'ai_pending': 0, 'year_invoice_total': 0, 'recent': []}

    return JsonResponse(data)


# ══════════════════════════════════════════════════════════════════════════════
# SMART ROUTER — unified entry point (replaces duplicate homepage/dashboard)
# ══════════════════════════════════════════════════════════════════════════════

def smart_home(request):
    """
    Single entry point for / and /dashboard/.
    - viskovic-group.de → public Viskovic website
    - authenticated users → role-appropriate dashboard
    - anonymous → login page
    """
    from django.shortcuts import render, redirect

    # Public website for viskovic-group.de
    host = request.get_host().split(':')[0].lower()
    if 'viskovic-group' in host:
        return render(request, 'viskovic_group_index.html')

    # limit-connect.com public landing page
    if 'fina-connect' in host and not request.user.is_authenticated:
        return render(request, 'fina_connect_landing.html')

    # All other domains require login
    if not request.user.is_authenticated:
        return redirect('login')

    user = request.user

    if user.is_superuser:
        return redirect('control_tower')

    # Check profile role
    role = getattr(getattr(user, 'profile', None), 'role', None)

    if role == 'manager' or (user.is_staff and not user.is_superuser):
        return redirect('manager_dashboard')
    elif role == 'investor':
        return redirect('investor_dashboard')
    elif role == 'partner':
        return redirect('partner_dashboard')
    elif role == 'worker':
        return redirect('worker_dashboard')
    else:
        return redirect('company_dashboard')


# ══════════════════════════════════════════════════════════════
# REVIZORSKI PAKET — Streaming ZIP download
# ══════════════════════════════════════════════════════════════

@login_required
def audit_package(request):
    """
    Generiraj kompletni revizorski paket (streaming ZIP).
    Sadrži: artikli, POS izvještaji, bonovi, prigovori, inventure, fiskalni logovi.
    GET ?from=2025-01-01&to=2025-12-31
    """
    from core.company_utils import get_user_company
    from core.streaming_zip import build_audit_package
    from datetime import date, datetime

    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema konteksta tvrtke.')
        return redirect('home')

    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')
    try:
        d_from = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else date.today().replace(month=1, day=1)
        d_to = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else date.today()
    except ValueError:
        d_from = date.today().replace(month=1, day=1)
        d_to = date.today()

    return build_audit_package(company, d_from, d_to)


@login_required
def ivan_cockpit(request):
    _cockpit_users = {'superadmin', 'marija.brtan'}
    if not request.user.is_superuser and request.user.username not in _cockpit_users:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import timedelta
    import subprocess
    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_start = today.replace(day=1)
    from django.contrib.auth.models import User
    from companies.models import Company
    from registration.models import CompanySubscription
    from pos.models import POSReceipt, POSSession, POSTerminal, ImprovementSuggestion
    from invoicing.models import Invoice
    from documents.models import ArhivaEntry
    from eracun.models import ERacun
    subs = list(CompanySubscription.objects.filter(is_active=True).select_related('company').order_by('-monthly_fee'))
    mrr = sum(float(s.monthly_fee or 0) for s in subs)
    pos_today_qs = POSReceipt.objects.filter(created_at__date=today, status='paid')
    # pos_by_company — template koristi row.b i row.p (kratki aliasi)
    pos_by_company = list(POSReceipt.objects.filter(
        created_at__date=today, status='paid'
    ).values('session__terminal__company__name').annotate(
        promet=Sum('total'), bonovi=Count('id'), p=Sum('total'), b=Count('id')
    ).order_by('-promet'))
    try:
        disk=subprocess.check_output(['df','-h','/'],text=True).split('\n')[1].split()
        # disk: [device, total, used, free, pct, mount]
        disk_used = disk[2]   # 30G
        disk_free = disk[3]   # 114G
        disk_pct  = disk[4]   # 21%
        disk_info = f"{disk_pct} ({disk_free} slobodno)"
    except:
        disk_used = disk_free = disk_pct = disk_info = 'N/A'
    try:
        mem=subprocess.check_output(['free','-h'],text=True).split('\n')[1].split()
        # mem: [Mem:, total, used, free, shared, buff, available]
        mem_used  = mem[2]   # 4.7Gi
        mem_total = mem[1]   # 7.6Gi
        mem_info  = f"{mem_used} / {mem_total}"
    except:
        mem_used = mem_total = mem_info = 'N/A'
    try:
        logs_raw=subprocess.check_output(['tail','-30','/var/www/fina-connect/logs/django.log'],text=True).strip().split('\n')
        recent_logs=[l for l in logs_raw if any(k in l for k in ['ERROR','WARNING','INFO whatsapp'])][-8:]
    except: recent_logs=[]
    _pos_promet = pos_today_qs.aggregate(t=Sum('total'))['t'] or 0
    _pos_bonovi = pos_today_qs.count()
    _pos_open   = POSSession.objects.filter(status='open').count()
    _pos_week   = POSReceipt.objects.filter(
        created_at__gte=week_ago, status='paid'
    ).aggregate(t=Sum('total'))['t'] or 0
    _inv_count  = Invoice.objects.filter(date_issued__date__gte=month_start).count()
    _inv_promet = Invoice.objects.filter(date_issued__date__gte=month_start).aggregate(t=Sum('total'))['t'] or 0
    context={
        'now':now,'today':today,
        'users_total':User.objects.count(),
        'users_active_week':User.objects.filter(last_login__gte=week_ago).count(),
        'users_week':User.objects.filter(last_login__gte=week_ago).count(),
        'users_never':User.objects.filter(last_login__isnull=True,is_active=True).count(),
        'companies':Company.objects.count(),
        'subs':subs,'mrr':mrr,
        'pos_promet_danas':_pos_promet, 'pos_promet':_pos_promet,
        'pos_bonovi_danas':_pos_bonovi, 'pos_bonovi':_pos_bonovi,
        'pos_open_sessions':_pos_open,  'pos_open':_pos_open,
        'pos_terminal_count':POSTerminal.objects.filter(is_active=True).count(),
        'pos_week':_pos_week,
        'pos_by_company':pos_by_company,
        'invoices_month':_inv_count,  'inv_count':_inv_count,
        'invoices_promet':_inv_promet,'inv_promet':_inv_promet,
        'eracun_total':ERacun.objects.count(),
        'eracun_sent':ERacun.objects.filter(status='sent').count(),
        'arhiva_total':ArhivaEntry.objects.count(), 'arhiva':ArhivaEntry.objects.count(),
        'disk_info':disk_info, 'disk_used':disk_used, 'disk_free':disk_free,
        'mem_info':mem_info,   'mem_used':mem_used,   'mem_total':mem_total,
        'recent_logs':recent_logs, 'logs':recent_logs,
        'feedback':ImprovementSuggestion.objects.filter(status='new').order_by('-created_at')[:5],
    }
    # API key + cert health check
    try:
        import anthropic, os
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if api_key:
            try:
                c = anthropic.Anthropic(api_key=api_key)
                c.messages.create(model='claude-haiku-4-5-20251001', max_tokens=5, messages=[{'role':'user','content':'ok'}])
                context['api_status'] = 'ok'
                context['api_key_short'] = api_key[:12] + '...' + api_key[-4:]
            except anthropic.BadRequestError as e:
                if 'credit balance' in str(e):
                    context['api_status'] = 'no_credit'
                else:
                    context['api_status'] = 'error'
                context['api_error'] = str(e)[:100]
                context['api_key_short'] = api_key[:12] + '...' + api_key[-4:]
            except Exception as e:
                context['api_status'] = 'error'
                context['api_error'] = str(e)[:100]
        else:
            context['api_status'] = 'missing'
    except Exception:
        context['api_status'] = 'unknown'

    # Cert expiry
    try:
        from eracun.services.cert_monitor import check_all_certs
        certs = check_all_certs()
        context['certs'] = certs
        context['certs_expiring'] = [c for c in certs if c.get('status') in ('CRITICAL','WARNING','ATTENTION','EXPIRED')]
    except Exception:
        context['certs'] = []
        context['certs_expiring'] = []

    return render(request,'dashboards/ivan_cockpit.html',context)

@login_required
@require_POST
def cockpit_gemini_task(request):
    """Pokreni Gemini agenta iz Fenix Cockpit-a."""
    _cockpit_users = {'superadmin', 'marija.brtan'}
    if not request.user.is_superuser and request.user.username not in _cockpit_users:
        return JsonResponse({'ok': False, 'error': 'Nemas pristup'}, status=403)
    import json as _json
    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    task_desc = data.get('task', '').strip()
    if not task_desc:
        return JsonResponse({'ok': False, 'error': 'Task prazan'}, status=400)
    max_steps = min(int(data.get('max_steps', 10)), 20)
    from core.gemini_tasks import run_gemini_task
    result = run_gemini_task.delay(task_desc, max_steps=max_steps, requested_by=request.user.username)
    return JsonResponse({'ok': True, 'task_id': str(result.id)})


@login_required
def cockpit_upload_photo(request):
    """API: Upload fotke iz Fenix Cockpit okruglog stola."""
    _cockpit_users = {'superadmin', 'marija.brtan'}
    if not request.user.is_superuser and request.user.username not in _cockpit_users:
        return JsonResponse({'ok': False, 'error': 'Nemas pristup'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    photo = request.FILES.get('photo')
    if not photo:
        return JsonResponse({'ok': False, 'error': 'Nema slike'}, status=400)
    seat = request.POST.get('seat', 'unknown')
    message = request.POST.get('message', '')[:200]
    import os, uuid
    ext = os.path.splitext(photo.name)[1] or '.jpg'
    filename = 'cockpit_%s_%s%s' % (seat, uuid.uuid4().hex[:8], ext)
    save_dir = '/var/www/fina-connect/media/cockpit/'
    os.makedirs(save_dir, exist_ok=True)
    filepath = os.path.join(save_dir, filename)
    with open(filepath, 'wb') as f:
        for chunk in photo.chunks():
            f.write(chunk)
    import json
    log_path = os.path.join(save_dir, 'feed.json')
    try:
        with open(log_path, 'r') as f:
            feed = json.load(f)
    except Exception:
        feed = []
    feed.insert(0, {
        'filename': filename, 'url': '/media/cockpit/%s' % filename,
        'seat': seat, 'user': request.user.username, 'message': message,
        'time': timezone.now().strftime('%H:%M'), 'date': timezone.now().strftime('%d.%m.'),
        'uploaded_at': timezone.now().isoformat(),
    })
    feed = feed[:50]
    with open(log_path, 'w') as f:
        json.dump(feed, f, ensure_ascii=False)
    return JsonResponse({'ok': True, 'url': '/media/cockpit/%s' % filename})


@login_required
def cockpit_photos(request):
    """API: Dohvati feed fotki iz cockpita."""
    import json, os
    log_path = '/var/www/fina-connect/media/cockpit/feed.json'
    try:
        with open(log_path, 'r') as f:
            feed = json.load(f)
    except Exception:
        feed = []
    return JsonResponse({'photos': feed[:20]})


@login_required
def cockpit_send_whatsapp(request):
    """API: Pošalji WhatsApp iz Fenix Cockpit okruglog stola."""
    _cockpit_users = {'superadmin', 'marija.brtan'}
    if not request.user.is_superuser and request.user.username not in _cockpit_users:
        return JsonResponse({'ok': False, 'error': 'Nemas pristup'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    import json as _json
    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    phone = data.get('phone', '').strip()
    message = data.get('message', '').strip()
    seat = data.get('seat', '')
    if not phone or not message:
        return JsonResponse({'ok': False, 'error': 'phone i message obavezni'}, status=400)
    try:
        from core.whatsapp_tasks import send_whatsapp_text_task
        send_whatsapp_text_task.delay(phone, message)
        from superadmin_ai.models import PendingAIAction
        PendingAIAction.objects.create(
            module='cockpit', action_type='whatsapp_sent',
            description='[COCKPIT→%s] %s' % (seat.upper(), message[:100]),
            status='executed', payload={'phone': phone, 'seat': seat},
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)[:100]}, status=500)


@login_required
def tim_chat(request):
    from pos.models import ImprovementSuggestion
    qs = ImprovementSuggestion.objects.filter(author=request.user).order_by('-created_at')[:10]
    return render(request, 'dashboards/tim_chat.html', {'user_messages': qs})


@login_required
def tim_chat(request):
    from pos.models import ImprovementSuggestion
    qs = ImprovementSuggestion.objects.filter(
        author=request.user
    ).order_by('-created_at')[:10]
    return render(request, 'dashboards/tim_chat.html', {'user_messages': qs})


@login_required
def tim_chat(request):
    from pos.models import ImprovementSuggestion
    qs = ImprovementSuggestion.objects.filter(
        author=request.user
    ).order_by('-created_at')[:10]
    return render(request, 'dashboards/tim_chat.html', {'user_messages': qs})

@login_required
@require_POST  
def tim_chat_send(request):
    from django.http import JsonResponse
    import json as _json
    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    desc = data.get('description','').strip()
    if not desc:
        return JsonResponse({'error': 'Prazna poruka'}, status=400)
    from pos.models import ImprovementSuggestion
    from core.company_utils import get_user_company
    s = ImprovementSuggestion.objects.create(
        company=get_user_company(request),
        author=request.user,
        source='user',
        title='Tim Chat: ' + desc[:50],
        description=desc,
        category=data.get('module','tim_chat'),
        priority=int(data.get('priority',2)),
        status='new',
    )
    return JsonResponse({'ok': True, 'id': str(s.id), 'message': 'Poruka primljena ✅'})


def promo_page(request):
    return render(request, 'website/promo_hr.html')

def promo_page_de(request):
    return render(request, 'website/promo_de.html')


def promo_opg(request):
    return render(request, 'website/promo_opg.html')


@csrf_exempt
def partner_signup_api(request):
    """Public API: Online registracija Tippgeber/Posrednik partnera."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()
    country = request.POST.get('country', 'DE')
    address = request.POST.get('address', '').strip()
    tax_id = request.POST.get('tax_id', '').strip()
    iban = request.POST.get('iban', '').strip()
    region = request.POST.get('region', '').strip()
    lang = request.POST.get('lang', 'de')

    if not first_name or not last_name or not email or not phone or not iban:
        return JsonResponse({'ok': False, 'error': 'Pflichtfelder fehlen / Obavezna polja nedostaju'}, status=400)

    # Provjeri duplikat
    from partners.models import Partner
    from companies.models import Company
    konjik = Company.objects.filter(oib='37590751921').first()
    if not konjik:
        konjik = Company.objects.first()

    existing = Partner.objects.filter(company=konjik, email=email).first()
    if existing:
        return JsonResponse({'ok': False, 'error': 'E-Mail bereits registriert / Email već registriran'}, status=400)

    # Kreiraj partnera
    partner = Partner.objects.create(
        company=konjik,
        name='%s %s' % (first_name, last_name),
        email=email,
        phone=phone,
        oib=tax_id or ('AGT-%s' % email[:8]),
        address=address,
        country=country,
        partner_type='agent',
        payment_term=14,
    )

    # Kreiraj referral kod
    import hashlib
    from django.utils import timezone
    from partners.models import AgentReferral
    ref_code = 'REF-%s-%s' % (
        last_name[:5].upper().replace(' ', ''),
        hashlib.md5(email.encode()).hexdigest()[:4].upper()
    )
    AgentReferral.objects.create(
        agent=partner,
        referred_company=konjik,  # placeholder — ažurira se kad agent dovede klijenta
        referral_code=ref_code,
        status='pending',
        commission_percent=20,
        commission_months=12,
        agent_iban=iban,
        contract_signed_at=timezone.now(),
        contract_ip=request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')),
        contract_user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
        expires_at=timezone.now() + timezone.timedelta(days=365),
    )

    # Spremi metadata
    import json as _json
    import os
    agent_data = {
        'partner_id': partner.pk,
        'referral_code': ref_code,
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'phone': phone,
        'country': country,
        'iban': iban,
        'region': region,
        'lang': lang,
        'signed_at': timezone.now().isoformat(),
        'ip': request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')),
        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
        'agreed_terms': True,
        'agreed_independent': True,
        'agreed_tax': True,
    }

    agents_dir = '/var/www/fina-connect/media/agents/'
    os.makedirs(agents_dir, exist_ok=True)
    with open(os.path.join(agents_dir, '%s_%s.json' % (partner.pk, email.replace('@', '_'))), 'w') as f:
        _json.dump(agent_data, f, ensure_ascii=False, indent=2)

    # Pošalji WhatsApp potvrdu
    try:
        from core.whatsapp import normalize_phone
        from core.whatsapp_tasks import send_whatsapp_text_task
        norm_phone = normalize_phone(phone)
        if norm_phone:
            wa_msg = (
                'Willkommen als LIMIT Connect Partner! 🎉\n\n'
                'Ihr Vertrag wurde digital unterzeichnet.\n'
                'Partner-ID: %s\n'
                'Provision: 20%% monatlich, 12 Monate\n\n'
                'Ihr Verkaufsmaterial:\n'
                'https://limit-connect.com/de/\n'
                'https://limit-connect.com/de/pakete/\n\n'
                '— LIMIT Connect Team'
            ) % str(partner.pk)[:8] if lang == 'de' else (
                'Dobrodošli kao LIMIT Connect partner! 🎉\n\n'
                'Vaš ugovor je digitalno potpisan.\n'
                'Partner-ID: %s\n'
                'Provizija: 20%% mjesečno, 12 mjeseci\n\n'
                '— LIMIT Connect tim'
            ) % str(partner.pk)[:8]
            send_whatsapp_text_task.delay(norm_phone, wa_msg)
    except Exception:
        pass

    # Notificiraj superadmina
    try:
        from superadmin_ai.tasks import _notify_superadmins
        _notify_superadmins(
            title='Novi partner: %s %s (%s)' % (first_name, last_name, country),
            message='Email: %s\nTelefon: %s\nRegija: %s\nIBAN: %s' % (email, phone, region, iban[:8] + '...'),
            notification_type='system',
        )
    except Exception:
        pass

    return JsonResponse({'ok': True, 'partner_id': str(partner.pk)[:8]})


@login_required
def cockpit_upload_photo(request):
    """API: Upload fotke iz Fenix Cockpit okruglog stola."""
    _cockpit_users = {'superadmin', 'marija.brtan'}
