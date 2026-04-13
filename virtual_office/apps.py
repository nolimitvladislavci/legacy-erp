from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
class VirtualOfficeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'virtual_office'
    verbose_name = 'Virtualni ured'
