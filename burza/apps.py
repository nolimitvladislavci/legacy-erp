from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class BurzaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'burza'
    verbose_name = 'Zlatni Kanban – Burza'
