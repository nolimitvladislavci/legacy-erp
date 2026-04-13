import logging
from celery import shared_task
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('ai_assistant.patrol')


@shared_task(bind=True, soft_time_limit=120, max_retries=2, retry_backoff=True)
def ai_midnight_patrol_company(self, company_id):
    """Patrol za jednu firmu — poziva se kao subtask iz ai_midnight_patrol."""
    from companies.models import Company
    from ai_assistant.patrol import run_patrol
    from ai_assistant.models import PatrolReport

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        logger.warning("Patrol: company %s ne postoji", company_id)
        return

    try:
        report = run_patrol(company)

        PatrolReport.objects.create(
            company=company,
            summary=report['summary'],
            raw_data=report['raw_data'],
            has_issues=report['has_issues'],
        )

        # Notify admins
        try:
            from accounts.models import UserProfile
            from notifications.services import notify
            admin_profiles = list(UserProfile.objects.filter(
                company=company,
                role__in=['company_admin', 'superadmin']
            ).select_related('user')[:3])

            if not admin_profiles:
                admin_profiles = list(UserProfile.objects.filter(
                    company=company,
                    user__is_staff=True
                ).select_related('user')[:3])

            for profile in admin_profiles:
                notify(
                    recipient=profile.user,
                    notification_type='system',
                    title='Jutarnji AI Patrol',
                    message=report['summary'][:200],
                    url='/ai/patrol/',
                    company=company,
                )

            if report['has_issues'] and admin_profiles:
                from core.whatsapp import send_text, is_gateway_healthy
                if is_gateway_healthy():
                    phone = getattr(admin_profiles[0], 'phone', '') or ''
                    if phone:
                        send_text(phone, "LIMIT Connect Patrol:\n{}".format(report['summary'][:500]))
        except DatabaseError as ne:
            logger.warning("Patrol notify failed for %s: %s", company.name, ne)

        logger.info("Patrol OK: %s — %s", company.name, 'ISSUES' if report['has_issues'] else 'OK')
        return {'company': company.name, 'status': 'ok', 'has_issues': report['has_issues']}

    except (IntegrityError, DatabaseError) as exc:
        logger.error("Patrol failed for %s: %s", company.name, exc)
        return {'company': company.name, 'status': 'error', 'error': str(exc)}


@shared_task(bind=True, soft_time_limit=60, max_retries=1)
def ai_midnight_patrol(self):
    """
    Orkestrator — raspoređuje po-firminu patrol kao zasebne subtaskove.
    Soft limit 60s — samo dispatcha, ne čeka rezultate.
    """
    from companies.models import Company

    # Samo aktivne firme (ne DRAFT OIB)
    company_ids = list(
        Company.objects.exclude(oib__startswith='DRAFT')
                       .values_list('id', flat=True)
    )

    dispatched = 0
    # Rasporedi s razmakom od 10s između firma — ne preopterećuje AI API
    for i, cid in enumerate(company_ids):
        ai_midnight_patrol_company.apply_async(
            args=[cid],
            countdown=i * 10,  # firma 0 odmah, firma 1 za 10s, firma 2 za 20s...
        )
        dispatched += 1

    logger.info("ai_midnight_patrol: dispatched %d company patrols", dispatched)
    return {'dispatched': dispatched}
