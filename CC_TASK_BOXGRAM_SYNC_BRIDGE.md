# CC_TASK_BOXGRAM_SYNC_BRIDGE.md
# LIMIT Connect → Boxgram — Automatski sync
# Agent: CC Code | Prioritet: VISOK | Datum: 05.04.2026.

## SVRHA
Pero Lapis (pčelar) i Ljubeta (uzgajivač pasa) koriste LIMIT Connect za poslovnu
evidenciju. Sve što unesu tamo — automatski se pojavljuje kao LifeEvent na Boxgram
profilu njihovog ljubimca/pčelinjaka na memio.pet.

Jedan login. Jedna evidencija. Dva lica (back-office + javno).

## PRAVILO
Korisnik ne smije znati da postoje dva sustava.

---

## B1 — company FK na PetProfile

U boxgram/models.py, dodaj FK na Company:

```python
from companies.models import Company

class PetProfile(models.Model):
    # ... postojeća polja ...
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pet_profiles',
        verbose_name='LIMIT Connect firma'
    )
    limit_connect_ref = models.CharField(
        max_length=100, blank=True,
        verbose_name='Referenca u LIMIT Connect',
        help_text='npr. apiary:uuid ili livestock:uuid'
    )
```

Migracija:
```bash
python manage.py makemigrations boxgram --name="add_company_fk_to_petprofile"
python manage.py migrate
```

---

## B2 — Django Signals (boxgram/signals.py)

Novi fajl: `/var/www/fina-connect/boxgram/signals.py`

