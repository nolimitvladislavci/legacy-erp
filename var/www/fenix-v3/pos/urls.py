from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    # Main terminal view
    path('', views.pos_joker, name='pos_joker'),
    path('<slug:terminal_slug>/', views.pos_joker, name='pos_joker_slug'),

    # Session
    path('api/login/', views.api_login, name='api_login'),
    path('api/session/close/', views.api_session_close, name='api_session_close'),
    path('api/report/', views.api_report, name='api_report'),

    # Cashier
    path('api/cashier/verify/', views.api_cashier_verify, name='api_cashier_verify'),

    # Receipt
    path('api/receipt/add/', views.api_receipt_add, name='api_receipt_add'),
    path('api/receipt/remove/', views.api_receipt_remove, name='api_receipt_remove'),
    path('api/pay/', views.api_pay, name='api_pay'),

    # Gastro tables
    path('api/table/<int:table_id>/open/', views.api_table_open, name='api_table_open'),

    # Barcode / search
    path('api/barcode/', views.api_barcode, name='api_barcode'),
]
