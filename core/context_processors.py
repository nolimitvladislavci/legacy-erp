from django.utils.translation import get_language
from django.conf import settings


def booking_globals(request):
    return {
        'BOOKING_LANGUAGES': settings.LANGUAGES,
        'BOOKING_CURRENT_LANG': get_language() or 'de',
    }

def company_switcher(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    try:
        from accounts.models import CompanyMembership

        if request.user.is_superuser:
            # Superadmin vidi SVE firme — KS LIMIT pristup
            from companies.models import Company
            all_companies = Company.objects.all().order_by('name')

            # Get existing memberships for highlighting
            existing_ids = set(
                CompanyMembership.objects.filter(user=request.user, is_active=True)
                .values_list('company_id', flat=True)
            )

            # Build pseudo-membership list for template
            memberships = list(
                CompanyMembership.objects.filter(user=request.user, is_active=True)
                .select_related('company')
                .order_by('-is_default', 'company__name')
            )

            # Add companies without membership (superadmin access)
            for comp in all_companies:
                if comp.id not in existing_ids:
                    # Create virtual membership object for template
                    pseudo = CompanyMembership(
                        user=request.user,
                        company=comp,
                        role='superadmin',
                        is_active=True,
                    )
                    pseudo.pk = None  # Mark as virtual
                    pseudo._is_virtual = True
                    memberships.append(pseudo)

            active_id = request.session.get('active_membership_id')
            return {
                'user_memberships': memberships,
                'has_multiple_companies': True,
                'active_membership_id': active_id,
                'is_superadmin_view': True,
                'total_companies': all_companies.count(),
            }
        else:
            memberships = list(
                CompanyMembership.objects.filter(user=request.user, is_active=True)
                .select_related('company')
                .order_by('-is_default', 'company__name')
            )

            # Umbrella admin: dodaj sve umbrella children kao virtual membership
            try:
                user_co = request.user.profile.company
                if user_co and user_co.is_umbrella:
                    from companies.models import Company
                    existing_ids = {m.company_id for m in memberships}
                    children = Company.objects.filter(
                        umbrella_parent=user_co
                    ).exclude(id__in=existing_ids).order_by('name')
                    for comp in children:
                        pseudo = CompanyMembership(
                            user=request.user, company=comp,
                            role='company_admin', is_active=True,
                        )
                        pseudo.pk = None
                        pseudo._is_virtual = True
                        memberships.append(pseudo)
            except Exception:
                pass

            active_id = request.session.get('active_membership_id')
            return {
                'user_memberships': memberships,
                'has_multiple_companies': len(memberships) > 1,
                'active_membership_id': active_id,
            }
    except Exception:
        return {}


def module_context(request):
    """
    Inject specialized module info into every template context.
    Provides:
      - active_spec_modules: list of active specialized module keys
      - sidebar_spec_modules: structured sidebar for specialized modules
      - spec_module_is_active: dict {module_key: bool} for quick checks
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}

    try:
        from core.company_utils import get_user_company
        company = get_user_company(request)
        if not company:
            return {}

        from core.module_registry import (
            get_active_modules,
            get_sidebar_items,
            MODULE_REGISTRY,
        )

        active_keys = get_active_modules(company)
        sidebar = get_sidebar_items(company)

        # Build quick-check dict for all registered modules
        module_active_map = {key: (key in active_keys) for key in MODULE_REGISTRY}

        return {
            'active_spec_modules': active_keys,
            'sidebar_spec_modules': sidebar,
            'spec_module_is_active': module_active_map,
        }

    except Exception:
        return {}


def failed_imports_badge(request):
    """Badge za sidebar/dashboard: neuspjeli uvozi koji čekaju pažnju korisnika."""
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}
    try:
        from smart_import.models import FailedImport
        from core.company_utils import get_user_company
        company = get_user_company(request)
        if not company:
            return {}
        count = FailedImport.objects.filter(
            company=company, resolved=False
        ).count()
        return {'failed_imports_count': count}
    except Exception:
        return {'failed_imports_count': 0}


def pending_claims_badge(request):
    """Badge za sidebar: broj pending claim zahtjeva."""
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {'pending_claims_count': 0}
    try:
        if request.user.is_superuser or request.user.is_staff:
            from registration.models import CompanyClaimRequest
            count = CompanyClaimRequest.objects.filter(status='pending').count()
        else:
            user_co = request.user.profile.company
            from registration.models import CompanyClaimRequest
            count = CompanyClaimRequest.objects.filter(
                status='pending', company__umbrella_parent=user_co,
            ).count()
        return {'pending_claims_count': count}
    except Exception:
        return {'pending_claims_count': 0}


def white_label_context(request):
    """Injektira WL varijable u sve templateove."""
    wl = getattr(request, 'white_label', None)
    if wl:
        return {
            'WL_ACTIVE': True,
            'WL_NAME': wl.brand_name,
            'WL_SUBDOMAIN': wl.subdomain,
            'WL_LOGO': wl.logo_url or '',
            'WL_COLOR': wl.primary_color,
            'WL_TAGLINE': wl.tagline,
            'WL_FISCAL': wl.fiscal_system,
        }
    return {
        'WL_ACTIVE': False,
        'WL_NAME': 'LIMIT Connect',
        'WL_LOGO': '',
        'WL_COLOR': '#c9a84c',
        'WL_TAGLINE': '',
        'WL_FISCAL': 'HR',
    }
