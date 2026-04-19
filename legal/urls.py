"""Fenix V3 — Legal URLs | Blok 7"""

from django.urls import path

from . import views

app_name = "legal"

urlpatterns = [
    # Ugovori
    path("ugovori/", views.ContractListView.as_view(), name="contract_list"),
    path("ugovori/novi/", views.ContractCreateView.as_view(), name="contract_create"),
    path("ugovori/<uuid:pk>/", views.ContractDetailView.as_view(), name="contract_detail"),
    path("ugovori/<uuid:pk>/potpiši/", views.ContractSignView.as_view(), name="contract_sign"),
    path("predlosci/<uuid:pk>/ai-generiraj/", views.ContractAIGenerateView.as_view(), name="contract_ai"),
    # Punomoći
    path("punomoći/", views.POAListView.as_view(), name="poa_list"),
    path("punomoći/nova/", views.POACreateView.as_view(), name="poa_create"),
    # Sporovi
    path("sporovi/", views.DisputeListView.as_view(), name="dispute_list"),
    path("sporovi/novi/", views.DisputeCreateView.as_view(), name="dispute_create"),
    path("sporovi/<uuid:pk>/", views.DisputeDetailView.as_view(), name="dispute_detail"),
]
