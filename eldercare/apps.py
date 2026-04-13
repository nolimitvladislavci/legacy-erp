from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class EldercareConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "eldercare"
    verbose_name = "Dom za starije"
