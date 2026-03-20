from django.http import JsonResponse
from django.urls import path

from . import views

app_name = 'premium_booking'


def _api_deprecated(request):
    """Legacy API endpoint — redirects to appointments module."""
    return JsonResponse({
        'status': 'error',
        'code': 410,
        'message': 'Ovaj API je zamijenjen novim sustavom rezervacija. '
                   'Koristite /appointments/api/book/ za nove rezervacije.',
    }, status=410)


urlpatterns = [
    path('', views.index, name='index'),
    path('<int:resource_id>/', views.detail, name='detail'),
    path('api/submit/', _api_deprecated, name='api_submit'),
]
