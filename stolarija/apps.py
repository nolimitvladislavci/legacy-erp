from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class StolarijaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'stolarija'
    verbose_name = 'Stolarija'
