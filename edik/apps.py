from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
class EdikConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'edik'
    verbose_name = 'EDIK - e-Porezna'
