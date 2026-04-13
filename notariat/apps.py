from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class NotariatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notariat'
    verbose_name = 'Notariat i pravne usluge'
