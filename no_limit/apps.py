from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class NoLimitConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'no_limit'
