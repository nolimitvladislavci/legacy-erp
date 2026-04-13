from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

class LovackiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lovacki'
    verbose_name = 'Lovački modul'
