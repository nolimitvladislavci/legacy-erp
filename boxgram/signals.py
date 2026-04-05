"""
Boxgram Sync Bridge — Django signali
LIMIT Connect → Boxgram automatski sync

Princip: "inform aggressively, execute conservatively"
- Signal uvijek pali
- Nikad ne blokira original save()
- Tiho preskače ako nema PetProfile za tu company
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
# PČELARSTVO — HoneyHarvest → LifeEvent
# ══════════════════════════════════════════════════════

def on_honey_harvest_saved(sender, instance, created, **kwargs):
    """
    Berba meda → milestone objava na pčelinjak profilu.
    HoneyHarvest fields: apiary(FK), datum, kolicina_kg, vrsta, cijena_kg
    """
    if not created:
        return
    try:
        from .models import PetProfile, LifeEvent

        # Traži PetProfile po company (Apiary.company → PetProfile.company)
        company = getattr(instance.apiary, 'company', None)
        if not company:
            return

        pets = PetProfile.objects.filter(company=company, species='pcela')
        if not pets.exists():
            return

        for pet in pets:
            LifeEvent.objects.get_or_create(
                pet=pet,
                source_id=f'honey_{instance.pk}',
                defaults={
                    'event_type': 'milestone',
                    'title': f'Berba meda — {instance.get_vrsta_display()}',
                    'description': (
                        f'{instance.kolicina_kg} kg {instance.get_vrsta_display().lower()} '
                        f's pčelinjaka {instance.apiary.naziv}.'
                    ),
                    'date': instance.datum,
                    'location': getattr(instance.apiary, 'adresa', ''),
                    'source': 'manual',
                    'is_public': True,
                }
            )
            logger.info(f'Boxgram sync: HoneyHarvest {instance.pk} → PetProfile {pet.id}')
    except Exception as e:
        logger.warning(f'Boxgram sync skip (HoneyHarvest {getattr(instance, "pk", "?")}): {e}')


# ══════════════════════════════════════════════════════
# PČELARSTVO — HiveInspection → LifeEvent (samo tretmani)
# ══════════════════════════════════════════════════════

def on_hive_inspection_saved(sender, instance, created, **kwargs):
    """
    Pregled košnice s tretmanom → vet posjet.
    HiveInspection fields: hive(FK→Apiary), datum, tretman_varroa, varroa_posip, snaga_zajednice
    """
    if not created:
        return
    # Samo značajni pregledi s tretmanom idu u javni feed
    if not instance.tretman_varroa and not instance.varroa_posip:
        return
    try:
        from .models import PetProfile, LifeEvent

        company = getattr(instance.hive.apiary, 'company', None)
        if not company:
            return

        pets = PetProfile.objects.filter(company=company, species='pcela')
        for pet in pets:
            LifeEvent.objects.get_or_create(
                pet=pet,
                source_id=f'inspect_{instance.pk}',
                defaults={
                    'event_type': 'vet',
                    'title': f'Tretman varoze — {instance.hive.oznaka}',
                    'description': (
                        f'Pregled košnice {instance.hive.oznaka}. '
                        f'Tretman: {instance.tretman_varroa}. '
                        f'Snaga zajednice: {instance.snaga_zajednice}/5.'
                    ),
                    'date': instance.datum,
                    'source': 'manual',
                    'is_public': False,
                }
            )
    except Exception as e:
        logger.warning(f'Boxgram sync skip (HiveInspection {getattr(instance, "pk", "?")}): {e}')


# ══════════════════════════════════════════════════════
# PČELARSTVO — EPPDojava → LifeEvent
# ══════════════════════════════════════════════════════

def on_epp_dojava_saved(sender, instance, created, **kwargs):
    """
    EPP Prilog 3 predano → milestone na profilu.
    EPPDojava fields: company, godina, datum_dojave, predano, predano_datum, ukupno_zajednica
    """
    if not instance.predano:
        return
    try:
        from .models import PetProfile, LifeEvent

        pets = PetProfile.objects.filter(company=instance.company, species='pcela')
        for pet in pets:
            LifeEvent.objects.get_or_create(
                pet=pet,
                source_id=f'epp_{instance.pk}',
                defaults={
                    'event_type': 'nagrada',
                    'title': f'EPP dojava {instance.godina}. predana ✓',
                    'description': (
                        f'Godišnja dojava broja pčelinjih zajednica za {instance.godina}. '
                        f'Ukupno {instance.ukupno_zajednica} zajednica u evidenciji.'
                    ),
                    'date': instance.predano_datum or instance.datum_dojave,
                    'source': 'manual',
                    'is_public': True,
                }
            )
    except Exception as e:
        logger.warning(f'Boxgram sync skip (EPPDojava {getattr(instance, "pk", "?")}): {e}')


# ══════════════════════════════════════════════════════
# UZGAJALIŠTE — Animal → PetProfile + LifeEvent
# ══════════════════════════════════════════════════════

SPECIES_MAP = {
    'pas': 'pas', 'dog': 'pas',
    'macka': 'macka', 'cat': 'macka',
    'konj': 'konj', 'horse': 'konj',
    'govedo': 'govedo', 'cattle': 'govedo', 'krava': 'govedo',
    'svinja': 'svinja', 'pig': 'svinja',
    'ovca': 'ovca', 'sheep': 'ovca',
    'koza': 'koza', 'goat': 'koza',
}


def on_animal_saved(sender, instance, created, **kwargs):
    """
    Novo mladunče → auto-kreacija PetProfile + LifeEvent rodenje.
    Radi samo za firme koje su linkane s Boxgramom.
    """
    if not created:
        return
    try:
        from .models import PetProfile, LifeEvent
        from django.utils.text import slugify
        import datetime

        company = getattr(instance, 'company', None)
        if not company:
            return

        # Provjeri ima li firma već Boxgram profile
        if not PetProfile.objects.filter(company=company).exists():
            return  # Firma nije onboardana na Boxgram — preskači

        species_raw = str(getattr(instance, 'vrsta', '') or getattr(instance, 'species', '')).lower()
        species = SPECIES_MAP.get(species_raw, 'ostalo')

        ime = getattr(instance, 'ime', None) or getattr(instance, 'name', None) or f'Ljubimac {instance.pk}'
        birth_date = getattr(instance, 'datum_rodenja', None) or getattr(instance, 'birth_date', None)

        # Generiraj unique slug
        base_slug = slugify(f'{ime}-{species}')[:40]
        slug = f'{base_slug}-{str(instance.pk)[:8]}'

        # Tenant — uzmi prvi tenant firme
        tenant = None
        if hasattr(company, 'tenant_set'):
            tenant = company.tenant_set.first()
        if not tenant and hasattr(company, 'tenant'):
            tenant = company.tenant

        if not tenant:
            logger.warning(f'Boxgram: Animal {instance.pk} — nema tenant za company {company.pk}')
            return

        pet, pet_created = PetProfile.objects.get_or_create(
            limit_connect_ref=f'livestock:{instance.pk}',
            defaults={
                'tenant': tenant,
                'company': company,
                'name': ime,
                'species': species,
                'birth_date': birth_date,
                'slug': slug,
                'is_public': True,
            }
        )

        if pet_created:
            LifeEvent.objects.create(
                pet=pet,
                event_type='rodenje',
                title=f'{ime} je na svijetu!',
                description='Novo mladunče registrirano u uzgajalištu.',
                date=birth_date or datetime.date.today(),
                source='manual',
                is_public=True,
            )
            logger.info(f'Boxgram: Auto-kreiran PetProfile za {ime} (Animal {instance.pk})')
    except Exception as e:
        logger.warning(f'Boxgram sync skip (Animal {getattr(instance, "pk", "?")}): {e}')


# ══════════════════════════════════════════════════════
# INVOICING — R1 vezan uz HoneyHarvest → verified event
# ══════════════════════════════════════════════════════

def on_invoice_saved(sender, instance, created, **kwargs):
    """
    R1 račun za berbu meda → LifeEvent dobiva is_verified=True.
    HoneyHarvest ima OneToOne FK na Invoice.
    """
    if not created:
        return
    try:
        from .models import LifeEvent
        from livestock.models import HoneyHarvest

        harvests = HoneyHarvest.objects.filter(invoice=instance)
        for harvest in harvests:
            updated = LifeEvent.objects.filter(
                source_id=f'honey_{harvest.pk}'
            ).update(is_verified=True)
            if updated:
                logger.info(f'Boxgram: LifeEvent verified via Invoice {instance.pk}')
    except Exception as e:
        logger.warning(f'Boxgram sync skip (Invoice {getattr(instance, "pk", "?")}): {e}')


# ══════════════════════════════════════════════════════
# REGISTRACIJA SIGNALA
# ══════════════════════════════════════════════════════

def connect_signals():
    """
    Poziva se iz BoxgramConfig.ready().
    Koristi string-based sender za lazy import — izbjegava circular imports.
    """
    try:
        from django.apps import apps

        if apps.is_installed('livestock'):
            try:
                HoneyHarvest = apps.get_model('livestock', 'HoneyHarvest')
                post_save.connect(on_honey_harvest_saved, sender=HoneyHarvest,
                                  dispatch_uid='boxgram_honey_harvest')
                logger.info('Boxgram signal: HoneyHarvest connected')
            except LookupError:
                pass

            try:
                HiveInspection = apps.get_model('livestock', 'HiveInspection')
                post_save.connect(on_hive_inspection_saved, sender=HiveInspection,
                                  dispatch_uid='boxgram_hive_inspection')
            except LookupError:
                pass

            try:
                EPPDojava = apps.get_model('livestock', 'EPPDojava')
                post_save.connect(on_epp_dojava_saved, sender=EPPDojava,
                                  dispatch_uid='boxgram_epp_dojava')
            except LookupError:
                pass

            try:
                Animal = apps.get_model('livestock', 'Animal')
                post_save.connect(on_animal_saved, sender=Animal,
                                  dispatch_uid='boxgram_animal')
            except LookupError:
                pass

        if apps.is_installed('invoicing'):
            try:
                Invoice = apps.get_model('invoicing', 'Invoice')
                post_save.connect(on_invoice_saved, sender=Invoice,
                                  dispatch_uid='boxgram_invoice')
            except LookupError:
                pass

        logger.info('Boxgram: svi signali registrirani')
    except Exception as e:
        logger.error(f'Boxgram connect_signals error: {e}')


# ══════════════════════════════════════════════════════
# AI ENRICHMENT — Haiku auto-opisi
# ══════════════════════════════════════════════════════

def auto_enrich_life_event(sender, instance, created, **kwargs):
    """
    AI Faza 1: Auto-enrich LifeEvent ako je kreirano bez opisa.
    Poziva enrich_life_event_ai task s countdown=2 sekunde.
    """
    if not created:
        return  # Samo za nove događaje

    if instance.description and instance.description.strip():
        return  # Ako već ima opisa, ne radim ništa

    try:
        from .tasks import enrich_life_event_ai

        enrich_life_event_ai.apply_async(
            args=[str(instance.id)],
            countdown=2  # Delayed start za 2 sekunde
        )
        logger.info(f'auto_enrich_life_event: Zakazan task za event {instance.id}')
    except Exception as e:
        logger.error(f'auto_enrich_life_event: {str(e)}')


# ══════════════════════════════════════════════════════
# REGISTRACIJA SIGNALA — AŽURIRANA
# ══════════════════════════════════════════════════════

def connect_signals():
    """
    Poziva se iz BoxgramConfig.ready().
    Koristi string-based sender za lazy import — izbjegava circular imports.
    """
    try:
        from django.apps import apps

        # AI Enrichment — LifeEvent signal
        try:
            LifeEvent = apps.get_model('boxgram', 'LifeEvent')
            post_save.connect(auto_enrich_life_event, sender=LifeEvent,
                              dispatch_uid='boxgram_auto_enrich_life_event')
            logger.info('Boxgram signal: LifeEvent AI enrichment connected')
        except LookupError:
            pass

        if apps.is_installed('livestock'):
            try:
                HoneyHarvest = apps.get_model('livestock', 'HoneyHarvest')
                post_save.connect(on_honey_harvest_saved, sender=HoneyHarvest,
                                  dispatch_uid='boxgram_honey_harvest')
                logger.info('Boxgram signal: HoneyHarvest connected')
            except LookupError:
                pass

            try:
                HiveInspection = apps.get_model('livestock', 'HiveInspection')
                post_save.connect(on_hive_inspection_saved, sender=HiveInspection,
                                  dispatch_uid='boxgram_hive_inspection')
            except LookupError:
                pass

            try:
                EPPDojava = apps.get_model('livestock', 'EPPDojava')
                post_save.connect(on_epp_dojava_saved, sender=EPPDojava,
                                  dispatch_uid='boxgram_epp_dojava')
            except LookupError:
                pass

            try:
                Animal = apps.get_model('livestock', 'Animal')
                post_save.connect(on_animal_saved, sender=Animal,
                                  dispatch_uid='boxgram_animal')
            except LookupError:
                pass

        if apps.is_installed('invoicing'):
            try:
                Invoice = apps.get_model('invoicing', 'Invoice')
                post_save.connect(on_invoice_saved, sender=Invoice,
                                  dispatch_uid='boxgram_invoice')
            except LookupError:
                pass

        # memio_pet bridge
        if apps.is_installed('memio_pet'):
            try:
                AnimalProfile = apps.get_model('memio_pet', 'AnimalProfile')
                post_save.connect(on_animal_profile_saved, sender=AnimalProfile,
                                  dispatch_uid='boxgram_animal_profile_bridge')
                logger.info('Boxgram signal: memio_pet AnimalProfile bridge connected')
            except LookupError:
                pass
            try:
                PetHealthRecord = apps.get_model('memio_pet', 'PetHealthRecord')
                post_save.connect(on_health_record_saved, sender=PetHealthRecord,
                                  dispatch_uid='boxgram_health_record_bridge')
                logger.info('Boxgram signal: memio_pet PetHealthRecord bridge connected')
            except LookupError:
                pass

        logger.info('Boxgram: svi signali registrirani')
    except Exception as e:
        logger.error(f'Boxgram connect_signals error: {e}')


# ══════════════════════════════════════════════════════
# MEMIO.PET BRIDGE — AnimalProfile + PetHealthRecord → Boxgram
# ══════════════════════════════════════════════════════

def on_animal_profile_saved(sender, instance, created, **kwargs):
    """memio_pet.AnimalProfile → boxgram.PetProfile auto-sync."""
    try:
        from boxgram.services.memio_bridge import sync_animal_to_boxgram
        sync_animal_to_boxgram(instance)
    except Exception as e:
        logger.warning(f'Boxgram bridge skip (AnimalProfile {getattr(instance, "pk", "?")}): {e}')


def on_health_record_saved(sender, instance, created, **kwargs):
    """memio_pet.PetHealthRecord → boxgram.LifeEvent auto-sync."""
    if not created:
        return
    try:
        from boxgram.services.memio_bridge import sync_health_record_to_boxgram
        sync_health_record_to_boxgram(instance)
    except Exception as e:
        logger.warning(f'Boxgram bridge skip (PetHealthRecord {getattr(instance, "pk", "?")}): {e}')
