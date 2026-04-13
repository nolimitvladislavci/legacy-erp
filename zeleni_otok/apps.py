from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class ZeleniOtokConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'zeleni_otok'
    verbose_name = 'Zeleni Otok — Competitive Intelligence'
