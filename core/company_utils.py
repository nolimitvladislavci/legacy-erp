import logging

from django.core.exceptions import ObjectDoesNotExist

from core.tenant import get_current_company

logger = logging.getLogger(__name__)


def _is_umbrella_ancestor(profile_company, child):
    """Check if profile_company is an ancestor of child (up to 3 levels).

    Supports multi-level umbrella hierarchies:
      Konjik → Viktor Grgurić → grandchild
    """
    current = child
    for _ in range(3):  # Max 3 levels deep
        if not current.umbrella_parent_id:
            return False
        if current.umbrella_parent_id == profile_company.id:
            return True
        # Walk up the chain
        from companies.models import Company

        try:
            current = Company.objects.get(pk=current.umbrella_parent_id)
        except Company.DoesNotExist:
            return False
    return False


def get_user_company(request=None):
    # 1. Thread-local (set by CompanyMiddleware or ImpersonationMiddleware)
    company = get_current_company()
    if company:
        return company
    # 2. Superadmin impersonating a company — read from session
    if request and getattr(request.user, "is_superuser", False):
        company_id = request.session.get("impersonated_company_id") or request.session.get("superadmin_as_company")
        if company_id:
            from companies.models import Company

            try:
                return Company.objects.get(pk=company_id)
            except ObjectDoesNotExist:
                pass
    # 2b. Umbrella admin viewing a child company (multi-level support)
    if request and request.user.is_authenticated:
        umbrella_cid = request.session.get("umbrella_as_company")
        if umbrella_cid:
            from companies.models import Company

            try:
                child = Company.objects.get(pk=umbrella_cid)
                profile_company = request.user.profile.company
                if _is_umbrella_ancestor(profile_company, child):
                    return child
                else:
                    # Invalid — clear session
                    for key in ("umbrella_as_company", "umbrella_home_company", "umbrella_home_name"):
                        request.session.pop(key, None)
            except ObjectDoesNotExist:
                pass
    # 3. Fallback to profile.company — samo za autenticirane korisnike
    if request and hasattr(request, "user") and request.user.is_authenticated:
        try:
            return request.user.profile.company
        except (AttributeError, ObjectDoesNotExist):
            logger.debug("Profile/company not found for user %s", request.user)
    return None


def get_umbrella_home(request):
    """Return the umbrella parent company when in switched mode, else None."""
    if not request or not request.user.is_authenticated:
        return None
    home_id = request.session.get("umbrella_home_company")
    if home_id:
        from companies.models import Company

        try:
            return Company.objects.get(pk=home_id)
        except Company.DoesNotExist:
            pass
    return None


def get_effective_modules(company, request=None):
    """Return the set of modules available for this company context.

    When a bookkeeper is viewing a child company via umbrella switch,
    the child inherits the parent's modules — the bookkeeper needs
    access to invoicing, konto, documents etc. regardless of the
    child's own subscription plan.
    """
    from registration.constants import PLAN_MODULES

    # Start with the company's own modules
    own_modules = set()
    try:
        sub = company.subscriptions.filter(is_active=True).order_by("-valid_from").first()
        if sub:
            # Check modules_override first
            if sub.modules_override:
                own_modules = set(sub.modules_override)
            else:
                plan_key = (sub.pricing_plan.slug if sub.pricing_plan else sub.plan).lower()
                own_modules = set(PLAN_MODULES.get(plan_key, []))
            # included_modules from PricingPlan
            if sub.pricing_plan and sub.pricing_plan.included_modules:
                own_modules.update(sub.pricing_plan.included_modules)
    except Exception:
        pass

    # Module config override
    try:
        cfg = company.companymoduleconfig
        if cfg and cfg.enabled_modules:
            own_modules.update(cfg.enabled_modules)
    except Exception:
        pass

    # If in umbrella context, inherit parent's modules
    if request:
        home = get_umbrella_home(request)
        if home and home.id != company.id:
            try:
                parent_sub = home.subscriptions.filter(is_active=True).order_by("-valid_from").first()
                if parent_sub:
                    if parent_sub.modules_override:
                        own_modules.update(parent_sub.modules_override)
                    else:
                        plan_key = (
                            parent_sub.pricing_plan.slug if parent_sub.pricing_plan else parent_sub.plan
                        ).lower()
                        own_modules.update(PLAN_MODULES.get(plan_key, []))
                    if parent_sub.pricing_plan and parent_sub.pricing_plan.included_modules:
                        own_modules.update(parent_sub.pricing_plan.included_modules)
            except Exception:
                pass
            # Also inherit parent's module config
            try:
                parent_cfg = home.companymoduleconfig
                if parent_cfg and parent_cfg.enabled_modules:
                    own_modules.update(parent_cfg.enabled_modules)
            except Exception:
                pass

    return own_modules


def company_queryset(model_class, request=None, company_field="company"):
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
