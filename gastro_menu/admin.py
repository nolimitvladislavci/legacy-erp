# Auto-register all models
import inspect

from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import models as _m
from .models import *

for name, obj in inspect.getmembers(_m):
    if inspect.isclass(obj) and issubclass(obj, _m.models.Model) and obj._meta.app_label == 'gastro_menu':
        try:
            admin.site.register(obj)
        except admin.sites.AlreadyRegistered:
            pass
