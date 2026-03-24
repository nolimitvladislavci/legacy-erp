from django.apps import AppConfig


class EinvoiceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "einvoice"
    verbose_name = "PROPTER e-Invoice (AS4/Peppol)"

    def ready(self):
        import einvoice.signals  # noqa: F401
