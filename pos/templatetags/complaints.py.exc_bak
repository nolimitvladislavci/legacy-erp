"""
Templatetag za globalni pristup Knjizi boljitaka.

Korištenje u BILO KOJEM templateu:
    {% load complaints %}
    {% complaints_button %}              → puni gumb s ikonom
    {% complaints_button style="fab" %}  → floating action button
    {% complaints_qr %}                  → QR kod za potrošačev mobitel
"""
from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

register = template.Library()


@register.inclusion_tag('pos/complaints_button.html', takes_context=True)
def complaints_button(context, style='inline', source_module='general'):
    """Renders complaint/impression button."""
    request = context.get('request')
    company = None
    if request:
        try:
            from core.company_utils import get_user_company
            company = get_user_company(request)
        except Exception:
            pass

    # Count pending (unanswered prigovori)
    pending = 0
    if company:
        try:
            from pos.models import KnjigaPrigovora
            pending = KnjigaPrigovora.objects.filter(
                company=company,
                record_type__in=['prigovor', 'reklamacija'],
                datum_odgovora__isnull=True,
            ).count()
        except Exception:
            pass

    return {
        'company': company,
        'company_id': company.pk if company else '',
        'pending_count': pending,
        'style': style,
        'source_module': source_module,
        'is_authenticated': getattr(request, 'user', None) and request.user.is_authenticated,
    }


@register.simple_tag(takes_context=True)
def complaints_qr_url(context):
    """Returns the public QR complaint URL for current company."""
    request = context.get('request')
    if not request:
        return ''
    try:
        from core.company_utils import get_user_company
        company = get_user_company(request)
        if company:
            return f'/pos/prigovori/new/?company={company.pk}&source=qr'
    except Exception:
        pass
    return ''


@register.simple_tag(takes_context=True)
def complaints_stats(context):
    """Returns dict with complaint/impression stats for dashboard widgets."""
    request = context.get('request')
    if not request:
        return {}
    try:
        from core.company_utils import get_user_company
        from pos.models import KnjigaPrigovora
        from django.db.models import Avg, Count, Q
        company = get_user_company(request)
        if not company:
            return {}

        qs = KnjigaPrigovora.objects.filter(company=company)
        return {
            'total': qs.count(),
            'prigovori': qs.filter(record_type='prigovor').count(),
            'pohvale': qs.filter(record_type='pohvala').count(),
            'utisci': qs.filter(record_type='utisak').count(),
            'reklamacije': qs.filter(record_type='reklamacija').count(),
            'pending': qs.filter(
                record_type__in=['prigovor', 'reklamacija'],
                datum_odgovora__isnull=True,
            ).count(),
            'overdue': qs.filter(
                record_type__in=['prigovor', 'reklamacija'],
                datum_odgovora__isnull=True,
            ).count(),  # will be filtered by date in template
            'avg_rating': qs.filter(star_rating__isnull=False).aggregate(
                avg=Avg('star_rating'))['avg'],
        }
    except Exception:
        return {}
