from django.apps import AppConfig

class UtilitiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'utilities'
    verbose_name = 'Režije i komunalije'

    def ready(self):
        import utilities.signals  # noqa
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
