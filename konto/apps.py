from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class KontoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "konto"
    verbose_name = _("Knjigovodstvo")

    def ready(self):
        import konto.integrity  # noqa: F401
        import konto.signals  # noqa: F401
