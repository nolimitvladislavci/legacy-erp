from django.urls import path

from . import views

app_name = "lovacki"

urlpatterns = [
    path("", views.hunting_dashboard, name="dashboard"),
    path("novi/", views.hunt_record_create, name="record_create"),
]
