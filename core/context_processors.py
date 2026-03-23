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
