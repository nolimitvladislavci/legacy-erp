from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import views

app_name = 'virtual_office'

urlpatterns = [
    path('', views.virtual_office_dashboard, name='dashboard'),
    path('mail/<int:pk>/', views.mail_detail, name='detail'),
    path('mail/new/', views.mail_create, name='create'),
    path('mail/<int:pk>/upload/', views.mail_upload_scan, name='upload_scan'),
    path('mail/<int:pk>/archive/', views.mail_archive, name='archive'),
]
