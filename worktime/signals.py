"""
TimeEntry pre_save signal — auto-log svake izmjene u TimeLogRevision.
Inspektorat rada zahtijeva nepromjenjivi trag.
"""
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

TRACKED_FIELDS = [
    'start_time', 'end_time', 'duration', 'date',
    'regular_hours', 'overtime_hours', 'night_hours',
    'status', 'break_minutes',
]


@receiver(pre_save, sender='worktime.TimeEntry')
def log_timeentry_revision(sender, instance, **kwargs):
    if not instance.pk:
        return  # novi zapis, nema što logirati

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    from core.audit import get_current_user
    user = get_current_user()

    for field in TRACKED_FIELDS:
        old_val = getattr(old, field, None)
        new_val = getattr(instance, field, None)
        if str(old_val) != str(new_val):
            from .models import TimeLogRevision
            TimeLogRevision.objects.create(
                time_entry=instance,
                company=instance.company,
                changed_by=user if user and hasattr(user, 'is_authenticated') and user.is_authenticated else None,
                field_name=field,
                old_value=str(old_val) if old_val is not None else '',
                new_value=str(new_val) if new_val is not None else '',
            )
