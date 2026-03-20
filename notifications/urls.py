from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('api/', views.notification_api, name='api'),
    path('<int:pk>/read/', views.notification_mark_read, name='mark_read'),
    path('read-all/', views.notification_mark_all_read, name='mark_all_read'),
]
