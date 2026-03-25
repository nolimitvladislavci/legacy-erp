from django.urls import path
from einvoice import views
from einvoice import views_mandate

app_name = "einvoice"

urlpatterns = [
    # Smart Mailbox (inbound)
    path("inbox/", views.smart_mailbox, name="smart_mailbox"),
    path("inbox/<uuid:pk>/", views.mailbox_detail, name="mailbox_detail"),
    path("inbox/<uuid:pk>/approve/", views.mailbox_approve, name="mailbox_approve"),
    path("inbox/<uuid:pk>/reject/", views.mailbox_reject, name="mailbox_reject"),
    # Outbound messages
    path("outbound/", views.outbound_messages, name="outbound_messages"),
    path("message/<uuid:pk>/", views.message_detail, name="message_detail"),
    # Mandati (Punomoći)
    path("mandates/", views_mandate.mandate_list, name="mandate_list"),
    path("mandates/create/", views_mandate.mandate_create, name="mandate_create"),
    path("mandates/<uuid:mandate_id>/pdf/", views_mandate.mandate_pdf, name="mandate_pdf"),
    path("mandates/<uuid:mandate_id>/upload/", views_mandate.mandate_upload_signed, name="mandate_upload_signed"),
    path("mandates/<uuid:mandate_id>/activate/", views_mandate.mandate_activate, name="mandate_activate"),
    path("mandates/<uuid:mandate_id>/revoke/", views_mandate.mandate_revoke, name="mandate_revoke"),
]
