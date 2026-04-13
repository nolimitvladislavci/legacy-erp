from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'payments'
    verbose_name = 'Payments'
