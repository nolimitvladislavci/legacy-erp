from django.apps import AppConfig


class EracunConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'eracun'
    verbose_name = 'e-Racuni'

    def ready(self):
        import eracun.signals  # noqa: F401
