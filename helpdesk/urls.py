from django.urls import path

from . import views

app_name = 'helpdesk'
urlpatterns = [
    path('', views.ticket_list, name='list'),
    path('dashboard/', views.helpdesk_dashboard, name='dashboard'),
    path('new/', views.ticket_create, name='create'),
    path('<int:pk>/', views.ticket_detail, name='detail'),
    path('<int:pk>/reply/', views.ticket_reply, name='reply'),
    path('<int:pk>/assign/', views.ticket_assign, name='assign'),
    path('<int:pk>/status/', views.ticket_status, name='status'),
    path('<int:pk>/close/', views.ticket_close, name='close'),
    path('vip/', views.vip_list, name='vip_list'),
]
