from django.urls import path

from . import futures_views, views

app_name = 'marketplace'

urlpatterns = [
    path('', views.catalog, name='catalog'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/', views.cart_add, name='cart_add'),
    path('cart/remove/<str:key>/', views.cart_remove, name='cart_remove'),
    path('cart/clear/', views.cart_clear, name='cart_clear'),
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.my_orders, name='my_orders'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path("orders/<int:pk>/reorder/", views.reorder, name="reorder"),
    path('seller/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/product/new/', views.seller_product_edit, name='seller_product_new'),
    path('seller/product/<int:pk>/edit/', views.seller_product_edit, name='seller_product_edit'),
    path('seller/order/<int:pk>/action/', views.seller_order_action, name='seller_order_action'),
    # Futures / Pre-harvest
    path('futures/', futures_views.futures_catalog, name='futures_catalog'),
    path('futures/my/', futures_views.futures_my, name='futures_my'),
    path('futures/create/', futures_views.futures_create, name='futures_create'),
    path('futures/<int:pk>/', futures_views.futures_detail, name='futures_detail'),
    path('futures/<int:pk>/reserve/', futures_views.futures_reserve, name='futures_reserve'),
    path('futures/reservation/<int:pk>/action/', futures_views.futures_seller_action, name='futures_seller_action'),


    # I-3: QR Reklamacija
    path('reklamacija/<str:token>/', views.reklamacija_view, name='reklamacija'),
    path('reklamacija/<str:token>/done/', views.reklamacija_done, name='reklamacija_done'),
    # I-4: Legal Vault
    path('orders/<int:pk>/vault/', views.legal_vault, name='legal_vault'),

    # Live Auction
    path('auction/<int:pk>/', views.auction_live, name='auction_live'),
    path('auction/<int:pk>/state/', views.auction_state_api, name='auction_state_api'),

    # Gastro Bridge — Last Call
    path('gastro-bridge/<int:pk>/', views.gastro_bridge, name='gastro_bridge'),

    # Farm-to-Fork Traceability QR
    path('traceability/<int:pk>/', views.traceability_view, name='traceability'),

    # WhatsApp Concierge
    path('cart/share/', views.cart_share_create, name='cart_share_create'),
    path('checkout/shared/<str:token>/', views.cart_shared_checkout, name='cart_shared_checkout'),
]
