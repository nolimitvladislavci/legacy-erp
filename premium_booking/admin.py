from django.contrib import admin

from .models import Addon, Booking, BookingAddon, Payment, Resource

admin.site.register(Resource)
admin.site.register(Addon)
admin.site.register(Booking)
admin.site.register(BookingAddon)
admin.site.register(Payment)
