"""
udruge/routing.py — WebSocket URL routing for live auctions.
"""
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/auction/(?P<product_id>\d+)/$', consumers.AuctionConsumer.as_asgi()),
]
