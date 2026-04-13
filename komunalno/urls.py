from django.urls import path

from . import views

app_name = "komunalno"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    # Kiosk mode (terenska app)
    path("kiosk/<int:station_id>/", views.kiosk_home, name="kiosk_home"),
    path("kiosk/<int:station_id>/scan/", views.kiosk_scan, name="kiosk_scan"),
    path("kiosk/<int:station_id>/citizen/<int:card_id>/", views.kiosk_citizen, name="kiosk_citizen"),
    path("kiosk/<int:station_id>/deliver/", views.kiosk_deliver, name="kiosk_deliver"),
    path("kiosk/<int:station_id>/confirm/<int:delivery_id>/", views.kiosk_confirm, name="kiosk_confirm"),
    path("kiosk/<int:station_id>/receipt/<int:delivery_id>/", views.kiosk_receipt, name="kiosk_receipt"),
    # Scale API
    path("api/scale/<int:station_id>/reading/", views.api_scale_reading, name="api_scale_reading"),
    path("api/scale/<int:station_id>/latest/", views.api_scale_latest, name="api_scale_latest"),
    # Citizen lookup
    path("api/citizen/lookup/", views.api_citizen_lookup, name="api_citizen_lookup"),
    # e-ONTO
    path("onto/", views.onto_dashboard, name="onto_dashboard"),
    path("onto/batch/<int:batch_id>/", views.onto_batch_detail, name="onto_batch_detail"),
    path("onto/export/", views.onto_manual_export, name="onto_manual_export"),
    # Reports
    path("reports/", views.reports, name="reports"),
    path("reports/daily/", views.daily_report, name="daily_report"),
    # Management
    path("stations/", views.station_list, name="station_list"),
    path("citizens/", views.citizen_list, name="citizen_list"),
    path("citizens/<int:card_id>/", views.citizen_detail, name="citizen_detail"),
    path("categories/", views.category_list, name="category_list"),
    path("quotas/", views.quota_management, name="quota_management"),
]
