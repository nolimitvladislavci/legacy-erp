"""
memio_pet ↔ boxgram Bridge
Spaja AnimalProfile s PetProfile, PetHealthRecord s LifeEvent.
Jednosmjerni sync: memio_pet → boxgram (javni profil).
"""
import logging

from django.utils.text import slugify

logger = logging.getLogger(__name__)


def sync_animal_to_boxgram(animal):
    """
    AnimalProfile → PetProfile + LifeEvent(rodenje).
    Idempotentno — ne kreira duplikate.
    """
    from boxgram.models import LifeEvent, PetProfile

    ref = f'memio_pet:{animal.pk}'

    # Nađi ili kreiraj PetProfile
    pet, created = PetProfile.objects.get_or_create(
        limit_connect_ref=ref,
        defaults={
            'name': animal.name,
            'species': _map_species(animal.vrsta),
            'breed': animal.breed or '',
            'birth_date': animal.date_of_birth,
            'bio': _build_bio(animal),
            'slug': _unique_slug(animal),
            'is_public': True,
            'is_verified_breeder': bool(animal.breeder and animal.breeder.is_cro_validated),
            'tenant_id': _get_tenant_id(animal),
            'owner_id': _get_owner_id(animal),
        }
    )

    if created:
        logger.info(f'Bridge: AnimalProfile {animal.name} → PetProfile {pet.slug}')

        # LifeEvent: rođenje
        if animal.date_of_birth:
            LifeEvent.objects.get_or_create(
                pet=pet,
                source_id=f'birth_{animal.pk}',
                defaults={
                    'event_type': 'rodenje',
                    'title': f'{animal.name} je na svijetu!',
                    'date': animal.date_of_birth,
                    'source': 'manual',
                    'is_public': True,
                }
            )

        # LifeEvent: usvajanje/vlasništvo
        from memio_pet.models import PetOwnership
        for ownership in PetOwnership.objects.filter(animal=animal).order_by('acquired_at'):
            LifeEvent.objects.get_or_create(
                pet=pet,
                source_id=f'ownership_{ownership.pk}',
                defaults={
                    'event_type': 'usvajanje' if ownership.transfer_type == 'adoption' else 'promjena_vlasnika',
                    'title': f'{animal.name} — {ownership.get_transfer_type_display() if hasattr(ownership, "get_transfer_type_display") else ownership.transfer_type}',
                    'description': f'Vlasnik: {ownership.owner_name}, {ownership.owner_city}' if hasattr(ownership, 'owner_city') else f'Vlasnik: {ownership.owner_name}',
                    'date': ownership.acquired_at or animal.date_of_birth,
                    'source': 'manual',
                    'is_public': True,
                }
            )
    else:
        # Update postojeći profil
        pet.name = animal.name
        pet.breed = animal.breed or ''
        pet.birth_date = animal.date_of_birth
        pet.bio = _build_bio(animal)
        pet.save(update_fields=['name', 'breed', 'birth_date', 'bio', 'updated_at'])

    return pet


def sync_health_record_to_boxgram(health_record):
    """
    PetHealthRecord → LifeEvent(vet/cijepljenje).
    """
    from boxgram.models import LifeEvent, PetProfile

    ref = f'memio_pet:{health_record.animal_id}'
    try:
        pet = PetProfile.objects.get(limit_connect_ref=ref)
    except PetProfile.DoesNotExist:
        # Prvo sync-aj animal
        pet = sync_animal_to_boxgram(health_record.animal)

    event_type = 'cijepljenje' if health_record.tip == 'cijepljenje' else 'vet'

    event, created = LifeEvent.objects.get_or_create(
        pet=pet,
        source_id=f'health_{health_record.pk}',
        defaults={
            'event_type': event_type,
            'title': f'{health_record.get_tip_display() if hasattr(health_record, "get_tip_display") else health_record.tip} — {health_record.animal.name}',
            'description': health_record.opis or '',
            'date': health_record.datum,
            'source': 'manual',
            'is_public': event_type == 'cijepljenje',  # Cijepljenja javna, ostalo privatno
            'is_verified': bool(health_record.veterinar),
        }
    )

    if created:
        logger.info(f'Bridge: PetHealthRecord {health_record.pk} → LifeEvent {event.pk}')

    return event


def sync_all_animals():
    """Bulk sync svih AnimalProfile-a. Za inicijalni import."""
    from memio_pet.models import AnimalProfile, PetHealthRecord

    synced_pets = 0
    synced_events = 0

    for animal in AnimalProfile.objects.select_related('breeder').all():
        sync_animal_to_boxgram(animal)
        synced_pets += 1

    for hr in PetHealthRecord.objects.select_related('animal').all():
        sync_health_record_to_boxgram(hr)
        synced_events += 1

    logger.info(f'Bridge bulk sync: {synced_pets} pets, {synced_events} health records')
    return {'pets': synced_pets, 'events': synced_events}


def _map_species(vrsta):
    """memio_pet vrsta → boxgram species."""
    MAP = {
        'pas': 'pas', 'dog': 'pas',
        'macka': 'macka', 'cat': 'macka',
        'konj': 'konj', 'horse': 'konj',
        'ptica': 'ptica', 'bird': 'ptica',
        'zec': 'zec', 'rabbit': 'zec',
    }
    return MAP.get(str(vrsta).lower(), 'ostalo')


def _build_bio(animal):
    """Generiraj bio iz AnimalProfile podataka."""
    parts = []
    if animal.breed:
        parts.append(animal.breed)
    if animal.color_description:
        parts.append(animal.color_description)
    if animal.chip_number:
        parts.append(f'Chip: {animal.chip_number}')
    if animal.pedigree_number:
        parts.append(f'Rodovnik: {animal.pedigree_number}')
    if animal.father_name or animal.mother_name:
        parents = []
        if animal.father_name:
            parents.append(f'otac: {animal.father_name}')
        if animal.mother_name:
            parents.append(f'majka: {animal.mother_name}')
        parts.append(', '.join(parents))
    return ' · '.join(parts) if parts else ''


def _unique_slug(animal):
    """Generiraj unique slug."""
    base = slugify(f'{animal.name}-{animal.vrsta}')[:40]
    return f'{base}-{str(animal.pk)[:8]}'


def _get_owner_id(animal):
    """Dohvati User vlasnika za animal."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    # Ako breeder ima email, traži usera
    if animal.breeder:
        email = getattr(animal.breeder, 'email', None)
        if email:
            user = User.objects.filter(email=str(email)).first()
            if user:
                return user.pk
    # Fallback: prvi superuser
    admin = User.objects.filter(is_superuser=True).first()
    return admin.pk if admin else None


def _get_tenant_id(animal):
    """Dohvati company (tenant) za animal. PetProfile.tenant je FK na Company."""
    from django.apps import apps
    Company = apps.get_model('companies', 'Company')

    # Ako breeder ima linkanu LIMIT Connect firmu
    if animal.breeder and animal.breeder.limit_company_id:
        try:
            return int(animal.breeder.limit_company_id)
        except (ValueError, TypeError):
            pass

    # Fallback: prva firma
    first = Company.objects.first()
    return first.pk if first else None
