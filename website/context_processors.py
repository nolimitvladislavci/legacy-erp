from .models import SiteSettings


def global_settings(request):
    # Povlači prve postavke koje ste kreirali u adminu
    settings = SiteSettings.objects.first()
    return {'site_settings': settings}
