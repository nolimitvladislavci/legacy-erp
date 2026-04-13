from django.apps import AppConfig
class HelpdeskConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'helpdesk'
    verbose_name = 'Helpdesk'

    def ready(self):
        import helpdesk.signals
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
