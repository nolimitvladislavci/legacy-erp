from django.urls import path

from . import views
from .views_public_docs import (
    public_doc_pdf,
    public_doc_verify,
    public_doc_view,
    public_docs_index,
)

app_name = "notariat"

urlpatterns = [
    path("pravnik/", views.pravnik_dashboard, name="pravnik_dashboard"),
    path("dimnjacari/", views.dimnjacari_dashboard, name="dimnjacari_dashboard"),
    path("dimnjacari/<int:pk>/pdf/", views.potvrda_dimnjaka_pdf, name="potvrda_dimnjaka_pdf"),
    path("pdf/punomoc/", views.punomoc_pdf, name="punomoc_pdf"),
    path("pdf/osnivanje-jdoo/", views.osnivanje_jdoo_pdf, name="osnivanje_jdoo_pdf"),
    path("pdf/kupoprodaja/", views.kupoprodaja_pdf, name="kupoprodaja_pdf"),
    path("pdf/zaduznica/", views.zaduznica_pdf, name="zaduznica_pdf"),
    path("api/tarifa/", views.api_tarifa, name="api_tarifa"),
    # ═══════════════════════════════════════════════════════════════
    #  Javni dokumenti s evalidator pečatom
    # ═══════════════════════════════════════════════════════════════
    path("docs/", public_docs_index, name="public_docs_index"),
    path("docs/<str:doc_id>/", public_doc_view, name="public_doc_view"),
    path("docs/<str:doc_id>/pdf/", public_doc_pdf, name="public_doc_pdf"),
    path("docs/<str:doc_id>/verify/", public_doc_verify, name="public_doc_verify"),
]
