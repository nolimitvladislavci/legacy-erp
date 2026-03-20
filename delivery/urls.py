from django.urls import path

from . import api, views
from . import haccp_views
from . import warehouse_views

app_name = "delivery"

urlpatterns = [
    path("", views.index, name="index"),

    # Consolidated Deliveries (Hub Dashboard)
    path("consolidated/", views.consolidated_list, name="consolidated_list"),
    path("consolidated/new/", views.consolidated_create, name="consolidated_create"),
    path("consolidated/<int:pk>/", views.consolidated_detail, name="consolidated_detail"),
    path("consolidated/<int:pk>/status/", views.consolidated_status_update, name="consolidated_status_update"),

    # Cold Chain API

    # Driver mobile
    path("stop/<int:pk>/", views.driver_stop, name="driver_stop"),
    path("stop/<int:stop_pk>/packaging/", views.driver_packaging_save, name="driver_packaging_save"),
    path("stop/<int:stop_pk>/scan/", views.driver_rollwagen_scan, name="driver_rollwagen_scan"),

    # Dispatcher
    path("dispatcher/", views.dispatcher_board, name="dispatcher_board"),
    path("dispatcher/data/", views.dispatcher_board_data, name="dispatcher_board_data"),
    path("offers/", views.driver_offers, name="driver_offers"),
    path("offers/<int:pk>/accept/", views.driver_accept_offer, name="driver_accept_offer"),

    # HACCP handoff
    path("stop/<int:stop_pk>/handoff/", views.driver_handoff, name="driver_handoff"),

# Driver PWA    path("driver/", views.driver_pwa, name="driver_pwa"),    path("driver/route/<int:route_pk>/start/", views.driver_start_route, name="driver_start_route"),    path("driver/stop/<int:stop_pk>/update/", views.driver_update_stop, name="driver_update_stop"),    path("driver/gps/", views.driver_gps_update, name="driver_gps_update"),
    # Cost calculator API
    path("api/cost/", views.delivery_cost_calc, name="delivery_cost_calc"),
    path("api/cold-chain/ingest/", api.sensor_reading_ingest, name="cold_chain_ingest"),
    path("api/cold-chain/<str:tracking_token>/", api.cold_chain_public, name="cold_chain_public"),

    # HACCP Incidents
    path("haccp/", haccp_views.haccp_incidents, name="haccp_incidents"),
    path("haccp/<int:pk>/resolve/", haccp_views.haccp_resolve, name="haccp_resolve"),
    path("haccp/<int:pk>/report/", haccp_views.haccp_forensic_report, name="haccp_forensic_report"),

    # Warehouse Pick & Pack Terminal
    path("warehouse/", warehouse_views.warehouse_terminal, name="warehouse_terminal"),
    path("warehouse/wave/<int:wave_pk>/", warehouse_views.wave_pick, name="wave_pick"),
    path("warehouse/wave/create/", warehouse_views.create_wave, name="create_wave"),
    path("warehouse/pack/<int:order_pk>/", warehouse_views.pack_station, name="pack_station"),

    # Public Delivery Zones API
    path("api/zones/<slug:slug>/", views.api_delivery_zones, name="api_delivery_zones"),
]
