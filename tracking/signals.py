from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="documents.Otpremnica")
def create_tracking_for_otpremnica(sender, instance, **kwargs):
    """Auto-create TrackedItem when Otpremnica is confirmed."""
    if instance.status != "confirmed":
        return
    from tracking.models import TrackedItem, TrackingStatus

    ct = ContentType.objects.get_for_model(instance)
    obj, created = TrackedItem.objects.get_or_create(
        content_type=ct,
        object_id=str(instance.pk),
        defaults={
            "tracking_type": "shipment",
        },
    )
    if created:
        status_qs = TrackingStatus.objects.filter(tracking_type="shipment", slug="ready")
        if status_qs.exists():
            obj.current_status = status_qs.first()
            obj.save(update_fields=["current_status"])


@receiver(post_save, sender="documents.CMR")
def create_tracking_for_cmr(sender, instance, **kwargs):
    """Auto-create TrackedItem when CMR is confirmed."""
    if instance.status != "confirmed":
        return
    from tracking.models import TrackedItem, TrackingStatus

    ct = ContentType.objects.get_for_model(instance)
    obj, created = TrackedItem.objects.get_or_create(
        content_type=ct,
        object_id=str(instance.pk),
        defaults={
            "tracking_type": "shipment",
        },
    )
    if created:
        status_qs = TrackingStatus.objects.filter(tracking_type="shipment", slug="ready")
        if status_qs.exists():
            obj.current_status = status_qs.first()
            obj.save(update_fields=["current_status"])
