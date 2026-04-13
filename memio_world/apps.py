from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class MemioWorldConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'memio_world'
    verbose_name = 'Memio World — Digitalna baština'
