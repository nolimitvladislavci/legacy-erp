"""
BORG Trust Decay — meaningful human control mechanism.

Sprjecava algoritamsku ljenost: ako korisnik 30 dana ne odbije
nijednu akciju, sustav namjerno forsa checkpoint.

Graduated Autonomy:
- Novi tenant = suggest_only
- 20 potvrda iste kategorije = ponudi semi_auto
- NIKAD full_auto za financijske/pravne akcije
"""
import logging
from django.utils import timezone

logger = logging.getLogger('borg.trust')

TRUST_DECAY_DAYS = 30
CATEGORY_THRESHOLD = 20


def get_or_create_tracker(company):
    """Get or create BorgAutonomyTracker for company."""
    from borg_ops.models import BorgAutonomyTracker
    tracker, _ = BorgAutonomyTracker.objects.get_or_create(company=company)
    return tracker


def record_user_decision(company, borg_task, approved):
    """
    Bilježi svako odobrenje/odbijanje za Trust Decay.
    Poziva se kad korisnik prihvati ili odbije BorgTask.
    """
    tracker = get_or_create_tracker(company)
    today = timezone.now().date()

    if approved:
        tracker.auto_approved_streak += 1
        # Track category approvals
        category = borg_task.task_type
        approvals = tracker.category_approvals or {}
        approvals[category] = approvals.get(category, 0) + 1
        tracker.category_approvals = approvals

        # Check for autonomy upgrade
        if approvals[category] >= CATEGORY_THRESHOLD and tracker.autonomy_level == 'suggest_only':
            logger.info(
                'Trust upgrade available for %s: %s has %d approvals',
                company.name, category, approvals[category],
            )
    else:
        # Rejection resets streak
        tracker.auto_approved_streak = 0
        tracker.last_rejection_date = today

    tracker.save()
    return tracker


def check_trust_decay(company):
    """
    Ako streak > 30 dana bez odbijanja -> forsiraj checkpoint.
    Returns: True if checkpoint needed, False otherwise.
    """
    tracker = get_or_create_tracker(company)
    today = timezone.now().date()

    # Skip if already checkpointed today
    if tracker.last_checkpoint_date == today:
        return False

    # If never rejected, use created_at as baseline
    baseline = tracker.last_rejection_date
    if baseline is None:
        baseline = tracker.created_at.date() if tracker.created_at else today

    days_since_rejection = (today - baseline).days

    if days_since_rejection >= TRUST_DECAY_DAYS:
        # Force checkpoint
        tracker.last_checkpoint_date = today
        tracker.save(update_fields=['last_checkpoint_date', 'updated_at'])

        # Log audit entry
        from borg_ops.audit_helpers import log_borg_audit
        log_borg_audit(
            company=company,
            entry_type='TRUST_CHECKPOINT',
            summary=(
                f'Kontrolna tocka povjerenja: {days_since_rejection} dana bez odbijanja. '
                f'Streak: {tracker.auto_approved_streak}. '
                f'Razina: {tracker.get_autonomy_level_display()}.'
            ),
            severity='INFO',
            metadata={
                'days_since_rejection': days_since_rejection,
                'streak': tracker.auto_approved_streak,
                'autonomy_level': tracker.autonomy_level,
            },
        )

        logger.info(
            'TRUST CHECKPOINT for %s: %d days without rejection',
            company.name, days_since_rejection,
        )
        return True

    return False


def check_trust_decay_all():
    """Check trust decay for all companies with active autonomy trackers."""
    from borg_ops.models import BorgAutonomyTracker
    trackers = BorgAutonomyTracker.objects.select_related('company').all()
    checkpoints = 0
    for tracker in trackers:
        if check_trust_decay(tracker.company):
            checkpoints += 1
    return checkpoints
