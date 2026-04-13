from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class KomunalnoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'komunalno'
    verbose_name = 'Komunalno'
