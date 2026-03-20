from django.apps import AppConfig


class PropterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "propter"
    verbose_name = "Propter Hub"

    def ready(self):
        import propter.signals  # noqa
