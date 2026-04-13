from django import template
from django.db import DatabaseError

register = template.Library()


@register.simple_tag(takes_context=True)
def project_count(context):
    request = context.get("request")
    if not request or not request.user.is_authenticated:
        return 0
    try:
        from core.company_utils import get_user_company
        from projects.models import Project

        company = get_user_company(request)
        return Project.objects.filter(company=company).count() if company else 0
    except DatabaseError:
        return 0


@register.simple_tag(takes_context=True)
def active_project_count(context):
    request = context.get("request")
    if not request or not request.user.is_authenticated:
        return 0
    try:
        from core.company_utils import get_user_company
        from projects.models import Project

        company = get_user_company(request)
        return Project.objects.filter(company=company, status="active").count() if company else 0
    except DatabaseError:
        return 0
