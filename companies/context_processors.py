"""
companies/context_processors.py
Injects sidebar_modules into every template context.
"""


def sidebar_modules(request):
    """Add active modules to template context for sidebar rendering."""
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}

    try:
        from core.company_utils import get_user_company
        company = get_user_company(request)
        if not company:
            return {}

        from companies.models import CompanyModuleConfig
        from companies.module_registry import MODULES, CATEGORIES

        config = CompanyModuleConfig.objects.filter(company=company).first()

        if config and config.enabled_modules:
            enabled = config.enabled_modules
        else:
            # Default: show all modules
            enabled = [m['id'] for m in MODULES]

        # Build sidebar structure grouped by category
        sidebar = []
        seen_cats = {}
        for m in MODULES:
            if m['id'] not in enabled and not m.get('always_visible'):
                continue
            cat = m.get('category', 'core')
            if cat not in seen_cats:
                cat_info = CATEGORIES.get(cat, {'name': cat.title(), 'icon': 'bi-folder', 'order': 99})
                seen_cats[cat] = {'info': cat_info, 'modules': [], 'order': cat_info.get('order', 99)}
            seen_cats[cat]['modules'].append(m)

        sidebar = sorted(seen_cats.values(), key=lambda x: x['order'])

        return {
            'sidebar_modules': sidebar,
            'sidebar_enabled_ids': enabled,
            'sidebar_all_modules': MODULES,
        }

    except Exception:
        return {}
