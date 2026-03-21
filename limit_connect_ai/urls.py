from django.urls import path
from . import views

app_name = "limit_connect_ai"

urlpatterns = [
    path("cockpit/", views.ai_cockpit, name="ai_cockpit"),
    path("missions/", views.ai_missions, name="ai_missions"),
    path("reports/", views.ai_reports, name="ai_reports"),
    path("funds/", views.ai_funds, name="ai_funds"),
]
