from django.urls import path
from no_limit import views

app_name = "no_limit"

urlpatterns = [
    path("preuzmi-vodic/", views.preuzmi_vodic, name="preuzmi_vodic"),
    path("vodic/", views.vodic_online, name="vodic_online"),
    path("azili/prijava/", views.prijava_azila, name="prijava_azila"),
]
