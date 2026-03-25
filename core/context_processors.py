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
