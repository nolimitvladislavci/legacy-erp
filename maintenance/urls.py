from django.urls import path

from . import views

app_name = "maintenance"
urlpatterns = [
    path("", views.maintenance_dashboard, name="dashboard"),
    path("assets/", views.asset_list, name="asset_list"),
    path("assets/new/", views.asset_create, name="asset_create"),
    path("assets/<int:pk>/", views.asset_detail, name="asset_detail"),
    path("assets/<int:pk>/edit/", views.asset_edit, name="asset_edit"),
    path("assets/<int:pk>/log/", views.add_maintenance_log, name="add_log"),
    path("assets/<int:pk>/schedule/", views.add_schedule, name="add_schedule"),
    path("calendar/", views.maintenance_calendar, name="calendar"),
    path("expiring/", views.expiring_list, name="expiring"),
    path("api/alerts/", views.alerts_api, name="alerts_api"),
    path("assets/register/", views.asset_register, name="asset_register"),
    path("assets/depreciation/run/", views.run_depreciation, name="run_depreciation"),
]
