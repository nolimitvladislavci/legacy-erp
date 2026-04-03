from django.urls import path
from . import views

app_name = 'notariat'

urlpatterns = [
    path('pravnik/', views.pravnik_dashboard, name='pravnik_dashboard'),
    path('dimnjacari/', views.dimnjacari_dashboard, name='dimnjacari_dashboard'),
]
