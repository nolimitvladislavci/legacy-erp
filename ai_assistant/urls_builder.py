from django.urls import path

from .builder import builder_api, builder_generate, builder_page, builder_queue

urlpatterns = [
    path("", builder_page, name="ai_builder"),
    path("api/chat/", builder_api, name="ai_builder_api"),
    path("generate/", builder_generate, name="ai_builder_generate"),
    path("queue/", builder_queue, name="ai_builder_queue"),
]
