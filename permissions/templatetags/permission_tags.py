from django import template

from permissions.manager import PermissionManager

register = template.Library()
@register.simple_tag(takes_context=True)
def has_permission(context, permission_codename, company=None):
    """
    Check permission in template
    
    Usage:
        {% load permission_tags %}
        {% has_permission 'invoices.create' as can_create %}
        {% if can_create %}
            <button>Create Invoice</button>
        {% endif %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False

    return PermissionManager.has_permission(request.user, permission_codename, company)
@register.filter
def has_perm(user, permission_codename):
    """
    Filter version
    
    Usage:
        {% if request.user|has_perm:"invoices.create" %}
            ...
        {% endif %}
    """
    if not user.is_authenticated:
        return False

    return PermissionManager.has_permission(user, permission_codename)
