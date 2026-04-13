"""
memio_pet/bridge.py — API Bridge: LIMIT Connect → Memio.pet baza

Jednosmjerni push: ERP podatak → memio_pets DB.
Sve se upisuje kroz ove funkcije, nikad direktnim ORM pozivom iz ERP koda.

Koristiti:
    from memio_pet.bridge import push_animal_profile, push_breeder_profile
"""

import logging

logger = logging.getLogger(__name__)


def push_breeder_profile(company) -> "BreederProfile":
    """
    Sinkronizira Company iz ERP-a u BreederProfile u memio_pets bazi.
    Poziva se kad se firma registrira ili kad se ažuriraju podaci.
    """
    from memio_pet.models import BreederProfile

    account_type = "shelter" if getattr(company, "is_shelter", False) else "breeder"

    profile, created = BreederProfile.objects.using("memio_pets").update_or_create(
        limit_company_id=str(company.pk),
        defaults={
            "account_type": account_type,
            "oib": company.oib or "",
            "name": company.name,
            "city": company.city or "",
            "country": company.country or "HR",
            "is_no_limit_partner": getattr(company, "is_shelter", False),
            "shelter_sponsor": getattr(company, "shelter_sponsor", "") or "",
        },
    )
    action = "kreiran" if created else "ažuriran"
    logger.info("Breeder profil %s: %s (company=%s)", action, profile.name, company.pk)
    return profile


def push_animal_profile(livestock_obj) -> "AnimalProfile":
    """
    Kopira Livestock objekt iz ERP-a u AnimalProfile u memio_pets bazi.
    Poziva se:
      - pri kreiranju ljubimca u LIMIT Connect
      - pri promjeni statusa (npr. prodano, udomljeno)
      - pri dodavanju zdravstvenih zapisa
    """
    from memio_pet.models import AnimalProfile, BreederProfile

    company = livestock_obj.company

    # Osiguraj da breeder postoji u memio_pets
    try:
        breeder = BreederProfile.objects.using("memio_pets").get(limit_company_id=str(company.pk))
    except BreederProfile.DoesNotExist:
        breeder = push_breeder_profile(company)

    # Kreiraj ili ažuriraj profil (ear_tag je unique identifier)
    profile, created = AnimalProfile.objects.using("memio_pets").update_or_create(
        ear_tag=livestock_obj.ear_tag,
        defaults={
            "chip_number": livestock_obj.chip_number or "",
            "pedigree_number": getattr(livestock_obj, "pedigree_number", "") or "",
            "name": livestock_obj.name or "",
            "vrsta": livestock_obj.vrsta,
            "breed": livestock_obj.breed or "",
            "spol": getattr(livestock_obj, "spol", "N") or "N",
            "color_description": getattr(livestock_obj, "color_description", "") or "",
            "date_of_birth": livestock_obj.date_of_birth,
            "weight_kg": livestock_obj.weight_kg,
            "father_name": getattr(livestock_obj, "father_name", "") or "",
            "mother_name": getattr(livestock_obj, "mother_name", "") or "",
            "status": _map_status(livestock_obj.status),
            "notes": livestock_obj.notes or "",
            "breeder": breeder,
            "breeder_name_snapshot": company.name,
            "breeder_oib_snapshot": company.oib or "",
            "limit_livestock_id": livestock_obj.pk,
        },
    )

    action = "kreiran" if created else "ažuriran"
    logger.info("AnimalProfile %s: %s (livestock_id=%s)", action, profile.name or profile.ear_tag, livestock_obj.pk)
    return profile


def push_health_record(health_record_obj, animal_profile=None):
    """
    Kopira HealthRecord iz ERP-a u PetHealthRecord u memio_pets bazi.
    """
    from memio_pet.models import AnimalProfile, PetHealthRecord

    livestock = health_record_obj.animal

    if animal_profile is None:
        try:
            animal_profile = AnimalProfile.objects.using("memio_pets").get(limit_livestock_id=livestock.pk)
        except AnimalProfile.DoesNotExist:
            animal_profile = push_animal_profile(livestock)

    PetHealthRecord.objects.using("memio_pets").update_or_create(
        animal=animal_profile,
        datum=health_record_obj.datum,
        tip=health_record_obj.tip,
        opis=health_record_obj.opis or "",
        defaults={
            "veterinar": health_record_obj.veterinar or "",
            "lijek": health_record_obj.lijek or "",
            "trosak_eur": health_record_obj.trosak_eur,
        },
    )


def _map_status(erp_status: str) -> str:
    """Mapira ERP status na memio_pet status."""
    mapping = {
        "aktivno": "aktivno",
        "prodano": "prodano",
        "uginulo": "uginulo",
        "u_azilu": "u_azilu",
        "karantena": "karantena",
        "rezerviran": "rezerviran",
        "udomljen": "udomljen",
        "eutanaziran": "uginulo",
        "gravidno": "aktivno",
        "zasuseno": "aktivno",
        "tov": "aktivno",
        "izluceno": "aktivno",
    }
    return mapping.get(erp_status, "aktivno")
