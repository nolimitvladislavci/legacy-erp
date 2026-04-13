from django.apps import AppConfig


class TrackingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tracking'
    verbose_name = 'Tracking'

    def ready(self):
        import tracking.signals  # noqa
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
