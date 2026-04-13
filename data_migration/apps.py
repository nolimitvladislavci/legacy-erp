from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class DataMigrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "data_migration"
    verbose_name = "Migracija podataka"
