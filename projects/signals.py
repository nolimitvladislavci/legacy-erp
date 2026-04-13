"""
Auto-sync projects.Project -> worktime.Project
When a Project is created or updated in the projects app,
mirror it to worktime.Project so it appears on timesheet forms.
"""
import logging
import uuid

from django.db.models.signals import post_save
from django.dispatch import receiver

from projects.models import Project

logger = logging.getLogger(__name__)

STATUS_MAP = {
    'planning': 'ACTIVE',
    'active': 'ACTIVE',
    'on_hold': 'PAUSED',
    'completed': 'COMPLETED',
    'archived': 'ARCHIVED',
}


@receiver(post_save, sender=Project)
def sync_project_to_worktime(sender, instance, created, **kwargs):
    from worktime.models import Project as WP

    if not instance.company:
        return

    wp_status = STATUS_MAP.get(instance.status, 'ACTIVE')

    wp = WP.objects.filter(company=instance.company, name=instance.name).first()
    if wp:
        # Update existing
        if wp.status != wp_status:
            wp.status = wp_status
            wp.save(update_fields=['status'])
    else:
        # Create new
        code = instance.code or ''
        if code and WP.objects.filter(code=code).exists():
            code = code + '-' + str(instance.company_id)[:4]
        if not code:
            code = 'P-' + uuid.uuid4().hex[:8]
        WP.objects.create(
            company=instance.company,
            name=instance.name,
            code=code,
            description=instance.description or '',
            status=wp_status,
            is_billable=True,
        )
        logger.info(f'Auto-synced project "{instance.name}" to worktime.Project')

    # Sync team -> members
    wp = WP.objects.filter(company=instance.company, name=instance.name).first()
    if wp and instance.team.exists():
        wp.members.set(instance.team.all())
