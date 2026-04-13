from django.urls import path

from . import views

app_name = 'honorari'

urlpatterns = [
    path('', views.contract_list, name='contract_list'),
    path('novi/', views.contract_create, name='contract_create'),
    path('<int:pk>/', views.contract_detail, name='contract_detail'),
    path('<int:pk>/edit/', views.contract_edit, name='contract_edit'),
    path('<int:pk>/obracun/', views.calculation_create, name='calculation_create'),
    path('obracun/<int:calc_id>/proknizi/', views.calculation_post, name='calculation_post'),
    path('joppd/', views.joppd_preview, name='joppd_preview'),
]
