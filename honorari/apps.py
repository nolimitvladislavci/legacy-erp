from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class HonorariConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'honorari'
    verbose_name = 'Honorari i ugovori o djelu'