```python
"""
Boxgram Sync Bridge — automatski kreira LifeEvent iz LIMIT Connect akcija.
Signal → PetProfile (ako postoji za tu company) → LifeEvent

Logika: "inform aggressively, execute conservatively"
- Signal uvijek pali
- Ako nema PetProfile za company → tiho preskače
- Nikad ne blokira original save()
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# PČELARSTVO — HoneyHarvest → LifeEvent
# ══════════════════════════════════════════════════════════════════

@receiver(post_save, sender='livestock.HoneyHarvest')
def sync_honey_harvest_to_boxgram(sender, instance, created, **kwargs):
    """Berba meda → objava na pčelinjak profilu."""
    if not created:
        return
    try:
        from boxgram.models import PetProfile, LifeEvent
        pets = PetProfile.objects.filter(
            company=instance.apiary.company,
            species='pcela'
        )
        for pet in pets:
            LifeEvent.objects.get_or_create(
                pet=pet,
                source='manual',
                source_id=f'honey_{instance.pk}',
                defaults={
                    'event_type': 'milestone',
                    'title': f'Berba meda — {instance.get_vrsta_display()}',
                    'description': (
                        f'{instance.kolicina_kg} kg {instance.get_vrsta_display().lower()} '
                        f'ubrano s pčelinjaka {instance.apiary.naziv}.'
                    ),
                    'date': instance.datum,
                    'location': instance.apiary.adresa,
                    'location_city': instance.apiary.katastarska_opcina,
                    'is_public': True,
                }
            )
            logger.info(f'Boxgram sync: HoneyHarvest {instance.pk} → PetProfile {pet.id}')
    except Exception as e:
        logger.warning(f'Boxgram sync skip (HoneyHarvest {instance.pk}): {e}')


@receiver(post_save, sender='livestock.HiveInspection')
def sync_hive_inspection_to_boxgram(sender, instance, created, **kwargs):
    """Pregled košnice → vet posjet event (samo ako je nađena varroa ili tretman)."""
    if not created:
        return
    # Samo značajni pregledi idu u javni feed
    if not instance.tretman_varroa and not instance.varroa_posip:
        return
    try:
        from boxgram.models import PetProfile, LifeEvent
        pets = PetProfile.objects.filter(
            company=instance.hive.apiary.company,
            species='pcela'
        )
        for pet in pets:
            LifeEvent.objects.get_or_create(
                pet=pet,
                source='manual',
                source_id=f'inspect_{instance.pk}',
                defaults={
                    'event_type': 'vet',
                    'title': f'Pregled i tretman — {instance.hive.oznaka}',
                    'description': (
                        f'Pregled košnice {instance.hive.oznaka}. '
                        f'Tretman: {instance.tretman_varroa}. '
                        f'Snaga zajednice: {instance.snaga_zajednice}/5.'
                    ),
                    'date': instance.datum,
                    'is_public': False,  # Vet info — privatno
                }
            )
    except Exception as e:
        logger.warning(f'Boxgram sync skip (HiveInspection {instance.pk}): {e}')


@receiver(post_save, sender='livestock.EPPDojava')
def sync_epp_to_boxgram(sender, instance, created, **kwargs):
    """EPP Prilog 3 predano → milestone na profilu."""
    if not instance.predano:
        return
    try:
        from boxgram.models import PetProfile, LifeEvent
        pets = PetProfile.objects.filter(
            company=instance.company,
            species='pcela'
        )
        for pet in pets:
            LifeEvent.objects.get_or_create(
                pet=pet,
                source='manual',
                source_id=f'epp_{instance.pk}',
                defaults={
                    'event_type': 'nagrada',
                    'title': f'EPP dojava {instance.godina}. predana',
                    'description': (
                        f'Godišnja dojava broja pčelinjih zajednica za {instance.godina}. '
                        f'Ukupno {instance.ukupno_zajednica} zajednica u evidenciji.'
                    ),
                    'date': instance.predano_datum or instance.datum_dojave,
                    'is_public': True,
                }
            )
    except Exception as e:
        logger.warning(f'Boxgram sync skip (EPPDojava {instance.pk}): {e}')


# ══════════════════════════════════════════════════════════════════
# UZGAJALIŠTE — Livestock eventi → Boxgram
# ══════════════════════════════════════════════════════════════════

@receiver(post_save, sender='livestock.Animal')
def sync_animal_birth_to_boxgram(sender, instance, created, **kwargs):
    """Novo mladunče → LifeEvent rodenje na profilu roditelja."""
    if not created:
        return
    try:
        from boxgram.models import PetProfile, LifeEvent

        # Mapiraj vrstu životinje na boxgram species
        SPECIES_MAP = {
            'pas': 'pas', 'macka': 'macka', 'konj': 'konj',
            'govedo': 'govedo', 'svinja': 'svinja', 'ovca': 'ovca',
            'koza': 'koza',
        }
        species = SPECIES_MAP.get(getattr(instance, 'vrsta', ''), 'ostalo')

        # Kreiraj PetProfile za novo mladunče ako ne postoji
        if instance.company:
            pet, created_pet = PetProfile.objects.get_or_create(
                limit_connect_ref=f'livestock:{instance.pk}',
                defaults={
                    'tenant': instance.company.tenant_set.first(),
                    'company': instance.company,
                    'name': getattr(instance, 'ime', f'Mladunče {instance.pk}'),
                    'species': species,
                    'breed': getattr(instance, 'pasmina', ''),
                    'birth_date': getattr(instance, 'datum_rodenja', None),
                    'slug': f'{species}-{instance.pk}',
                    'is_public': True,
                }
            )
            if created_pet:
                LifeEvent.objects.create(
                    pet=pet,
                    event_type='rodenje',
                    title=f'{pet.name} je na svijetu!',
                    description=f'Novo mladunče registrirano u uzgajalištu.',
                    date=pet.birth_date or __import__('django.utils.timezone', fromlist=['now']).now().date(),
                    source='manual',
                    is_public=True,
                )
                logger.info(f'Boxgram: Auto-kreiran PetProfile za {pet.name}')
    except Exception as e:
        logger.warning(f'Boxgram sync skip (Animal {instance.pk}): {e}')


# ══════════════════════════════════════════════════════════════════
# INVOICING — R1 račun za med → link na HoneyHarvest event
# ══════════════════════════════════════════════════════════════════

@receiver(post_save, sender='invoicing.Invoice')
def sync_invoice_to_boxgram(sender, instance, created, **kwargs):
    """Ako je R1 račun vezan na HoneyHarvest → ažuriraj LifeEvent."""
    if not created:
        return
    try:
        from livestock.models import HoneyHarvest
        from boxgram.models import LifeEvent

        harvests = HoneyHarvest.objects.filter(invoice=instance)
        for harvest in harvests:
            LifeEvent.objects.filter(
                source_id=f'honey_{harvest.pk}'
            ).update(
                is_verified=True,
                description=LifeEvent.objects.filter(
                    source_id=f'honey_{harvest.pk}'
                ).values_list('description', flat=True).first() or '' +
                f' R1 račun: {instance.number}.'
            )
    except Exception as e:
        logger.warning(f'Boxgram sync skip (Invoice {instance.pk}): {e}')
```

---

## B3 — Registracija signala (boxgram/apps.py)

```python
from django.apps import AppConfig

class BoxgramConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'boxgram'
    verbose_name = 'Boxgram — Digitalni život ljubimca'

    def ready(self):
        import boxgram.signals  # noqa — registrira sve signale
```

---

## B4 — Management command: boxgram_link

Za ručno linkanje postojećih firmi s Boxgram profilima:

