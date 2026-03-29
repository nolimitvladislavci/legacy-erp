from django.urls import path
from . import views

app_name = 'knjiznica'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Katalog
    path('katalog/', views.catalog_list, name='catalog_list'),
    path('katalog/<int:pk>/', views.catalog_detail, name='catalog_detail'),
    path('katalog/nova-knjiga/', views.catalog_create, name='catalog_create'),

    # Članovi
    path('clanovi/', views.member_list, name='member_list'),
    path('clanovi/novi/', views.member_create, name='member_create'),
    path('clanovi/<int:pk>/', views.member_detail, name='member_detail'),

    # Posudba
    path('posudba/nova/', views.loan_create, name='loan_create'),
    path('posudba/<int:pk>/vrati/', views.loan_return, name='loan_return'),

    # Rezervacija
    path('rezervacija/nova/', views.reservation_create, name='reservation_create'),

    # Statistika
    path('statistika/', views.statistics, name='statistics'),
    path('statistika/nsk-export/', views.nsk_export, name='nsk_export'),
]
