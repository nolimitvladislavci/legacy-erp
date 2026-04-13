from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class GastroMenuConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gastro_menu'
    verbose_name = 'Digitalni meni'
