"""
Celery periodic tasks for interventions.
Wraps the existing check_ttl management command.
"""

import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task
def check_intervention_ttl():
    """Run the check_ttl management command via Celery Beat."""
    call_command("check_ttl")
    logger.info("check_intervention_ttl: completed")
