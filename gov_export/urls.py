from django.urls import path
from . import views
from .validator import public_validator

app_name = 'gov_export'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('<uuid:export_id>/run/', views.run_export, name='run'),
    path('<uuid:export_id>/xml/', views.download_xml, name='download_xml'),
    path('<uuid:export_id>/log/', views.export_log, name='log'),
    path('validator/', public_validator, name='validator'),
]
