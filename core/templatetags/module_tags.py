"""
core/templatetags/module_tags.py
Template tags for specialized module visibility control.

Usage:
    {% load module_tags %}

    {% if_module "dvd" %}
        <div>DVD vatrogasni sadržaj</div>
    {% endif_module %}

    {% module_sidebar %}
"""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


# ═══════════════════════════════════════════════════════════════════════
#  {% if_module "key" %} ... {% endif_module %}
# ═══════════════════════════════════════════════════════════════════════


class IfModuleNode(template.Node):
    def __init__(self, module_key, nodelist_true, nodelist_false):
        self.module_key = module_key
        self.nodelist_true = nodelist_true
        self.nodelist_false = nodelist_false

    def render(self, context):
        # Resolve variable or use literal string
        try:
            key = template.Variable(self.module_key).resolve(context)
        except template.VariableDoesNotExist:
            key = self.module_key

        active_modules = context.get("active_spec_modules", [])
        if key in active_modules:
            return self.nodelist_true.render(context)
        elif self.nodelist_false:
            return self.nodelist_false.render(context)
        return ""


@register.tag("if_module")
def do_if_module(parser, token):
    """
    Conditionally render block if specialized module is active.

    Usage:
        {% if_module "dvd" %}...{% endif_module %}
        {% if_module "dvd" %}...{% else_module %}...{% endif_module %}
    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise template.TemplateSyntaxError(f"'{bits[0]}' tag requires exactly one argument (module key).")
    module_key = bits[1]
    # Strip quotes if present
    if module_key[0] in ('"', "'") and module_key[-1] == module_key[0]:
        module_key = module_key[1:-1]

    nodelist_true = parser.parse(("else_module", "endif_module"))
    token = parser.next_token()

    if token.contents == "else_module":
        nodelist_false = parser.parse(("endif_module",))
        parser.delete_first_token()
    else:
        nodelist_false = None

    return IfModuleNode(module_key, nodelist_true, nodelist_false)


# ═══════════════════════════════════════════════════════════════════════
#  {% module_sidebar %} — renders sidebar for active specialized modules
# ═══════════════════════════════════════════════════════════════════════


@register.simple_tag(takes_context=True)
def module_sidebar(context):
    """
    Render sidebar navigation for all active specialized modules.
    Groups items by category with collapsible sections.
    """
    sidebar_modules = context.get("sidebar_spec_modules", [])
    if not sidebar_modules:
        return ""

    html_parts = []

    for group in sidebar_modules:
        cat_name = group["category_name"]
        cat_icon = group["category_icon"]
        group["category_key"]

        # Category group wrapper
        html_parts.append('<div class="sidebar-group">')
        html_parts.append(
            f'<button class="sidebar-group-toggle" onclick="toggleGroup(this)">'
            f'<span><i class="fas {cat_icon}" style="margin-right:6px;font-size:0.65rem"></i>'
            f"{cat_name}</span>"
            f'<i class="fas fa-chevron-down chevron"></i>'
            f"</button>"
        )
        html_parts.append('<div class="sidebar-group-links">')

        for module in group["modules"]:
            for item in module.get("items", []):
                url_name = item.get("url", "#")
                icon = item.get("icon", "fa-circle")
                name = item.get("name", "")

                # Try to resolve Django URL name, fallback to literal
                try:
                    from django.urls import reverse

                    resolved_url = reverse(url_name)
                except ImportError:
                    resolved_url = "#"

                html_parts.append(
                    f'<a href="{resolved_url}" onclick="closeSidebar()">'
                    f'<i class="fas {icon}"></i> <span>{name}</span>'
                    f"</a>"
                )

        html_parts.append("</div></div>")

    return mark_safe("\n".join(html_parts))


# ═══════════════════════════════════════════════════════════════════════
#  Simple filter: {{ "dvd"|module_active }}
# ═══════════════════════════════════════════════════════════════════════


@register.filter(name="module_active")
def module_active(module_key, context=None):
    """
    Template filter to check module status. Designed for use with
    the spec_module_is_active dict in context.

    Preferred usage in templates:
        {% if spec_module_is_active.dvd %}...{% endif %}
    """
    return False  # Filters don't have context access; use the dict approach


# ═══════════════════════════════════════════════════════════════════════
#  {% module_icon "dvd" %} — returns the icon class for a module
# ═══════════════════════════════════════════════════════════════════════


@register.simple_tag
def module_icon(module_key):
    """Return FontAwesome icon class for a module."""
    from core.module_registry import MODULE_REGISTRY

    mod = MODULE_REGISTRY.get(module_key)
    if mod:
        return mod.get("icon", "fa-puzzle-piece")
    return "fa-puzzle-piece"


@register.simple_tag
def module_name(module_key):
    """Return display name for a module."""
    from core.module_registry import MODULE_REGISTRY

    mod = MODULE_REGISTRY.get(module_key)
    if mod:
        return mod.get("name", module_key)
    return module_key
