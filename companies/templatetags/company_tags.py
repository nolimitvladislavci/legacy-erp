"""
Template tags za company-level konfiguraciju.

Usage u templateima:
    {% load company_tags %}
    {% company_language as lang %}
    {% if lang == "de" %}Deutsch{% else %}Hrvatski{% endif %}
"""
from django import template
from django.utils.translation import get_language

register = template.Library()


@register.simple_tag(takes_context=True)
def company_language(context):
    """Vraca jezik firme iz requesta ili fallback na get_language()."""
    request = context.get("request")
    if request:
        try:
            from core.company_utils import get_user_company
            company = get_user_company(request)
            if company and company.ui_language:
                return company.ui_language
        except ImportError:
            pass
    return get_language() or "hr"


@register.simple_tag(takes_context=True)
def is_german(context):
    """Helper: True ako je firma na njemackom."""
    request = context.get("request")
    if request:
        try:
            from core.company_utils import get_user_company
            company = get_user_company(request)
            if company:
                return company.ui_language == "de" or company.country == "DE"
        except ImportError:
            pass
    return False
