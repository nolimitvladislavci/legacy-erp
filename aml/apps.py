from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
class AmlConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aml'
    verbose_name = 'AML - Dubinska analiza'
