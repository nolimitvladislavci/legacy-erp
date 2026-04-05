from django.apps import AppConfig


class BoxgramConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'boxgram'
    verbose_name = 'Boxgram - Pet Social Network'

    def ready(self):
        from .signals import connect_signals
        connect_signals()
