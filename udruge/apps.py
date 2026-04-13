from django.apps import AppConfig


class UdrugeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'udruge'
    verbose_name = 'Udruge'

    def ready(self):
        from django.db.models.signals import post_save
        from companies.models import Company

        def auto_setup_nonprofit(sender, instance, created, **kwargs):
            if instance.is_nonprofit:
                try:
                    from konto.nonprofit_setup import setup_nonprofit_accounts
                    setup_nonprofit_accounts(instance)
                except ImportError:
                    pass  # Konto app might not be ready yet

        post_save.connect(auto_setup_nonprofit, sender=Company,
                         dispatch_uid='udruge_auto_nonprofit_setup')

        import udruge.signals  # noqa: F401 — KnjigaPrimitaka + Donacija archival
