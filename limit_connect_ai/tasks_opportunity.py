"""
BORG FENIX — Opportunity Lifecycle Tasks (F2.2)
Manages the identified → notified → applied → utilized pipeline.

Tasks:
1. notify_new_matches — batch notify all identified matches
2. expire_old_matches — mark expired opportunities
3. opportunity_digest — weekly summary for umbrella admin
"""
import logging

from celery import shared_task
from django.db.models import Count, Sum
from django.utils import timezone

logger = logging.getLogger('borg.opportunity')


@shared_task
def notify_new_matches(batch_size=200):
    """
    Move identified matches to notified status.
    In production, this would send email/WhatsApp. For now, just status update.
    """
    from limit_connect_ai.models import ClientOpportunityMatch

    matches = (
        ClientOpportunityMatch.objects
        .filter(status='identified')
        .select_related('company', 'opportunity')
        .order_by('-calculated_savings')[:batch_size]
    )

    now = timezone.now()
    notified = 0

    for match in matches:
        match.status = 'notified'
        match.notified_at = now
        match.notified_via = 'dashboard'
        match.save(update_fields=['status', 'notified_at', 'notified_via'])
        notified += 1

    logger.info('Notified %d opportunity matches', notified)
    return {'notified': notified}


@shared_task
def expire_old_matches():
    """Mark matches as expired if opportunity deadline has passed."""
    from limit_connect_ai.models import ClientOpportunityMatch

    today = timezone.now().date()
    expired = (
        ClientOpportunityMatch.objects
        .filter(
            status__in=['identified', 'notified', 'interested'],
            opportunity__deadline__lt=today,
        )
        .update(status='expired')
    )

    logger.info('Expired %d opportunity matches', expired)
    return {'expired': expired}


@shared_task
def opportunity_digest():
    """
    Weekly opportunity digest — summary of all matches per company.
    Returns structured data for dashboard widget.
    """
    from limit_connect_ai.models import ClientOpportunityMatch

    stats = (
        ClientOpportunityMatch.objects
        .exclude(status__in=['expired', 'rejected'])
        .values('company__name', 'status')
        .annotate(count=Count('id'), total_savings=Sum('calculated_savings'))
        .order_by('company__name', 'status')
    )

    digest = {}
    for row in stats:
        co = row['company__name']
        if co not in digest:
            digest[co] = {'statuses': {}, 'total_savings': 0}
        digest[co]['statuses'][row['status']] = row['count']
        digest[co]['total_savings'] += float(row['total_savings'] or 0)

    # Summary
    total_matches = ClientOpportunityMatch.objects.exclude(status__in=['expired', 'rejected']).count()
    total_savings = ClientOpportunityMatch.objects.exclude(status__in=['expired', 'rejected']).aggregate(
        s=Sum('calculated_savings'))['s'] or 0
    utilized = ClientOpportunityMatch.objects.filter(status='utilized').count()

    result = {
        'total_active_matches': total_matches,
        'total_potential_savings_eur': float(total_savings),
        'utilized_count': utilized,
        'companies_with_matches': len(digest),
        'top_5': sorted(digest.items(), key=lambda x: -x[1]['total_savings'])[:5],
    }

    logger.info('Opportunity digest: %d matches, %.0f EUR, %d utilized',
                total_matches, float(total_savings), utilized)
    return result
