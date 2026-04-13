"""Celery tasks for AI Midnight Patrol."""
import logging
from celery import shared_task
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('ai_assistant.patrol')


@shared_task(bind=True, max_retries=2, retry_backoff=True)
def ai_midnight_patrol(self):
    """
    Nightly patrol: scan all active companies for anomalies.
    Sends summary via notifications (dashboard + WhatsApp if critical).
    Runs at 02:00 via Celery Beat.
    """
    from companies.models import Company
    from notifications.services import notify
    from ai_assistant.patrol import run_patrol
    from ai_assistant.models import PatrolReport

    companies = Company.objects.all()
    total_findings = 0

    for company in companies:
        try:
            result = run_patrol(company)
            if not result or not result.get('has_issues'):
                continue

            total_findings += 1
            report = result.get('summary', '')

            # Save patrol report to DB
            PatrolReport.objects.create(
                company=company,
                findings=result.get('raw_data', {}),
                summary=report,
                finding_count=1,
                critical_count=1 if result.get('has_issues') else 0,
            )

            # Find company admins to notify
            from accounts.models import UserProfile
            admin_profiles = UserProfile.objects.filter(
                company=company,
                user__is_active=True,
                role__in=['company_admin', 'superadmin']
            ).select_related('user')

            # Fallback to staff users if no role-based admins found
            if not admin_profiles.exists():
                admin_profiles = UserProfile.objects.filter(
                    company=company,
                    user__is_active=True,
                    user__is_staff=True
                ).select_related('user')[:3]

            has_critical = result.get('has_issues', False)

            for profile in admin_profiles:
                # Dashboard notification always
                notify(
                    recipient=profile.user,
                    notification_type='system',
                    title='🔍 Noćna Patrola' + (' — KRITIČNO!' if has_critical else ''),
                    message=report[:500],
                    url='/ai/',
                    company=company,
                )

                # WhatsApp only for critical findings
                if has_critical and profile.phone:
                    try:
                        from core.whatsapp_tasks import send_whatsapp_text_task
                        send_whatsapp_text_task.delay(
                            profile.phone,
                            report[:1000]
                        )
                    except ImportError:
                        pass

            logger.info(f'Patrol for {company.name}: {len(findings)} findings')

        except (IntegrityError, DatabaseError) as e:
            logger.error(f'Patrol failed for company {company.id}: {e}')

    logger.info(f'Midnight patrol complete: {total_findings} total findings across {companies.count()} companies')
    return f'{total_findings} findings'
