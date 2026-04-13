from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
class UsersConfig(AppConfig):
    name = 'users'
    verbose_name = 'Users (stub)'
