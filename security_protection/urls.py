from django.urls import path
from . import views

urlpatterns = [
    path("log/", views.security_log, name="security_log"),
]
