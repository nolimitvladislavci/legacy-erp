from datetime import timedelta

from django import template
from django.utils import timezone

register = template.Library()


@register.inclusion_tag('tax_wizard/_widget.html', takes_context=True)
def tax_wizard_widget(context, context_type='general', amount=None):
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return {'show': False}

    try:
        from accounts.models import UserProfile
        up = UserProfile.objects.select_related('company').get(user=request.user)
        company = up.company
    except DatabaseError:
        return {'show': False}

    today = timezone.now().date()

    from tax_wizard.models import TaxDeadline
    upcoming = TaxDeadline.objects.filter(
        company=company,
        deadline_date__gte=today,
        deadline_date__lte=today + timedelta(days=30),
        is_filed=False,
    ).select_related('template').order_by('deadline_date')[:3]

    trigger_message = None
    if context_type == 'invoice' and amount:
        btype = getattr(company, 'business_type', '') or ''
        if btype in ('obrt', 'pausalni_obrt') and float(amount or 0) > 5000:
            trigger_message = 'Značajan promet — provjeri PO-SD obračun!'

    return {
        'show': bool(upcoming or trigger_message),
        'upcoming_deadlines': upcoming,
        'trigger_message': trigger_message,
        'wizard_url': '/porezni-savjetnik/',
        'context_type': context_type,
    }
