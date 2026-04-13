from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class BorgOpsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'borg_ops'
    verbose_name = 'BORG Operations'
