from django.urls import path
from . import views

app_name = 'notariat'

urlpatterns = [
    path('pravnik/', views.pravnik_dashboard, name='pravnik_dashboard'),
    path('dimnjacari/', views.dimnjacari_dashboard, name='dimnjacari_dashboard'),
    path('dimnjacari/<int:pk>/pdf/', views.potvrda_dimnjaka_pdf, name='potvrda_dimnjaka_pdf'),
    path('pdf/punomoc/', views.punomoc_pdf, name='punomoc_pdf'),
    path('pdf/osnivanje-jdoo/', views.osnivanje_jdoo_pdf, name='osnivanje_jdoo_pdf'),
    path('pdf/kupoprodaja/', views.kupoprodaja_pdf, name='kupoprodaja_pdf'),
    path('pdf/zaduznica/', views.zaduznica_pdf, name='zaduznica_pdf'),
    path('api/tarifa/', views.api_tarifa, name='api_tarifa'),
]
