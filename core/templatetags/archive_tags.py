from django import template
from django.db import DatabaseError

register = template.Library()


@register.simple_tag
def is_archive_readonly(user):
    """Check if user's company is on archive_readonly plan."""
    try:
        company = user.profile.company
        if not company:
            return False
        sub = company.subscriptions.filter(
            is_active=True
        ).order_by('-valid_from').first()
        return sub and sub.plan == 'archive_readonly'
    except DatabaseError:
        return False
