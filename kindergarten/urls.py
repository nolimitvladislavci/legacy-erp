from django.urls import path

from . import views

app_name = "kindergarten"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("djeca/", views.child_list, name="child_list"),
    path("djeca/novi/", views.child_create, name="child_create"),
    path("djeca/<int:pk>/", views.child_detail, name="child_detail"),
    path("grupe/", views.group_list, name="group_list"),
    path("dolasci/", views.attendance_daily, name="attendance_daily"),
    path("dolasci/spremi/", views.attendance_save, name="attendance_save"),
    path("naplata/", views.billing_list, name="billing_list"),
    path("naplata/generiraj/", views.billing_generate, name="billing_generate"),
    path("obavijest/nova/", views.announcement_create, name="announcement_create"),
    path("izvjestaj/novi/", views.daily_report_create, name="daily_report_create"),
    path("import/", views.bulk_import_children, name="bulk_import"),
    path("preporuci-kud/", views.preporuci_u_kud, name="preporuci_kud"),
]
