from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class TaxWizardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tax_wizard'
    verbose_name = 'Porezni Savjetnik'
