from django import template

from permissions.engine import get_engine

register = template.Library()


@register.simple_tag(takes_context=True)
def has_permission(context, permission_codename, company=None):
    """
    Provjera ovlasti u templateu.
    Koristi: {% has_permission 'invoices.create' as can_create %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False
    return get_engine().has_permission(request.user, permission_codename, company)


@register.filter
def has_perm(user, permission_codename):
    """
    Filter verzija: {% if request.user|has_perm:"invoices.create" %}
    """
    if not user.is_authenticated:
        return False
    return get_engine().has_permission(user, permission_codename)
