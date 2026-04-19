from django.urls import path

from . import views

app_name = "evalidator"

urlpatterns = [
    path("", views.ValidationDashboardView.as_view(), name="dashboard"),
    path("api/", views.ValidateAPIView.as_view(), name="api_validate"),
    path("cert/<uuid:token>/", views.CertificatePublicView.as_view(), name="cert_public"),
    # ChainBlock POE — javna verifikacija (bez auth)
    path("verify/<str:seal_token>/", views.ChainBlockVerifyView.as_view(), name="chain_verify"),
    path("verify/<str:seal_token>/download/", views.ChainBlockDownloadView.as_view(), name="chain_download"),
]
