from django.urls import path

from . import views

app_name = 'fiscal'

urlpatterns = [
    path('test/', views.test_connection, name='test_connection'),
    path('status/', views.fiscal_status, name='status'),
]
