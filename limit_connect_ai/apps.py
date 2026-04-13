from django.apps import AppConfig


class LimitConnectAiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "limit_connect_ai"
    verbose_name = "LIMIT Connect AI"

    def ready(self):
        import limit_connect_ai.kg_signals  # noqa: F401
