import logging
from celery import shared_task

logger = logging.getLogger('ai_assistant.patrol')


@shared_task(bind=True, max_retries=2, retry_backoff=True)
def ai_midnight_patrol(self):
    """Run AI patrol for all active companies. Scheduled nightly at 02:00."""
    from companies.models import Company
    from ai_assistant.patrol import run_patrol
    from ai_assistant.models import PatrolReport
    from notifications.services import notify
    from django.contrib.auth import get_user_model
    User = get_user_model()

    companies = Company.objects.all()
    results = []

    for company in companies:
        try:
            report = run_patrol(company)

            # Save report to DB
            patrol = PatrolReport.objects.create(
                company=company,
                summary=report['summary'],
                raw_data=report['raw_data'],
                has_issues=report['has_issues'],
            )

            # Notify company admins via profile role
            admin_profiles = []
            try:
                from accounts.models import UserProfile
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
            except Exception as ne:
                logger.warning("Notification failed for {}: {}".format(company.name, ne))

            # WhatsApp notification if issues found
            if report['has_issues'] and admin_profiles:
                try:
                    from core.whatsapp import send_text, is_gateway_healthy
                    if is_gateway_healthy():
                        first_admin = admin_profiles[0]
                        phone = getattr(first_admin, 'phone', '') or ''
                        if phone:
                            msg = "LIMIT Connect Patrol:\n{}".format(report['summary'][:500])
                            send_text(phone, msg)
                except Exception as e:
                    logger.warning("WhatsApp patrol notify failed: {}".format(e))

            results.append({
                'company': company.name,
                'status': 'ok',
                'has_issues': report['has_issues']
            })
            logger.info("Patrol completed for {}: {}".format(
                company.name, 'ISSUES' if report['has_issues'] else 'OK'))

        except Exception as e:
            logger.error("Patrol failed for {}: {}".format(company.name, e))
            results.append({
                'company': company.name,
                'status': 'error',
                'error': str(e)
            })

    return results
