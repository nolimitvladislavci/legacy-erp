from django.urls import path
from . import views

app_name = 'outreach'

urlpatterns = [
    path('',                                    views.dashboard,             name='dashboard'),
    path('contacts/',                           views.contacts_list,         name='contacts'),
    path('contacts/new/',                       views.contact_new,           name='contact_new'),
    path('contacts/<int:pk>/edit/',             views.contact_edit,          name='contact_edit'),
    path('contacts/<int:pk>/whatsapp/',         views.contact_whatsapp,      name='contact_whatsapp'),
    path('contacts/csv-import/',                views.csv_import,            name='csv_import'),
    path('contacts/import-partners/',           views.import_from_partners,  name='import_partners'),
    path('campaign/new/',                       views.campaign_new,          name='campaign_new'),
    path('campaign/<int:pk>/',                  views.campaign_detail,       name='campaign_detail'),
    path('campaign/<int:pk>/preview/',          views.campaign_preview,      name='campaign_preview'),
    path('campaign/<int:pk>/send/',             views.campaign_send,         name='campaign_send'),
    path('campaign/<int:pk>/bulk-send/',        views.campaign_bulk_send,    name='campaign_bulk_send'),
    path('campaign/<int:pk>/add-contacts/',     views.campaign_add_contacts, name='campaign_add_contacts'),
    path('inbox/',                              views.inbox,                 name='inbox'),
    path('inbox/<int:cc_pk>/replied/',          views.mark_replied,          name='mark_replied'),
]
