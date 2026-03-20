from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"api/items", views.InventoryItemViewSet)
router.register(r"api/movements", views.StockMovementViewSet)

app_name = "inventory"

urlpatterns = [
    path('api/quick-create-article/', views.api_quick_create_article, name='api_quick_create_article'),
    # Articles
    path("", views.item_list, name="list"),
    path("new/", views.item_create, name="create"),
    path("<int:pk>/", views.item_detail, name="detail"),
    path("<int:pk>/edit/", views.item_edit, name="edit"),
    path("<int:pk>/movement/", views.stock_movement, name="movement"),
    # Primka (GoodsReceipt)
    path("receipts/", views.goods_receipt_list, name="receipt_list"),
    path("receipts/new/", views.goods_receipt_create, name="receipt_create"),
    path("receipts/<int:pk>/", views.goods_receipt_detail, name="receipt_detail"),
    path("receipts/<int:pk>/pdf/", views.goods_receipt_pdf, name="receipt_pdf"),

    # Skladista
    path("warehouses/", views.warehouse_list, name="warehouse_list"),

    # Medjuskladisnice
    path("transfers/", views.transfer_list, name="transfer_list"),
    path("transfers/new/", views.transfer_create, name="transfer_create"),
    path("transfers/<int:pk>/", views.transfer_detail, name="transfer_detail"),
    path("transfers/<int:pk>/confirm/", views.transfer_confirm, name="transfer_confirm"),
    path("transfers/<int:pk>/receive/", views.transfer_receive, name="transfer_receive"),
    path("receipts/<int:pk>/confirm/", views.goods_receipt_confirm, name="receipt_confirm"),
    # Stock overview
    path("overview/", views.stock_overview, name="stock_overview"),
    path("stock-card/<int:item_id>/", views.stock_card, name="stock_card"),
    # Kalo
    path("kalo/", views.kalo_view, name="kalo"),

    path("blind-count/", views.blind_count_view, name="blind_count"),
    # Phase 10: Continuous Blind Inventory
    path('api/submit-count/', views.api_submit_count, name='api_submit_count'),
    path('api/batch/<int:batch_id>/check-dispatch/', views.api_check_batch_for_dispatch, name='api_check_batch_dispatch'),
    path("reorder-predictions/", views.reorder_predictions, name="reorder_predictions"),
    path("predictive/", views.predictive_dashboard, name="predictive_dashboard"),
    path("reorder-trigger/", views.trigger_reorder, name="reorder_trigger"),
    path("auto-po/", views.auto_generate_po, name="auto_generate_po"),

    # ═══ Inventura (Godišnji popis) ═══
    path("inventura/", views.inventura_list, name="inventura_list"),
    path("inventura/new/", views.inventura_create, name="inventura_create"),
    path("inventura/<int:pk>/", views.inventura_detail, name="inventura_detail"),
    path("inventura/<int:pk>/count/", views.inventura_count, name="inventura_count"),
    path("inventura/<int:pk>/complete/", views.inventura_complete, name="inventura_complete"),
    path("inventura/<int:pk>/approve/", views.inventura_approve, name="inventura_approve"),
    path("inventura/<int:pk>/pdf/", views.inventura_pdf, name="inventura_pdf"),
    path("inventura/<int:pk>/differences/", views.inventura_difference_pdf, name="inventura_difference_pdf"),
    path("inventura/<int:pk>/csv/", views.inventura_export_csv, name="inventura_export_csv"),
    path("inventura/<int:pk>/api/scan/", views.inventura_api_scan, name="inventura_api_scan"),

    # DRF API
    path("", include(router.urls)),
]
