from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # Katalog
    path("knjige/", views.book_list, name="book_list"),
    path("knjige/nova/", views.book_create, name="book_create"),
    path("knjige/<int:pk>/", views.book_detail, name="book_detail"),

    # ISBN Lookup (AJAX)
    path("api/isbn/", views.isbn_lookup, name="isbn_lookup"),

    # Posudba / Vracanje
    path("posudba/", views.loan_checkout, name="loan_checkout"),
    path("vracanje/", views.loan_return, name="loan_return"),
    path("produljenje/<int:pk>/", views.loan_renew, name="loan_renew"),

    # Clanovi
    path("clanovi/", views.member_list, name="member_list"),
    path("clanovi/novi/", views.member_create, name="member_create"),
    path("clanovi/<int:pk>/", views.member_detail, name="member_detail"),
    path("clanovi/<int:pk>/qr/", views.member_qr, name="member_qr"),

    # QR Scan (AJAX)
    path("api/qr-scan/", views.qr_scan_member, name="qr_scan_member"),

    # Kasnjenja
    path("kasnjenja/", views.overdue_list, name="overdue_list"),

    # Statistika
    path("statistika/", views.statistics, name="statistics"),
]

    # Agregator izvora
from .sources import import_from_source, search_gutenberg, search_openlibrary, source_hub

urlpatterns += [
    path('izvori/', source_hub, name='source_hub'),
    path('api/gutenberg/', search_gutenberg, name='search_gutenberg'),
    path('api/openlibrary/', search_openlibrary, name='search_openlibrary'),
    path('api/import-source/', import_from_source, name='import_from_source'),
]
