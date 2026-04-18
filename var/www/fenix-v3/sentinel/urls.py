"""FENIX SENTINEL — URL konfiguracija (PLAN_072–083)"""

from django.urls import path
from . import views

app_name = "sentinel"

urlpatterns = [
    # Dashboard — /hr/sentinel/
    path("", views.dashboard, name="dashboard"),
    # Alerts
    path("alert/<str:alert_id>/resolve/", views.alert_resolve, name="alert_resolve"),
    path("alerts/resolve-all/", views.alerts_resolve_all, name="alerts_resolve_all"),
    # EU Navigator — /hr/sentinel/eu/
    path("eu/", views.eu_navigator, name="eu_navigator"),
    path("eu/match/<str:match_id>/", views.eu_match_detail, name="eu_match_detail"),
    # Obrasci Engine — /hr/sentinel/obrasci/
    path("obrasci/", views.obrasci_lista, name="obrasci_lista"),
    path("obrasci/<str:pk>/", views.obrazac_detail, name="obrazac_detail"),
    path("obrasci/<str:pk>/xml/", views.obrazac_xml_download, name="obrazac_xml"),
    # Digitalni Ured — /hr/sentinel/ured/
    path("ured/", views.digitalni_ured, name="digitalni_ured"),
    path("ured/nova/", views.ured_nova_konverzacija, name="ured_nova_konverzacija"),
    path("ured/<str:conv_id>/", views.digitalni_ured, name="digitalni_ured_conv"),
    path("ured/<str:conv_id>/send/", views.ured_send_message, name="ured_send"),
    # Kalendar obveza
    path("kalendar/", views.kalendar_obveza, name="kalendar_obveza"),
]
