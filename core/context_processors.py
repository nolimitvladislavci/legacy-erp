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
