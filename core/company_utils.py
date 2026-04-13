import logging

from django.core.exceptions import ObjectDoesNotExist

from core.tenant import get_current_company

logger = logging.getLogger(__name__)


def get_user_company(request=None):
    # 1. Thread-local (set by CompanyMiddleware or ImpersonationMiddleware)
    company = get_current_company()
    if company:
        return company
    # 2. Superadmin impersonating a company — read from session
    if request and getattr(request.user, 'is_superuser', False):
        company_id = (
            request.session.get('impersonated_company_id') or
            request.session.get('superadmin_as_company')
        )
        if company_id:
            from companies.models import Company
            try:
                return Company.objects.get(pk=company_id)
            except ObjectDoesNotExist:
                pass
    # 2b. Umbrella admin viewing a child company
    if request and request.user.is_authenticated:
        umbrella_cid = request.session.get('umbrella_as_company')
        if umbrella_cid:
            from companies.models import Company
            try:
                child = Company.objects.get(pk=umbrella_cid)
                # Verify the user's own company is indeed umbrella parent
                profile_company = request.user.profile.company
                if child.umbrella_parent_id == profile_company.id:
                    return child
                else:
                    # Invalid - clear session
                    del request.session['umbrella_as_company']
            except ObjectDoesNotExist:
                pass
    # 3. Fallback to profile.company
    if request:
        try:
            return request.user.profile.company
        except AttributeError:
            logger.exception("Profile access failed")
    return None


def company_queryset(model_class, request=None, company_field='company'):
    company = get_user_company(request)
    if not company:
        return model_class.objects.none()
    return model_class.objects.filter(**{company_field: company})


def get_user_company_from_user(user):
    """Get company from a User object (no request needed). For WebSocket consumers."""
    if not user or not user.is_authenticated:
        return None
    try:
        return user.profile.company
    except AttributeError:
        return None
