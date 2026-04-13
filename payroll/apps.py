from django.apps import AppConfig

class PayrollConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payroll'
    verbose_name = 'Obračun plaća'

    def ready(self):
        import payroll.signals  # noqa: F401
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
