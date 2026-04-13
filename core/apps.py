from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"

    def ready(self):
        from core.audit import connect_audit_signals

        connect_audit_signals()

        # Register DejaVu Sans fonts for Croatian character support in PDFs
        from core.pdf_fonts import register_pdf_fonts

        register_pdf_fonts()
        # Onboarding auto-completion signals
        import core.onboarding_signals  # noqa: F401

        # Global Validation Engine — OIB/IBAN/MBS validation on ALL models
        from core.validation_engine import activate

        activate()
