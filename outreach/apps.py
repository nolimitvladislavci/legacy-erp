from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class OutreachConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'outreach'
    verbose_name = 'Outreach / CRM'
