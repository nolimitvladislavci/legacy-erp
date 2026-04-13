"""
memio_pet/tasks.py -- Celery periodic tasks

trust_score_refresh: Svaka 24h recalculate Trust Score za sve breedere.
"""
import logging
from celery import shared_task

logger = logging.getLogger("memio_pet")


@shared_task(name="memio_pet.trust_score_refresh")
def trust_score_refresh():
    """Periodic: refresh Trust Score za sve breedere."""
    from memio_pet.trust_score import bulk_update_trust_scores
    results = bulk_update_trust_scores()
    logger.info("Trust Score refresh: %d breedera azurirano", len(results))
    return {"updated": len(results), "scores": {name: score for name, score in results}}


import math

def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


@shared_task(name='memio_pet.notify_barf_breeders')
def notify_barf_breeders(listing_id):
    """Notificiraj BARF partnere u radijusu o novoj ponudi."""
    from memio_pet.models import RawFoodListing, BreederProfile
    from django.core.cache import cache

    try:
        listing = RawFoodListing.objects.get(pk=listing_id, status='available')
    except RawFoodListing.DoesNotExist:
        return

    if not listing.latitude or not listing.longitude:
        return

    breeders = BreederProfile.objects.filter(barf_partner=True).exclude(phone='')
    notified = 0

    for br in breeders:
        if br.latitude and br.longitude:
            km = _haversine_km(listing.latitude, listing.longitude, br.latitude, br.longitude)
            if km > (br.barf_radius_km or 50):
                continue

        cache_key = f'barf_notif:{br.pk}:{listing.product_type}:{listing.available_from}'
        if cache.get(cache_key):
            continue

        msg = (f'BARF ponuda:\n'
               f'{listing.get_product_type_display()} — {listing.quantity_kg}kg\n'
               f'{listing.price_eur_kg} EUR/kg\n'
               f'OPG: {listing.company.name}\n'
               f'memio.pet/barf/')

        try:
            from core.whatsapp import send_whatsapp
            if br.phone:
                send_whatsapp(br.phone, msg)
                cache.set(cache_key, 1, 86400)
                notified += 1
        except ImportError:
            pass

    logger.info('notify_barf_breeders: %s notifikacija za listing %s', notified, listing_id)


@shared_task(name="memio_pet.send_odjava_reminder")
def send_odjava_reminder(animal_pk):
    """Šalje podsjetnik za zakonsku odjavu — 10 dana nakon uginuća."""
    try:
        from memio_pet.models import AnimalProfile
        animal = AnimalProfile.objects.using('memio_pets').get(pk=animal_pk)
        if animal.status != 'uginulo':
            return 'skip: status changed'

        breeder = animal.breeder
        if not breeder or not breeder.email:
            return 'skip: no breeder email'

        from django.core.mail import send_mail
        identifier = animal.chip_number or animal.ear_tag
        send_mail(
            subject=f'Podsjetnik — odjava {animal.name} iz Upisnika',
            message=(
                f'Dragi {breeder.name},\n\n'
                f'Podsjećamo da ste zakonski obvezni odjaviti {animal.name} '
                f'iz Upisnika kućnih ljubimaca u roku 14 dana od uginuća.\n\n'
                f'Odjava: https://e-uprava.gov.hr\n\n'
                f'Memorijal {animal.name}: '
                f'https://memio.pet/pas/{identifier}/\n\n'
                f'S poštovanjem,\nMemio.pet tim'
            ),
            from_email='noreply@memio.pet',
            recipient_list=[breeder.email],
            fail_silently=True,
        )
        logger.info("Odjava reminder sent for %s to %s", animal.name, breeder.email)
        return f'sent to {breeder.email}'
    except Exception as e:
        logger.error("Odjava reminder error: %s", e)
        return f'error: {e}'
