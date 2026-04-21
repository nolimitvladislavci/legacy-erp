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


def _create_verification_log(
    verification_type, snapshot_data, animal=None, breeder=None, veterinar=None, verified_by="System (auto)"
):
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

        exists = (
            VerificationLog.objects.using("memio_pets")
            .filter(
                breeder=instance,
                verification_type="breeder_oib",
            )
            .exists()
        )
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


@receiver(post_save, sender="memio_pet.RawFoodListing")
def on_barf_listing_created(sender, instance, created, **kwargs):
    """Nova BARF ponuda → notificiraj uzgajivače u radijusu."""
    if created and instance.status == "available":
        try:
            from memio_pet.tasks import notify_barf_breeders

            notify_barf_breeders.delay(instance.pk)
        except ImportError as e:
            import logging

            logging.getLogger("memio_pet").warning("BARF signal: %s", e)


@receiver(post_save, sender="memio_pet.AnimalProfile")
def on_animal_status_uginulo(sender, instance, **kwargs):
    """Kad status = uginulo → kreiraj MemorialProfile automatski."""
    if instance.status != "uginulo":
        return

    from memio_pet.models import MemorialProfile

    db = "memio_pets"
    memorial, created = MemorialProfile.objects.using(db).get_or_create(
        animal=instance,
        defaults={
            "date_of_death": instance.updated_at.date()
            if hasattr(instance, "updated_at") and instance.updated_at
            else None,
        },
    )
    if created:
        logger.info("MemorialProfile kreiran za %s (pk=%s)", instance.name, instance.pk)
        # Email vlasniku
        try:
            from django.core.mail import send_mail

            breeder = instance.breeder
            if breeder and breeder.email:
                identifier = instance.chip_number or instance.ear_tag
                send_mail(
                    subject=f"Memorijal za {instance.name} — Memio.pet",
                    message=(
                        f"Dragi {breeder.name},\n\n"
                        f"Stranica sjećanja za {instance.name} je kreirana:\n"
                        f"https://memio.pet/pas/{identifier}/\n\n"
                        f"Možete dodati posmrtnu poruku i urediti memorijal.\n\n"
                        f"Naše najdublje sućuti.\n"
                        f"— Memio.pet tim"
                    ),
                    from_email="noreply@memio.pet",
                    recipient_list=[breeder.email],
                    fail_silently=True,
                )
        except ImportError:
            pass
        # Celery podsjetnik za zakonsku odjavu (10 dana)
        try:
            from memio_pet.tasks import send_odjava_reminder

            send_odjava_reminder.apply_async(
                args=[str(instance.pk)],
                countdown=10 * 24 * 3600,
            )
        except ImportError:
            pass  # Celery možda nije aktivan


# ═══════════════════════════════════════════════════════════════
# BRIDGE SIGNAL: Company (ERP) → BreederProfile (memio_pets)
# Kad se Company s is_shelter=True spremi, automatski sync u memio_pets
# ═══════════════════════════════════════════════════════════════


@receiver(post_save, sender="companies.Company")
def on_company_shelter_save(sender, instance, **kwargs):
    """Auto-push shelter/breeder profile to memio_pets when Company saved with is_shelter."""
    if not instance.is_shelter:
        return
    try:
        from memio_pet.bridge import push_breeder_profile

        push_breeder_profile(instance)
        logger.info("Bridge auto-push: %s → memio_pets (shelter)", instance.name)
    except Exception as e:
        logger.warning("Bridge push failed for %s: %s", instance.name, e)


# ═══════════════════════════════════════════════════════════════
# DIGITALNO NASLJEĐE — Heritage Bridge Signals (2026-04-21)
# Patent MPH-001: Kriptografski verificirano digitalno nasljeđe
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender="memio_pet.AnimalProfile")
def on_animal_status_heritage_sync(sender, instance, **kwargs):
    """
    Kad animal.status → uginulo:
      → Pokretanje sync_dugini_most_to_oracles(animal)
      → Svako dijete u sustavu dobiva memorial pet_fragment u HeritageOracle
    """
    if instance.status != "uginulo":
        return
    try:
        from memio_world.heritage_bridge import sync_dugini_most_to_oracles
        count = sync_dugini_most_to_oracles(instance)
        if count:
            logger.info(
                "Heritage Bridge: Dugini Most '%s' → %d Oracle(a) ažurirano",
                instance.name, count
            )
    except Exception as exc:
        logger.warning("Heritage Bridge signal greška (non-critical): %s", exc)


@receiver(post_save, sender="memio_pet.HeritageTrait")
def on_heritage_trait_save(sender, instance, created, **kwargs):
    """
    Kad se kreira/ažurira HeritageTrait → recalculate DigitalHeritage score.
    """
    if not created:
        return
    try:
        from memio_pet.trust_score import update_digital_heritage
        update_digital_heritage(instance.animal)
        logger.info("DigitalHeritage recalculated za %s", instance.animal.name)
    except Exception as exc:
        logger.warning("Heritage recalc signal greška: %s", exc)


@receiver(post_save, sender="memio_pet.LegacyBequest")
def on_legacy_bequest_created(sender, instance, created, **kwargs):
    """
    Kad se kreira LegacyBequest → VerificationLog za nepromjenjivost.
    """
    if not created:
        return
    try:
        _create_verification_log(
            verification_type="chip_register",  # reuse za bequest
            animal=instance.animal,
            breeder=instance.animal.breeder if instance.animal else None,
            snapshot_data={
                "bequest_id": str(instance.pk),
                "animal_name": instance.animal.name,
                "successor_hash": instance.successor_email_hash[:16] + "...",
                "seal_hash": instance.seal_hash[:16] + "...",
                "trigger": instance.trigger,
                "created_at": str(instance.created_at),
            },
            verified_by="System (auto — LegacyBequest)",
        )
        logger.info("LegacyBequest VerificationLog kreiran za %s", instance.animal.name)
    except Exception as exc:
        logger.warning("LegacyBequest signal greška: %s", exc)
