from django.apps import AppConfig


class InvoicingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'invoicing'
    verbose_name = 'Invoicing'

    def ready(self):
        import invoicing.signals  # noqa: F401
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
