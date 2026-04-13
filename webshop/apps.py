from django.apps import AppConfig


class WebshopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "webshop"

    def ready(self):
        import webshop.signals  # noqa: F401
