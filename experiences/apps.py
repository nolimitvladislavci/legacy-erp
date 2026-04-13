from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class ExperiencesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'experiences'
    verbose_name = 'Agro-Turizam 360'