```python
# boxgram/management/commands/boxgram_link.py
from django.core.management.base import BaseCommand
from companies.models import Company
from boxgram.models import PetProfile

class Command(BaseCommand):
    help = 'Linkaj LIMIT Connect firmu s Boxgram PetProfile-om'

    def add_arguments(self, parser):
        parser.add_argument('--company-oib', type=str, required=True)
        parser.add_argument('--pet-slug', type=str, required=True)

    def handle(self, *args, **options):
        try:
            company = Company.objects.get(oib=options['company_oib'])
            pet = PetProfile.objects.get(slug=options['pet_slug'])
            pet.company = company
            pet.save(update_fields=['company'])
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Linkano: {company.name} → {pet.name} ({pet.slug})'
                )
            )
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Firma s OIB {options["company_oib"]} ne postoji'))
        except PetProfile.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'PetProfile {options["pet_slug"]} ne postoji'))
```

Primjer korištenja:
```bash
# Poveži Pero Lapis OPG s njegovim pčelinjak profilom
python manage.py boxgram_link --company-oib=PERO_OIB --pet-slug=pcelinjak-pero-lapis
```

---

## B5 — Celery task: bulk sync postojećih podataka

Za retroaktivni import svih starih evidencija:

```python
# boxgram/tasks.py — dodaj:
@shared_task(queue='default')
def bulk_sync_company_to_boxgram(company_id):
    """
    Retroaktivni sync svih LIMIT Connect podataka na Boxgram.
    Pokreće se jednom po linkanju nove firme.
    """
    try:
        from companies.models import Company
        company = Company.objects.get(pk=company_id)

        synced = 0

        # HoneyHarvest
        try:
            from livestock.models import HoneyHarvest
            from boxgram.signals import sync_honey_harvest_to_boxgram
            for harvest in HoneyHarvest.objects.filter(apiary__company=company):
                sync_honey_harvest_to_boxgram(
                    sender=HoneyHarvest, instance=harvest, created=True
                )
                synced += 1
        except Exception as e:
            pass

        # EPP dojave
        try:
            from livestock.models import EPPDojava
            from boxgram.signals import sync_epp_to_boxgram
            for epp in EPPDojava.objects.filter(company=company, predano=True):
                sync_epp_to_boxgram(
                    sender=EPPDojava, instance=epp, created=False
                )
                synced += 1
        except Exception as e:
            pass

        return f'Bulk sync za {company.name}: {synced} evenata kreiran/ažuriran'
    except Exception as e:
        return f'Bulk sync FAIL: {e}'
```

---

## B6 — Admin widget: "Boxgram profili" na Company admin stranici

U `companies/admin.py` dodaj inline:

```python
class PetProfileInline(admin.TabularInline):
    model = PetProfile  # iz boxgram.models
    fk_name = 'company'
    extra = 0
    fields = ['name', 'species', 'slug', 'is_public', 'is_memorial']
    readonly_fields = ['slug', 'sha256_seal']
    verbose_name = 'Boxgram profil ljubimca'
    verbose_name_plural = 'Boxgram profili (memio.pet)'
    show_change_link = True

# Na CompanyAdmin dodaj u inlines lista
```

---

## DONE kriterij

- [ ] company + limit_connect_ref polja na PetProfile, migracija aplicirana
- [ ] boxgram/signals.py kreira se bez grešaka (import check)
- [ ] boxgram/apps.py.ready() registrira signale
- [ ] Test: kreiraj HoneyHarvest → LifeEvent se automatski pojavi u boxgram
- [ ] Test: signal tiho preskače ako nema PetProfile za company (ne baca exception)
- [ ] boxgram_link management command radi
- [ ] bulk_sync_company_to_boxgram Celery task radi
- [ ] PetProfileInline vidljiv na Company admin stranici
- [ ] Commit: "feat(boxgram): sync bridge LIMIT Connect → Boxgram signals"

## NAPOMENA ZA PILOTE
Nakon što se modeli i signali deployaju:
```bash
# Pero Lapis
python manage.py boxgram_link --company-oib=PERO_OIB --pet-slug=pcelinjak-pero-lapis

# Ljubeta
python manage.py boxgram_link --company-oib=LJUBETA_OIB --pet-slug=kennel-ljubeta-novaki

# Retroaktivni sync
python manage.py shell -c "
from boxgram.tasks import bulk_sync_company_to_boxgram
bulk_sync_company_to_boxgram.delay('PERO_COMPANY_ID')
bulk_sync_company_to_boxgram.delay('LJUBETA_COMPANY_ID')
"
```
