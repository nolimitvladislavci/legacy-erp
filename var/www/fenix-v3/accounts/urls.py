from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("accounts/login/", views.LoginView.as_view(), name="login"),
    path("accounts/logout/", views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("accounts/switch-company/", views.CompanySwitchView.as_view(), name="switch_company"),
]
