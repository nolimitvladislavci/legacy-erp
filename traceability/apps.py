from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class TraceabilityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'traceability'
    verbose_name = 'Sljedivost'
