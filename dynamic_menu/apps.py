from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
class DynamicMenuConfig(AppConfig):
    name = 'dynamic_menu'
