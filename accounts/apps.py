from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Accounts'

    def ready(self):
        import accounts.signals  # noqa: F401
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
