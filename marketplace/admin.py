# Auto-register all models
import inspect

from django.contrib import admin

from . import models as _m
from .models import *

for name, obj in inspect.getmembers(_m):
    if inspect.isclass(obj) and issubclass(obj, _m.models.Model) and obj._meta.app_label == "marketplace":
        try:
            admin.site.register(obj)
        except admin.sites.AlreadyRegistered:
            pass
