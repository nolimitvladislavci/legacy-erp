from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_dashboard, name="dashboard"),
    path("revenue/", views.revenue_report, name="revenue"),
    path("worktime/", views.worktime_report, name="worktime"),
    path("export/revenue/csv/", views.export_revenue_csv, name="export_revenue_csv"),
    path("export/revenue/excel/", views.export_revenue_excel, name="export_revenue_excel"),
    path("export/worktime/csv/", views.export_worktime_csv, name="export_worktime_csv"),
    path("export/worktime/excel/", views.export_worktime_excel, name="export_worktime_excel"),
]
