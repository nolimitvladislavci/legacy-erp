from django.urls import path
from . import views

app_name = "evalidator"

urlpatterns = [
    path("", views.ValidationDashboardView.as_view(), name="dashboard"),
    path("api/", views.ValidateAPIView.as_view(), name="api_validate"),
    path("cert/<uuid:token>/", views.CertificatePublicView.as_view(), name="cert_public"),

    # ChainBlock POE
    path("verify/<str:seal_token>/", views.ChainBlockVerifyView.as_view(), name="chain_verify"),
    path("verify/<str:seal_token>/download/", views.ChainBlockDownloadView.as_view(), name="chain_download"),

    # Defensive Publication — Seal Innovation
    path("dp/", views.DefensivePublicationListView.as_view(), name="dp_list"),
    path("dp/novo/", views.SealInnovationView.as_view(), name="seal_innovation"),
    path("dp/novo/submit/", views.SealInnovationSubmitView.as_view(), name="seal_submit"),
    path("<str:dp_id>/", views.DefensivePublicationDetailView.as_view(), name="dp_detail"),
    path("<str:dp_id>/download/", views.DPDownloadView.as_view(), name="dp_download"),

    # Bunker Integrity
    path("bunker/", views.BunkerStatusView.as_view(), name="bunker"),
]
