from django.urls import path

from website import views

urlpatterns = [
    path('<slug:slug>/', views.company_site, name='company_site'),
    path('<slug:slug>/contact/', views.company_site_contact, name='company_site_contact'),
]
