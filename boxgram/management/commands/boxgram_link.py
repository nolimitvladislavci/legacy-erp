from django.core.management.base import BaseCommand
from boxgram.models import PetProfile
from companies.models import Company
import logging
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Link company OIB to pet slug'

    def add_arguments(self, parser):
        parser.add_argument('company_id', type=str)
        parser.add_argument('pet_slug', type=str)

    def handle(self, *args, **options):
        company_id = options['company_id']
        pet_slug = options['pet_slug']

        try:
            company = Company.objects.get(id=company_id)
            pet = PetProfile.objects.get(slug=pet_slug)
            
            pet.company = company
            pet.limit_connect_ref = company.oib or company.id
            pet.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully linked company {company.name} to pet {pet.name}'
                )
            )
            logger.info(f"Linked company {company_id} to pet {pet_slug}")
        except Company.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Company {company_id} not found')
            )
        except PetProfile.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Pet {pet_slug} not found')
            )
        except ObjectDoesNotExist as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {str(e)}')
            )
