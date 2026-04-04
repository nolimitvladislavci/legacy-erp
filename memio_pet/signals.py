"""
memio_pet/signals.py -- Auto-VerificationLog na kljucne dogadjaje

Svaki put kad se:
  - Breeder OIB verificira
  - Health record s verificiranim vetom kreira
  - Ownership transfer dogodi
  - Review verificira
... automatski se kreira VerificationLog sa SHA-256 snapshotom.
"""
import hashlib
import json
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger("memio_pet")


def _create_verification_log(verification_type, snapshot_data, animal=None, breeder=None, veterinar=None, verified_by="System (auto)"):
    """Helper za kreiranje VerificationLog s SHA-256."""
    from memio_pet.models import VerificationLog
    raw = json.dumps(snapshot_data, sort_keys=True, ensure_ascii=False, default=str)
    sha = hashlib.sha256(raw.encode()).hexdigest()

    VerificationLog.objects.using("memio_pets").create(
        animal=animal,
        breeder=breeder,
        veterinar=veterinar,
        verification_type=verification_type,
        snapshot_data=snapshot_data,
        sha256_hash=sha,
        verified_by=verified_by,
    )
    logger.info("Auto VerificationLog: %s sha=%s", verification_type, sha[:16])


@receiver(post_save, sender="memio_pet.BreederProfile")
def on_breeder_save(sender, instance, created, **kwargs):
    """Kad se breeder verificira (is_cro_validated promijeni u True)."""
    if instance.is_cro_validated:
        from memio_pet.models import VerificationLog
        exists = VerificationLog.objects.using("memio_pets").filter(
            breeder=instance,
            verification_type="breeder_oib",
        ).exists()
        if not exists:
            _create_verification_log(
                verification_type="breeder_oib",
                breeder=instance,
                snapshot_data={
                    "breeder_name": instance.name,
                    "validated_name": instance.validated_name,
                    "city": instance.city,
                    "country": instance.country,
                    "account_type": instance.account_type,
                },
                verified_by="CroValidator (auto)",
            )


@receiver(post_save, sender="memio_pet.PetHealthRecord")
def on_health_record_save(sender, instance, created, **kwargs):
    """Kad se kreira health record s verificiranim vetom."""
    if created and instance.vet_profile and instance.vet_profile.is_verified:
        _create_verification_log(
            verification_type="health_cert",
            animal=instance.animal,
            breeder=instance.animal.breeder if instance.animal else None,
            veterinar=instance.vet_profile,
            snapshot_data={
                "animal_name": instance.animal.name if instance.animal else "",
                "animal_ear_tag": instance.animal.ear_tag if instance.animal else "",
                "datum": str(instance.datum),
                "tip": instance.tip,
                "opis": instance.opis,
                "vet_name": instance.vet_profile.name,
                "vet_license": instance.vet_profile.license_number,
            },
            verified_by=f"dr. {instance.vet_profile.name} (auto)",
        )


@receiver(post_save, sender="memio_pet.PetOwnership")
def on_ownership_save(sender, instance, created, **kwargs):
    """Kad se kreira ownership transfer."""
    if created:
        _create_verification_log(
            verification_type="ownership",
            animal=instance.animal,
            breeder=instance.animal.breeder if instance.animal else None,
            snapshot_data={
                "animal_name": instance.animal.name if instance.animal else "",
                "animal_ear_tag": instance.animal.ear_tag if instance.animal else "",
                "transfer_type": instance.transfer_type,
                "owner_name": instance.owner_name,
                "owner_city": instance.owner_city,
                "acquired_at": str(instance.acquired_at),
            },
            verified_by="System (auto)",
        )


@receiver(post_save, sender="memio_pet.AnimalProfile")
def on_animal_chip_registered(sender, instance, created, **kwargs):
    """Kad se zivotinja prvi put kreira s chip numberom."""
    if created and instance.chip_number:
        _create_verification_log(
            verification_type="chip_register",
            animal=instance,
            breeder=instance.breeder,
            snapshot_data={
                "name": instance.name,
                "ear_tag": instance.ear_tag,
                "chip_number": instance.chip_number,
                "vrsta": instance.vrsta,
                "breed": instance.breed,
                "breeder_name": instance.breeder.name if instance.breeder else "",
            },
            verified_by="System (auto)",
        )
