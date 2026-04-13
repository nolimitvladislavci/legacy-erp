from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class FiskalizacijaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fiskalizacija'
    verbose_name = 'Fiskalizacija (CIS / Porezna uprava)'
