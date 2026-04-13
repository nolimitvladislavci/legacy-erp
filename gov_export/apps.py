from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

class GovExportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gov_export'
    verbose_name = 'GovExport — Državni export pipeline'
