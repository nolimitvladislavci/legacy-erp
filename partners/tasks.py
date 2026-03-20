"""Agent provizija — mjesečni obračun."""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone as tz

logger = logging.getLogger('agents')


@shared_task
def calculate_agent_commissions():
    """
    Mjesečno: izračunaj proviziju za sve aktivne agente.
    Pokreće se 1. u mjesecu za prethodni mjesec.
    """
    from partners.models import AgentReferral, AgentPayout
    from registration.models import CompanySubscription

    now = tz.now()
    # Prethodni mjesec
    if now.month == 1:
        month, year = 12, now.year - 1
    else:
        month, year = now.month - 1, now.year

    active_referrals = AgentReferral.objects.filter(status='active').select_related('agent', 'referred_company')

    agents_processed = {}

    for ref in active_referrals:
        # Provjeri da li je istekao (12 mjeseci)
        if ref.expires_at and now > ref.expires_at:
            ref.status = 'expired'
            ref.save(update_fields=['status'])
            continue

        # Nađi aktivnu pretplatu
        sub = CompanySubscription.objects.filter(
            company=ref.referred_company, is_active=True
        ).first()

        if not sub or not sub.monthly_fee:
            continue

        # Izračunaj proviziju
        commission = sub.monthly_fee * ref.commission_percent / 100

        # Akumuliraj po agentu
        agent_pk = str(ref.agent.pk)
        if agent_pk not in agents_processed:
            agents_processed[agent_pk] = {
                'agent': ref.agent,
                'total': Decimal('0'),
                'referrals': [],
                'iban': ref.agent_iban,
            }

        agents_processed[agent_pk]['total'] += commission
        agents_processed[agent_pk]['referrals'].append({
            'company': ref.referred_company.name,
            'plan': sub.plan,
            'monthly_fee': str(sub.monthly_fee),
            'commission_pct': str(ref.commission_percent),
            'commission': str(commission),
        })

        # Update referral total
        ref.total_earned += commission
        ref.save(update_fields=['total_earned'])

    # Kreiraj payout zapise
    created = 0
    for agent_pk, data in agents_processed.items():
        if data['total'] <= 0:
            continue

        payout, was_created = AgentPayout.objects.get_or_create(
            agent=data['agent'],
            period_month=month,
            period_year=year,
            defaults={
                'amount': data['total'],
                'referrals_count': len(data['referrals']),
                'breakdown': data['referrals'],
                'iban': data['iban'],
            }
        )
        if was_created:
            created += 1
            logger.info(
                '[AGENT] Payout created: %s — %s EUR (%d referrals) for %02d/%d',
                data['agent'].name, data['total'], len(data['referrals']), month, year
            )

    return {'month': '%02d/%d' % (month, year), 'agents': len(agents_processed), 'payouts_created': created}
