"""
registration/tasks.py — Celery taskovi za registraciju i onboarding.
"""

import logging

from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_ambassador_onboarding_email(self, lead_id):
    """
    Šalje NO LIMIT Ambasador onboarding email.
    Poziva se kad se is_disability_ambassador uključi na SalesLead.
    """
    from registration.models import SalesLead

    try:
        lead = SalesLead.objects.get(pk=lead_id)
    except SalesLead.DoesNotExist:
        logger.error(f'SalesLead {lead_id} ne postoji')
        return

    if not lead.is_disability_ambassador:
        return

    agent_name = lead.contact_name or lead.company_name or 'Ambasadore'
    email = lead.contact_email
    if not email:
        logger.warning(f'SalesLead {lead_id} nema email — preskačem')
        return

    dashboard_url = 'https://limit-connect.com/hr/moji-klijenti/'

    html_body = render_to_string('email/ambassador_onboarding.html', {
        'agent_name': agent_name,
        'dashboard_url': dashboard_url,
    })

    plain_body = (
        f'Dobrodošli u NO LIMIT Ambasador program, {agent_name}!\n\n'
        f'Vaša komisija: 15% mjesečne pretplate svakog klijenta.\n'
        f'Dashboard: {dashboard_url}\n\n'
        f'Kontakt: Ljilja — 092-1104-615\n'
        f'— LIMIT Connect'
    )

    try:
        send_mail(
            subject='Dobrodošli u NO LIMIT Ambasador program!',
            message=plain_body,
            from_email=None,
            recipient_list=[email],
            html_message=html_body,
            fail_silently=False,
        )
        logger.info(f'Ambassador onboarding email sent to {email} (lead={lead_id})')
    except Exception as exc:
        logger.error(f'Failed to send ambassador email to {email}: {exc}')
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def downgrade_expired_subscriptions(self):
    """
    Svake noći u 01:00 — firme s isteklom pretplatom → archive_readonly.
    Korisnici OSTAJU aktivni, ali vide samo arhivu i konto (read-only).
    Zakonska obaveza: pristup arhivi 11 godina (ZOR čl. 10).
    """
    from registration.models import CompanySubscription, PricingPlan
    from django.utils import timezone

    archive_plan = PricingPlan.objects.filter(slug='archive_readonly').first()
    if not archive_plan:
        logger.error('PricingPlan archive_readonly ne postoji!')
        return

    today = timezone.now().date()
    active_plans = ['starter', 'professional', 'micro', 'enterprise', 'distributor', 'business']

    expired = CompanySubscription.objects.filter(
        is_active=True,
        valid_until__lt=today,
        plan__in=active_plans,
    )

    downgraded = 0
    for sub in expired:
        # Provjeri cancel_at_period_end ili expired valid_until
        old_plan = sub.plan
        sub.plan = 'archive_readonly'
        sub.pricing_plan = archive_plan
        sub.monthly_fee = 0
        sub.save(update_fields=['plan', 'pricing_plan', 'monthly_fee'])
        downgraded += 1
        logger.info(
            'Downgraded %s from %s to archive_readonly (valid_until=%s)',
            sub.company.name, old_plan, sub.valid_until,
        )

    if downgraded:
        logger.info('downgrade_expired_subscriptions: %d firm downgraded', downgraded)
    return downgraded
