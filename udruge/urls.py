from django.urls import path
from . import views

app_name = 'udruge'

urlpatterns = [
    # Clanovi
    path('', views.clan_list, name='clan_list'),
    path('novi/', views.clan_create, name='clan_create'),
    path('<int:pk>/', views.clan_detail, name='clan_detail'),
    path('<int:pk>/oib-lookup/', views.oib_lookup, name='oib_lookup'),
    path('<int:pk>/ai-analyze/', views.ai_analyze, name='ai_analyze'),
    path('<int:pk>/whatsapp/', views.send_whatsapp, name='send_whatsapp'),

    # Clanarine
    path('clanarine/', views.clanarina_list, name='clanarina_list'),
    path('clanarine/bulk/', views.clanarina_bulk_create, name='clanarina_bulk_create'),
    path('clanarine/<int:pk>/pay/', views.clanarina_pay, name='clanarina_pay'),

    # Donacije
    path('donacije/', views.donacija_list, name='donacija_list'),
    path('donacije/nova/', views.donacija_create, name='donacija_create'),
    path('donacije/<int:pk>/potvrda/', views.download_donatorska_potvrda, name='donatorska_potvrda'),

    # Knjiga primitaka i izdataka
    path('knjiga/', views.knjiga_primitaka, name='knjiga_primitaka'),
    path('knjiga/nova/', views.knjiga_primitaka_create, name='knjiga_primitaka_create'),

    # FINA izvjestaji
    path('izvjestaji/', views.fina_reports, name='fina_reports'),
    path('izvjestaji/pr-ras-npf/', views.download_prras_npf, name='download_prras_npf'),
    path('izvjestaji/bil-npf/', views.download_bil_npf, name='download_bil_npf'),
    path('izvjestaji/g-pr-iz-npf/', views.download_gpriznpf, name='download_gpriznpf'),

    # EU Fondovi / Volonteri
    path('eu/', views.eu_reports, name='eu_reports'),
    path('eu/timesheet/', views.download_volunteer_timesheet, name='volunteer_timesheet'),
    path('eu/inkind/', views.download_inkind_report, name='inkind_report'),
    path('eu/godisnje/', views.download_annual_volunteer_report, name='annual_volunteer_report'),
]
