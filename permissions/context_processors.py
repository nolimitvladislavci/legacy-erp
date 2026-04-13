"""
Context processors for permissions and subscription module gating.
"""


class _AllModulesSet:
    """A set-like object where __contains__ always returns True (for superusers)."""

    def __contains__(self, item):
        return True

    def __iter__(self):
        return iter([])

    def __bool__(self):
        return True


def permissions_context(request):
    """Add user_permissions and user_role to template context."""
    return {
        "user_permissions": getattr(request, "user_permissions", set()),
        "user_role": getattr(request, "user_role", None),
    }


def _get_plan_info(company):
    """Helper to get plan name and slug from company subscription."""
    plan_name = ""
    plan_slug = ""
    if company:
        try:
            sub = company.subscriptions.filter(is_active=True).order_by("-valid_from").first()
            if sub and sub.pricing_plan:
                plan_name = sub.pricing_plan.name
                plan_slug = sub.pricing_plan.slug
            elif sub:
                plan_name = sub.get_plan_display()
                plan_slug = sub.plan
        except DatabaseError:
            pass
    return plan_name, plan_slug


def subscription_context(request):
    """Expose allowed_modules and is_company_admin to all templates."""
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {
            "allowed_modules": set(),
            "is_company_admin": False,
            "active_plan_name": "",
            "active_plan_slug": "",
        }

    if request.user.is_superuser:
        return {
            "allowed_modules": _AllModulesSet(),
            "is_company_admin": True,
            "active_plan_name": "Super Admin",
            "active_plan_slug": "superadmin",
        }

    # Determine company (impersonation-aware)
    company = getattr(request, "impersonated_company", None)
    if not company:
        try:
            company = request.user.profile.company
        except AttributeError:
            company = None

    # Platform owner bypass - all modules unlocked
    if company:
        try:
            if company.is_platform_owner:
                from registration.constants import PLAN_MODULES

                _all = set()
                for _mods in PLAN_MODULES.values():
                    _all.update(_mods)
                plan_name, plan_slug = _get_plan_info(company)
                return {
                    "allowed_modules": _all or _AllModulesSet(),
                    "is_company_admin": True,
                    "active_plan_name": plan_name,
                    "active_plan_slug": plan_slug,
                }
        except DatabaseError:
            pass

    modules = set()
    if company:
        # SOFT GATE: sidebar shows ALL enabled modules, not just subscription.
        # Upgrade banner handles upsell, not sidebar visibility.
        try:
            # 1. Start with subscription modules
            sub = company.subscriptions.filter(is_active=True).order_by("-valid_from").first()
            if sub:
                modules = set(sub.allowed_modules)
        except DatabaseError:
            pass

        # 2. UNION with Module Picker (not intersection!)
        # If user enabled 21 modules in picker, show all 21.
        try:
            from companies.models import CompanyModuleConfig

            config = CompanyModuleConfig.objects.filter(company=company).first()
            if config and config.enabled_modules:
                picker_set = set(config.enabled_modules)
                modules = modules | picker_set  # UNION, not intersection
        except DatabaseError:
            pass

        # 3. Always include core modules
        modules |= {"pos", "partners", "inventory", "invoicing", "documents", "konto"}

    # is_company_admin: superadmin/company_admin role or is_staff
    is_admin = request.user.is_staff
    if not is_admin:
        try:
            is_admin = request.user.profile.role in ("superadmin", "company_admin")
        except AttributeError:
            pass

    # Plan info for sidebar pill
    plan_name, plan_slug = _get_plan_info(company)

    return {
        "allowed_modules": modules,
        "is_company_admin": is_admin,
        "active_plan_name": plan_name,
        "active_plan_slug": plan_slug,
    }
