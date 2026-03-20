from django.urls import path
from . import portal_views

urlpatterns = [
    path('', portal_views.portal_home, name='portal_home'),
    path('invoices/', portal_views.portal_invoices, name='portal_invoices'),
    path('invoices/<int:pk>/', portal_views.portal_invoice_detail, name='portal_invoice_detail'),
    path('invoices/<int:pk>/pdf/', portal_views.portal_invoice_pdf, name='portal_invoice_pdf'),
    path('projects/', portal_views.portal_projects, name='portal_projects'),
    path('documents/', portal_views.portal_documents, name='portal_documents'),
]
