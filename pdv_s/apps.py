from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
class PdvSConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pdv_s'
    verbose_name = 'PDV-S Obrazac'
