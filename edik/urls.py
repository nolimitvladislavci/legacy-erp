from django.urls import path
from . import views

app_name = 'edik'

urlpatterns = [
    path('', views.edik_dashboard, name='dashboard'),
    path('submission/<int:pk>/', views.edik_submission_detail, name='detail'),
    path('submission/new/', views.edik_submission_create, name='create'),
    path('submission/<int:pk>/status/', views.edik_submission_update_status, name='update_status'),
    path('calendar/', views.edik_calendar, name='calendar'),
    path('calendar/generate/', views.edik_generate_calendar, name='generate_calendar'),
]
