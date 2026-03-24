from django.urls import path

from . import views
from . import pickup_views
from . import field_sales_views
from . import views_v2

app_name = 'pos'

urlpatterns = [
    path('kiosk/<str:token>/', views.kiosk_view, name='kiosk'),
    # Standardizirani API (Gemini JSON Ugovor A/B/C)
    path('api/pos/items/', views.api_pos_items, name='api_pos_items'),
    path('api/pos/checkout/', views.api_pos_checkout, name='api_pos_checkout'),

    path('', views.dashboard, name='dashboard'),
    path('terminal/<int:terminal_id>/', views.terminal_detail, name='terminal_detail'),
    path('terminal/<int:terminal_id>/open/', views.open_session, name='open_session'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),
    path('session/<int:session_id>/close/', views.close_session, name='close_session'),
    path('session/<int:session_id>/receipt/new/', views.new_receipt, name='new_receipt'),
    path('receipt/<int:receipt_id>/', views.receipt_detail, name='receipt_detail'),
    path('receipt/<int:receipt_id>/add-item/', views.add_item, name='add_item'),
    path('receipt/<int:receipt_id>/remove-item/<int:item_id>/', views.remove_item, name='remove_item'),
    path('receipt/<int:receipt_id>/pay/', views.process_payment, name='process_payment'),
    path('receipt/<int:receipt_id>/cancel/', views.cancel_receipt, name='cancel_receipt'),
    path('api/barcode/', views.barcode_lookup, name='barcode_lookup'),
    path('api/ai-barcode/', views.ai_barcode_lookup, name='ai_barcode_lookup'),
    path('api/quick-add-item/', views.api_quick_add_item, name='api_quick_add_item'),
    path('webshop/<slug:slug>/', views.webshop_public, name='webshop_public'),
    path('yesterday/', views.yesterday_manage, name='yesterday_manage'),
    path('terminal/new/', views.new_terminal, name='new_terminal'),
    path('session/<int:session_id>/zreport/', views.session_zreport, name='session_zreport'),
    path('session/<int:session_id>/deposit/', views.cash_deposit, name='cash_deposit'),
    path('receipt/<int:receipt_id>/pdf/', views.receipt_pdf, name='receipt_pdf'),
    path('session/<int:session_id>/cashier-report/', views.cashier_full_report, name='cashier_full_report'),
    # ── POS Variants ───────────────────────────────────────────────────────
    path('quick/', views.quick_pos_redirect, name='quick_pos_redirect'),
    path('quick/<int:terminal_id>/',      views.quick_pos,      name='quick_pos'),
    path('restaurant/<int:terminal_id>/', views.restaurant_pos, name='restaurant_pos'),
    path('session/<int:session_id>/quick-pay/', views.quick_pay, name='quick_pay'),
    # ── Restaurant AJAX endpoints ───────────────────────────────────────────
    path('receipt/<int:receipt_id>/json/',     views.receipt_json,     name='receipt_json'),
    path('receipt/<int:receipt_id>/add-item/', views.receipt_add_item, name='receipt_add_item'),
    path('receipt/<int:receipt_id>/pay/',      views.receipt_pay,      name='receipt_pay'),
    path('session/<int:session_id>/new-receipt/', views.new_receipt_ajax, name='new_receipt_ajax'),
    # ── Settings ────────────────────────────────────────────────────────────────
    path('settings/',                            views.pos_settings,          name='pos_settings'),
    path('settings/save-printer/',               views.settings_save_printer, name='settings_save_printer'),
    path('settings/save-fiscal/',                views.settings_save_fiscal,  name='settings_save_fiscal'),
    path('settings/test-fiscal/',                views.settings_test_fiscal,  name='settings_test_fiscal'),
    path('settings/test-print/',                 views.settings_test_print,   name='settings_test_print'),
    path('settings/cashier/save/',               views.cashier_save,          name='cashier_save'),
    path('settings/cashier/<int:cashier_id>/delete/', views.cashier_delete,   name='cashier_delete'),
    path('api/cashier/verify-pin/', views.cashier_pin_verify, name='cashier_pin_verify'),
    path('settings/inventory/save/',             views.inventory_item_save,   name='inventory_item_save'),
    path('settings/inventory/csv-import/',       views.inventory_csv_import,  name='inventory_csv_import'),
    path('settings/reports/export/',             views.reports_export,        name='reports_export'),

    # ── Gastro POS ──────────────────────────────────────────────────────────────
    path('gastro/',                                     views.gastro_dashboard,       name='gastro_dashboard'),
    path('gastro/table/<int:table_id>/',                views.gastro_table_order,     name='gastro_table_order'),
    path('gastro/table/<int:table_id>/checkout/',       views.table_checkout,         name='table_checkout'),
    path('gastro/kitchen/',                             views.gastro_kitchen,         name='gastro_kitchen'),
    path('gastro/kitchen/api/',                         views.gastro_kitchen_api,     name='gastro_kitchen_api'),
    path('gastro/order/<int:order_id>/update/',         views.gastro_order_update,    name='gastro_order_update'),
    path('gastro/order/<int:order_id>/add-item/',       views.gastro_order_add_item,  name='gastro_order_add_item'),
    path('gastro/order/<str:token>/',                   views.gastro_order_public,    name='gastro_order_public'),
    path("gastro/order/<str:tracking_token>/review/", views.gastro_order_review, name="gastro_order_review"),
    path("gastro/reviews/<int:company_id>/", views.gastro_reviews_public, name="gastro_reviews_public"),

    # Waiter system
    path('waiter/',                                      views.waiter_app,             name='waiter_app'),
    path('session/<int:session_id>/report/', views.session_report_json, name='session_report_json'),
    path('session/<int:session_id>/report/html/', views.cashier_report_html, name='cashier_report_html'),
    path('session/<int:session_id>/cashier/<int:cashier_id>/report/', views.cashier_report, name='cashier_report'),
    path('waiter/shift/',                                views.waiter_shift_toggle,    name='waiter_shift_toggle'),
    path('waiter/heartbeat/',                            views.waiter_heartbeat,       name='waiter_heartbeat'),
    path('waiter/claim/<int:order_id>/',                 views.waiter_claim_order,     name='waiter_claim_order'),
    path('waiter/deliver/<int:order_id>/',               views.waiter_deliver_order,   name='waiter_deliver_order'),
    path('waiter/shifts/',                               views.waiter_shift_log,       name='waiter_shift_log'),
    # Kitchen tablet (no login)
    path('gastro/kds/<str:token>/',                      views.kitchen_tablet,         name='kitchen_tablet'),
    path('gastro/kds/<str:token>/api/',                  views.kitchen_tablet_api,     name='kitchen_tablet_api'),
    path('gastro/kds/<str:token>/action/<int:order_id>/',views.kitchen_tablet_action,  name='kitchen_tablet_action'),
    path('gastro/kds/<str:token>/cook-scan/',            views.kitchen_cook_scan,      name='kitchen_cook_scan'),
    path('gastro/qr/<str:qr_code>/',                   views.gastro_qr,              name='gastro_qr'),
    # ── Expiry Tracking ─────────────────────────────────────────────────────────
    path('expiry/',                                     views.expiry_dashboard,       name='expiry_dashboard'),
    path('expiry/add/',                                 views.expiry_add,             name='expiry_add'),
    path('expiry/api/alerts/',                          views.expiry_alerts_api,      name='expiry_alerts_api'),
    path('api/quick-create/',                            views.article_quick_create,   name='article_quick_create'),
    path('api/articles/search/', views.article_search, name='article_search'),
    # ── Pfand + Vauceri ───────────────────────────────────────────────────────
    # ── Fiskalna soba ────────────────────────────────────────────────────────────
    path('fiscal/room/',        views.fiscal_room,        name='fiscal_room'),
    path('fiscal/room/sync/',   views.fiscal_room_sync,   name='fiscal_room_sync'),
    path('fiscal/status-api/',  views.fiscal_status_api,  name='fiscal_status_api'),
    path('api/pfand-items/',             views.pfand_items_api,   name='pfand_items_api'),
    path('api/pfand-return/',            views.pfand_return,      name='pfand_return'),
    path('api/voucher/check/',           views.voucher_check_api, name='voucher_check_api'),
    path('vouchers/',                    views.voucher_list,      name='voucher_list'),
    path('receipt/<int:receipt_id>/refund/', views.refund_receipt, name='refund_receipt'),
    # Knjiga prigovora (zakonski obavezno)
    path('prigovori/',           views.prigovori_list,       name='prigovori_list'),
    path('api/prigovori/',       views.prigovori_api,        name='prigovori_api'),
    path('prigovori/pdf/',       views.knjiga_prigovora_pdf, name='knjiga_prigovora_pdf'),
    path('tips/',                        views.tip_report,        name='tip_report'),
    # Revolut naplata
    path('revolut/pay/<int:receipt_id>/',    views.revolut_pay,     name='revolut_pay'),
    path('revolut/status/<int:receipt_id>/', views.revolut_status,  name='revolut_status'),
    path('revolut/qr/<int:receipt_id>/',     views.revolut_qr,      name='revolut_qr'),
    path('revolut/webhook/',                 views.revolut_webhook, name='revolut_webhook'),
    # Pickup QR flow (pekara)
    path('pickup/<str:company_slug>/',              pickup_views.pickup_menu,          name='pickup_menu'),
    path('pickup/<str:company_slug>/order/',         pickup_views.pickup_order,         name='pickup_order'),
    path('pickup/<str:company_slug>/board/',         pickup_views.pickup_board,         name='pickup_board'),
    path('pickup/track/<str:tracking_token>/',       pickup_views.pickup_track,         name='pickup_track'),
    path('pickup/status/<int:order_id>/',            pickup_views.pickup_status_update, name='pickup_status_update'),

    # Terenska prodaja
    path('field/<int:terminal_id>/start/',    field_sales_views.field_start,     name='field_start'),
    path('field/<int:session_id>/dashboard/', field_sales_views.field_dashboard, name='field_dashboard'),
    path('field/<int:session_id>/return/',    field_sales_views.field_return,    name='field_return'),
    # ── Novi endpointi (2026-03-18) ─────────────────────────────────────────────
    path('api/item/<int:item_id>/',        views.pos_item_api,          name='pos_item_api'),
    path('reports/daily/',                 views.daily_reports_list,    name='daily_reports'),
    path('gastro/kds/<str:token>/cook-logout/', views.kitchen_cook_logout, name='kitchen_cook_logout'),
    path('device-token/create/',           views.device_token_create,   name='device_token_create'),
    path('device-token/<int:token_id>/panic/', views.device_token_panic, name='device_token_panic'),
    path('device-token/list/',             views.device_token_list,     name='device_token_list'),
    # ── Knjiga boljitaka + Onboarding ─────────────────────────────────────────
    path('improvements/',                       views.improvement_list,    name='improvement_list'),
    path('improvements/<int:pk>/update/',       views.improvement_update,  name='improvement_update'),
    path('onboarding/',                         views.onboarding_wizard,   name='onboarding_wizard'),
    path('cashier/setup/',                       views.cashier_setup,        name='cashier_setup'),
    # ── BEZ PAPIRA — Receipt delivery ────────────────────────────────────────
    path('receipts/',                                views.receipt_list,         name='receipt_list'),
    path('receipt/<int:receipt_id>/deliver/',      views.receipt_deliver,      name='receipt_deliver'),
    path('receipt/<int:receipt_id>/whatsapp/',     views.receipt_whatsapp,     name='receipt_whatsapp'),
    path('receipt/<int:receipt_id>/email/',        views.receipt_email,        name='receipt_email'),
    path('receipt/<int:receipt_id>/public/',       views.receipt_public,       name='receipt_public'),
    path('r/<int:receipt_id>/<str:token>/',       views.receipt_public,       name='receipt_public_short'),
    path('receipt/<int:receipt_id>/drawer-kick/',  views.receipt_drawer_kick,  name='receipt_drawer_kick'),
    path('api/delivery-settings/',                views.pos_delivery_settings, name='delivery_settings'),

    # DSFinV-K Export (DE Kassenarchiv)
    path('dsfinvk-export/',                       views.dsfinvk_export,       name='dsfinvk_export'),
    path('kassenbuch/',                            views.kassenbuch_download,  name='kassenbuch'),
    # -- QR Instant Open (zero-login) --
    path("qr/<str:token>/", views.pos_qr_open, name="pos_qr_open"),
    path("qr/session/<int:session_id>/", views.qr_session, name="qr_session"),
    path("qr/session/<int:session_id>/quick-pay/", views.qr_quick_pay, name="qr_quick_pay"),
    # ══════════════════════════════════════════════════════════════════════════
    # V2 ENDPOINTS (Session 2026-03-21)
    # ══════════════════════════════════════════════════════════════════════════
    # B-13: Kitchen API cached (ETag + throttle)
    path('gastro/kitchen/api/v2/',              views_v2.kitchen_api_cached,    name='kitchen_api_cached'),
    # HR-F11: Storno fiskalizacija
    path('receipt/<int:receipt_id>/storno/',     views_v2.storno_receipt,        name='storno_receipt'),
    # HR-P12: Customer Display
    path('display/<str:token>/',                 views_v2.customer_display,      name='customer_display'),
    path('api/display/<str:token>/',             views_v2.customer_display_api,  name='customer_display_api'),
    path('terminal/<int:terminal_id>/display-token/', views_v2.generate_display_token, name='generate_display_token'),
    # HR-P13: Training mode
    path('terminal/<int:terminal_id>/training/', views_v2.toggle_training,       name='toggle_training'),
    # HR-C12: Partial payment
    path('receipt/<int:receipt_id>/partial-pay/', views_v2.partial_payment,      name='partial_payment'),
    # HR-P11: Split bill
    path('receipt/<int:receipt_id>/split/',       views_v2.split_bill,           name='split_bill'),
    # DE-05: ZUGFeRD
    path('receipt/<int:receipt_id>/zugferd/',     views_v2.zugferd_pdf,          name='zugferd_pdf'),
    # DE-07: DATEV
    path('datev/',                               views_v2.datev_export,          name='datev_export'),
    # POS Pulse
    path('pulse/',                               views_v2.pulse_dashboard,       name='pulse_dashboard'),
    path('api/pulse/',                           views_v2.pulse_api,             name='pulse_api'),
    path('api/pulse/read/',                      views_v2.pulse_mark_read,       name='pulse_mark_read'),
    # Pocket Mode (mobitel = blagajna)
    path('pocket/activate/',                     views_v2.pocket_mode_activate,  name='pocket_activate'),
    path('pocket/status/',                       views_v2.pocket_mode_status,    name='pocket_status'),
    # Offline Sync (ServiceWorker batch)
    path('api/offline-sync/',                    views_v2.offline_sync,          name='offline_sync'),
    path('api/offline-catalog/',                 views_v2.offline_catalog,       name='offline_catalog'),
    # B-01: ServiceWorker
    path('sw.js',                                views_v2.pos_service_worker,    name='pos_sw'),
    # Hash Chain — kriptografski audit trail
    path('chain/verify/',                        views_v2.chain_verify,          name='chain_verify'),
    path('chain/receipt/<int:receipt_id>/',       views_v2.chain_receipt_check,   name='chain_receipt_check'),
]
