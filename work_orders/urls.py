from django.urls import path

from . import views

app_name = 'work_orders'

urlpatterns = [
    # Work Orders
    path('board/',                     views.work_order_board,      name='board'),
    path('',                           views.work_order_list,       name='list'),
    path('new/',                       views.work_order_create,     name='create'),
    path('<int:pk>/',                  views.work_order_detail,     name='detail'),
    path('<int:pk>/edit/',             views.work_order_edit,       name='edit'),
    path('<int:pk>/complete/',         views.work_order_complete,   name='complete'),
    path('<int:pk>/cancel/',           views.work_order_cancel,     name='cancel'),
    path('<int:pk>/to-invoice/',       views.work_order_to_invoice, name='to_invoice'),

    # Vehicle Cards
    path('vehicles/',                  views.vehicle_card_list,     name='vehicle_list'),
    path('vehicles/new/',              views.vehicle_card_create,   name='vehicle_create'),
    path('vehicles/<int:pk>/',         views.vehicle_card_detail,   name='vehicle_detail'),
    path('vehicles/<int:pk>/edit/',    views.vehicle_card_edit,     name='vehicle_edit'),

    # Client Cards
    path('client-cards/',              views.client_card_list,      name='client_card_list'),
    path('client-cards/new/',          views.client_card_create,    name='client_card_create'),
    path('client-cards/<int:pk>/',     views.client_card_detail,    name='client_card_detail'),
    path('client-cards/<int:pk>/edit/', views.client_card_edit,     name='client_card_edit'),
]
