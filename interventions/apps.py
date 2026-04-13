from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class InterventionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "interventions"
    verbose_name = "Hitne intervencije"
