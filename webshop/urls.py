from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"api/products", views.ProductViewSet)
router.register(r"api/orders", views.OrderViewSet)
router.register(r"api/orderitems", views.OrderItemViewSet)

app_name = "webshop"
urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("orders/", views.order_list, name="order_list"),
    path("orders/new/", views.order_create, name="order_create"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("orders/<int:pk>/status/", views.order_status_change, name="order_status"),
    # Phase 11: Polymorphic Cart
    path("api/cart/add/", views.api_cart_add, name="api_cart_add"),
    path("", include(router.urls)),
    # Javni webshop po kompaniji
    path("shop/<slug:company_slug>/", views.public_shop, name="public_shop"),
    path("shop/<slug:company_slug>/proizvod/<int:pk>/", views.public_product, name="public_product"),
    path("shop/<slug:company_slug>/kosara/", views.public_cart, name="public_cart"),
    path("shop/<slug:company_slug>/kosara/dodaj/", views.public_cart_add, name="public_cart_add"),
    path("shop/<slug:company_slug>/kosara/ukloni/", views.public_cart_remove, name="public_cart_remove"),
    path("shop/<slug:company_slug>/naruci/", views.public_checkout, name="public_checkout"),
    path("shop/<slug:company_slug>/naruci/potvrdi/", views.public_checkout_submit, name="public_checkout_submit"),
]
