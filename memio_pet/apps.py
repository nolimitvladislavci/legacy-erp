from django.apps import AppConfig


class MemioPetConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "memio_pet"
    verbose_name = "Memio.pet — Ljubimci"

    def ready(self):
        import memio_pet.signals  # noqa: F401
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
