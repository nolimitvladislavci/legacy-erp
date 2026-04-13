from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import portal_views

urlpatterns = [
    path('<uuid:token>/', portal_views.portal_dashboard, name='helpdesk_portal'),
    path('<uuid:token>/new/', portal_views.portal_new_ticket, name='helpdesk_portal_new'),
    path('<uuid:token>/ticket/<int:pk>/', portal_views.portal_ticket_detail, name='helpdesk_portal_ticket'),
    path('<uuid:token>/ticket/<int:pk>/reply/', portal_views.portal_ticket_reply, name='helpdesk_portal_reply'),
    path('<uuid:token>/ticket/<int:pk>/rate/', portal_views.portal_ticket_rate, name='helpdesk_portal_rate'),
]
