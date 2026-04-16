from django.urls import re_path
from . import consumers_agent

websocket_urlpatterns = [
    re_path(
        r"ws/fenix/agent/(?P<task_id>[0-9a-f\-]+)/$",
        consumers_agent.FenixAgentConsumer.as_asgi(),
    ),
]
