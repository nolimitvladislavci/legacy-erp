from django.urls import path
from . import views

app_name = 'seasonal'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('radnici/', views.worker_list, name='worker_list'),
    path('radnici/novi/', views.worker_create, name='worker_create'),
    path('radnici/<int:pk>/', views.worker_detail, name='worker_detail'),
    path('radnici/<int:worker_pk>/ugovor/', views.contract_create, name='contract_create'),
    path('ugovori/<int:pk>/', views.contract_detail, name='contract_detail'),
    path('ugovori/<int:pk>/aktiviraj/', views.contract_activate, name='contract_activate'),
    path('ugovori/<int:pk>/zavrsi/', views.contract_complete, name='contract_complete'),
    path('ugovori/<int:contract_pk>/isplata/', views.payment_create, name='payment_create'),
    path('isplate/<int:pk>/odobri/', views.payment_approve, name='payment_approve'),
    path('ugovori/<int:contract_pk>/hzmo/<str:action>/', views.hzmo_mark_sent, name='hzmo_mark'),
    path('izvjestaj/', views.cost_report, name='cost_report'),
]
