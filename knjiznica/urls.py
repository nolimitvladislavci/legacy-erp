from django.urls import path

from . import portal_views, views

app_name = "knjiznica"

urlpatterns = [
    # ═══ ADMIN BACKEND (login_required) ═══
    path("", views.dashboard, name="dashboard"),
    # Katalog
    path("katalog/", views.catalog_list, name="catalog_list"),
    path("katalog/<int:pk>/", views.catalog_detail, name="catalog_detail"),
    path("katalog/nova-knjiga/", views.catalog_create, name="catalog_create"),
    # Članovi
    path("clanovi/", views.member_list, name="member_list"),
    path("clanovi/novi/", views.member_create, name="member_create"),
    path("clanovi/<int:pk>/", views.member_detail, name="member_detail"),
    # Posudba
    path("posudba/nova/", views.loan_create, name="loan_create"),
    path("posudba/<int:pk>/vrati/", views.loan_return, name="loan_return"),
    # Rezervacija
    path("rezervacija/nova/", views.reservation_create, name="reservation_create"),
    # Statistika
    path("statistika/", views.statistics, name="statistics"),
    path("statistika/nsk-export/", views.nsk_export, name="nsk_export"),
    # ═══ JAVNI PORTAL (bez django login-a) ═══
    path("portal/<slug:slug>/", portal_views.portal_home, name="portal_home"),
    path("portal/<slug:slug>/katalog/", portal_views.portal_catalog, name="portal_catalog"),
    path("portal/<slug:slug>/knjiga/<int:pk>/", portal_views.portal_book_detail, name="portal_book_detail"),
    path("portal/<slug:slug>/mediji/", portal_views.portal_media, name="portal_media"),
    path("portal/<slug:slug>/mediji/<int:pk>/", portal_views.portal_media_watch, name="portal_media_watch"),
    path("portal/<slug:slug>/bedževi/", portal_views.portal_badges, name="portal_badges"),
    # Portal — PIN login
    path("portal/<slug:slug>/prijava/", portal_views.portal_login, name="portal_login"),
    path("portal/<slug:slug>/odjava/", portal_views.portal_logout, name="portal_logout"),
    # Portal — Obitelj (zahtijeva PIN)
    path("portal/<slug:slug>/obitelj/", portal_views.portal_family, name="portal_family"),
    path("portal/<slug:slug>/dijete/<int:pk>/", portal_views.portal_child_detail, name="portal_child_detail"),
    path("portal/<slug:slug>/zabilježi-čitanje/", portal_views.portal_log_reading, name="portal_log_reading"),
]
