from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .builder import builder_page, builder_api, builder_generate, builder_queue

urlpatterns = [
    path('', builder_page, name='ai_builder'),
    path('api/chat/', builder_api, name='ai_builder_api'),
    path('generate/', builder_generate, name='ai_builder_generate'),
    path('queue/', builder_queue, name='ai_builder_queue'),
]
