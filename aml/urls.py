from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import views

app_name = 'aml'

urlpatterns = [
    path('', views.aml_dashboard, name='dashboard'),
    path('profile/<int:pk>/', views.aml_profile_detail, name='detail'),
    path('profile/new/', views.aml_profile_create, name='create'),
    path('transaction/report/', views.aml_transaction_report, name='report_transaction'),
]
