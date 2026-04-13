from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class FenixInputConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fenix_input'
    verbose_name = 'Fenix Input — Univerzalni ulaz'
