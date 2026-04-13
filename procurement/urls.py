from django.urls import path

from . import views

app_name = 'procurement'
urlpatterns = [
    path('', views.po_list, name='list'),
    path('new/', views.po_create, name='create'),
    path('dashboard/', views.procurement_dashboard, name='dashboard'),
    path('price-lists/', views.price_list, name='price_lists'),
    path('<int:pk>/', views.po_detail, name='detail'),
    path('<int:pk>/edit/', views.po_edit, name='edit'),
    path('<int:pk>/send/', views.po_send, name='send'),
    path('<int:pk>/receive/', views.po_receive, name='receive'),
    path('<int:pk>/cancel/', views.po_cancel, name='cancel'),
    path('<int:pk>/match/', views.po_match, name='match'),
    path('<int:pk>/approve-match/', views.po_approve_match, name='approve_match'),
]
