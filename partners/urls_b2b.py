from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .b2b_views import b2b_dashboard, b2b_invoices, b2b_invoice_detail, b2b_invoice_action, b2b_invoice_pdf

urlpatterns = [
    path('', b2b_dashboard, name='b2b_dashboard'),
    path('invoices/', b2b_invoices, name='b2b_invoices'),
    path('invoice/<int:pk>/', b2b_invoice_detail, name='b2b_invoice_detail'),
    path('invoice/<int:pk>/action/', b2b_invoice_action, name='b2b_invoice_action'),
    path('invoice/<int:pk>/pdf/', b2b_invoice_pdf, name='b2b_invoice_pdf'),
]
