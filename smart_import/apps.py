from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class SmartImportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'smart_import'
    verbose_name = 'Smart Import (AIP)'
