from django.urls import path
from . import views

app_name = 'stolarija'

urlpatterns = [
    path('',                                    views.dashboard,          name='dashboard'),
    path('nova-sesija/',                        views.session_new,        name='session_new'),
    path('sesija/<int:session_id>/',            views.measure,            name='measure'),
    path('sesija/<int:session_id>/detalji/',    views.session_detail,     name='session_detail'),
    path('sesija/<int:session_id>/ponuda/',     views.generate_offer,     name='generate_offer'),
    path('ponuda/<int:offer_id>/',              views.offer_detail,       name='offer_detail'),
    path('mjerenje/<int:pk>/delete/',           views.measurement_delete, name='measurement_delete'),

    # Phase 4: Production
    path('proizvodnja/<int:offer_id>/kreiraj/',  views.create_production_order, name='create_production'),
    path('proizvodnja/<int:order_id>/',           views.production_detail,       name='production_detail'),

    # Phase 6: Installation
    path('ugradnja/<int:order_id>/kreiraj/',      views.create_installation,     name='create_installation'),
    path('ugradnja/<int:install_id>/',            views.installation_detail,     name='installation_detail'),

    # Phase 7: Handover
    path('primopredaja/<int:install_id>/',        views.handover,                name='handover'),
    path('primopredaja/<int:handover_id>/detalj/',views.handover_detail,         name='handover_detail'),

    # Phase 8: Service & Warranty
    path('garancije/',                            views.warranty_list,           name='warranty_list'),
    path('garancija/<str:qr_token>/',             views.warranty_public,         name='warranty_public'),
    path('servis/',                               views.service_list,            name='service_list'),
    path('servis/<int:visit_id>/',                views.service_detail,          name='service_detail'),

    # PDF + WhatsApp
    path('ponuda/<int:offer_id>/pdf/',          views.offer_pdf,          name='offer_pdf'),
    path('ponuda/<int:offer_id>/whatsapp/',     views.offer_send_whatsapp, name='offer_whatsapp'),
    path('garancija/<int:warranty_id>/pdf/',     views.warranty_pdf,       name='warranty_pdf'),

    # API
    path('voice-parse/',                        views.voice_parse_api,    name='voice_parse'),
    path('ponuda/<int:offer_id>/sign/',         views.sign_offer,         name='sign_offer'),
    path('sesija/<int:session_id>/primopredaja/', views.session_handover,  name='session_handover'),
]
