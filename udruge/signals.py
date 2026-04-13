import logging

from django.db import DatabaseError, IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger("udruge")


@receiver(post_save, sender="udruge.KnjigaPrimitaka")
def archive_knjiga_primitaka(sender, instance, created, **kwargs):
    """Auto-arhivira KnjigaPrimitaka u ArhivaEntry."""
    if not created:
        return
    try:
        from documents.models import ArhivaEntry

        source_id = str(instance.pk)
        if ArhivaEntry.objects.filter(source_type="document", source_id=source_id).exists():
            return
        ArhivaEntry.objects.create(
            company=instance.company,
            source_type="document",
            source_id=source_id,
            doc_number=f"KP-{instance.redni_broj}",
            partner_name=(instance.opis or "")[:100],
            amount=instance.iznos,
            currency="EUR",
            doc_date=instance.datum,
            ai_summary=f"Knjiga primitaka #{instance.redni_broj}: {instance.get_vrsta_display()} — {instance.get_izvor_display()}",
        )
    except (IntegrityError, DatabaseError) as e:
        logger.error("archive_knjiga_primitaka: %s", e)


@receiver(post_save, sender="udruge.Donacija")
def archive_donacija(sender, instance, created, **kwargs):
    """Auto-arhivira Donaciju u ArhivaEntry."""
    if not created:
        return
    try:
        from documents.models import ArhivaEntry

        sid = f"don-{instance.pk}"
        if ArhivaEntry.objects.filter(source_type="document", source_id=sid).exists():
            return
        ArhivaEntry.objects.create(
            company=instance.company,
            source_type="document",
            source_id=sid,
            doc_number=instance.potvrda_number or f"DON-{instance.pk}",
            partner_name=instance.donor_name[:200],
            amount=instance.amount,
            currency="EUR",
            doc_date=instance.date,
            ai_summary=f"Donacija: {instance.donor_name} {instance.amount} EUR — {instance.purpose or 'opca'}",
        )
    except (IntegrityError, DatabaseError) as e:
        logger.error("archive_donacija: %s", e)
