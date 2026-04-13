from django.apps import AppConfig


class WorktimeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'worktime'
    verbose_name = 'Worktime'

    def ready(self):
        import worktime.signals  # noqa: F401
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
