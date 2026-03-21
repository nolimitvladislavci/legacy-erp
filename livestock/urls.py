from django.urls import path
from . import views

app_name = 'livestock'

urlpatterns = [
    path('', views.livestock_list, name='list'),
    path('<int:pk>/', views.livestock_detail, name='detail'),
    path('create/', views.livestock_create, name='create'),
    path('fields/', views.field_list, name='field_list'),
    path('crops/', views.crop_list, name='crop_list'),
]
