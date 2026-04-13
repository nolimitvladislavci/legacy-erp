"""
ASGI config for LIMIT Connect.
Supports HTTP + WebSocket (Django Channels).
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from udruge.routing import websocket_urlpatterns
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
