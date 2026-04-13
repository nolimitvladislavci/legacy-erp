from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import Addon, Booking, BookingAddon, Payment, Resource

admin.site.register(Resource)
admin.site.register(Addon)
admin.site.register(Booking)
admin.site.register(BookingAddon)
admin.site.register(Payment)
