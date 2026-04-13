from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class SuperadminAiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'superadmin_ai'
    verbose_name = 'AI Upravljanje'
