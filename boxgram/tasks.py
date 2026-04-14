import logging

from core.qr_views import qr_png_bytes
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile

from .models import Competition, PetProfile, SocialImport

logger = logging.getLogger(__name__)


@shared_task
def close_competition(competition_id):
    try:
        competition = Competition.objects.get(id=competition_id)
        competition.status = "closed"

        if competition.entries.exists():
            top_entry = competition.entries.order_by("-votes").first()
            if top_entry:
                competition.winner = top_entry.pet
                top_entry.rank = 1
                top_entry.save()

                rank = 2
                for entry in competition.entries.exclude(id=top_entry.id).order_by("-votes"):
                    entry.rank = rank
                    entry.save()
                    rank += 1

        competition.save()
        logger.info(f"Competition {competition_id} closed successfully")
    except Competition.DoesNotExist:
        logger.error(f"Competition {competition_id} not found")
    except ObjectDoesNotExist as e:
        logger.error(f"Error closing competition {competition_id}: {str(e)}")


@shared_task
def fetch_social_import(import_id):
    try:
        social_import = SocialImport.objects.get(id=import_id)
        if social_import.platform == "facebook":
            pass
        elif social_import.platform == "instagram":
            pass
        elif social_import.platform == "tiktok":
            pass
        logger.info(f"Social import {import_id} processed")
    except SocialImport.DoesNotExist:
        logger.error(f"Social import {import_id} not found")
    except ObjectDoesNotExist as e:
        logger.error(f"Error fetching social import {import_id}: {str(e)}")


@shared_task
def generate_pet_qr(pet_id):
    try:
        pet = PetProfile.objects.get(id=pet_id)
        png_bytes = qr_png_bytes(f"https://memio.pet/{pet.slug}/", size=250)
        pet.qr_code.save(f"qr_{pet.id}.png", ContentFile(png_bytes))
        pet.save()
        logger.info(f"QR code generated for pet {pet_id}")
    except PetProfile.DoesNotExist:
        logger.error(f"Pet {pet_id} not found")
    except ObjectDoesNotExist as e:
        logger.error(f"Error generating QR for pet {pet_id}: {str(e)}")


@shared_task
def bulk_sync_company_to_boxgram(company_id):
    try:
        from companies.models import Company

        from .models import PetProfile

        company = Company.objects.get(id=company_id)
        pets = PetProfile.objects.filter(company=company)

        if pets.exists():
            logger.info(f"Bulk sync for company {company_id}: {pets.count()} pets")
        else:
            logger.info(f"No pets found for company {company_id}")
    except ObjectDoesNotExist as e:
        logger.error(f"Error in bulk_sync_company_to_boxgram: {str(e)}")


@shared_task(bind=True, max_retries=3)
def retry_fetch_social_import(self, import_id):
    """Retry task za dohvaćanje social importa nakon timeout-a"""
    try:
        from .services.social_import import fetch_oembed

        social_import = SocialImport.objects.get(id=import_id)
        preview = fetch_oembed(social_import.source_url)

        if preview.success:
            social_import.raw_data = preview.raw_data
            social_import.save()
            logger.info(f"Retry successful for social import {import_id}")
        else:
            if self.request.retries < self.max_retries:
                # Retry za 5 minuta
                raise self.retry(countdown=300, exc=Exception(preview.error))
            else:
                logger.error(f"Max retries reached for social import {import_id}: {preview.error}")
    except SocialImport.DoesNotExist:
        logger.error(f"Social import {import_id} not found")
    except ObjectDoesNotExist as e:
        logger.error(f"Error in retry_fetch_social_import: {str(e)}")
        raise


@shared_task
def enrich_life_event_ai(event_id):
    """
    AI Faza 1: Auto-generiši opis za LifeEvent koristeći Haiku.
    Poziva se iz signala kada se kreira event bez opisa.
    """
    try:
        from .models import LifeEvent
        from .services.ai_enrichment import enrich_life_event

        event = LifeEvent.objects.get(id=event_id)

        # Ako već ima opisa, ne radim ništa
        if event.description and event.description.strip():
            logger.info(f"enrich_life_event_ai {event_id}: Event već ima opis, preskačem")
            return

        # Generiši opis
        description = enrich_life_event(event)

        if description:
            event.description = description
            event.save()
            logger.info(f"enrich_life_event_ai {event_id}: Opis je generiš i spreman")
        else:
            logger.warning(f"enrich_life_event_ai {event_id}: Nema generiwanog opisa")

    except LifeEvent.DoesNotExist:
        logger.error(f"enrich_life_event_ai: Event {event_id} nije pronađen")
    except ObjectDoesNotExist as e:
        logger.error(f"enrich_life_event_ai {event_id}: {type(e).__name__}: {str(e)}")
