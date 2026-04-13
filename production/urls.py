from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views

app_name = 'production'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # BOM (sastavnice)
    path('bom/', views.bom_list, name='bom_list'),
    path('bom/nova/', views.bom_create, name='bom_create'),
    path('bom/<uuid:pk>/', views.bom_detail, name='bom_detail'),
    path('bom/<uuid:pk>/uredi/', views.bom_create, name='bom_edit'),

    # Production Orders (radni nalozi)
    path('nalozi/', views.order_list, name='order_list'),
    path('nalozi/novi/', views.order_create, name='order_create'),
    path('nalozi/<uuid:pk>/', views.order_detail, name='order_detail'),
    path('nalozi/<uuid:pk>/uredi/', views.order_create, name='order_edit'),
    path('nalozi/<uuid:pk>/akcija/<str:action>/', views.order_action, name='order_action'),
    path('nalozi/<uuid:pk>/proizvedi/', views.order_produce, name='order_produce'),
    path('nalozi/<uuid:pk>/pdf/', views.order_pdf, name='order_pdf'),

    # Steps (koraci)
    path('korak/<uuid:pk>/azuriraj/', views.step_update, name='step_update'),

    # Quality Checks (kontrola kvalitete)
    path('nalozi/<uuid:order_pk>/qc/', views.qc_create, name='qc_create'),

    # Workstations (radne stanice)
    path('stanice/', views.workstation_list, name='workstation_list'),
    path('stanice/nova/', views.workstation_create, name='workstation_create'),
    path('stanice/<uuid:pk>/uredi/', views.workstation_create, name='workstation_edit'),

    # MRP
    path('mrp/', views.mrp_dashboard, name='mrp_dashboard'),
    path('mrp/pokreni/', views.mrp_run_view, name='mrp_run'),
    path('varijance/', views.variance_report, name='variance_report'),
    path('kretanja/', views.stock_movements, name='stock_movements'),

    # API
    path('api/dostupnost/', views.api_availability, name='api_availability'),
]
