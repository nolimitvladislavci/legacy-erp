from django.contrib import admin

from fenix_input.models import InputMessage, SMSDevice


@admin.register(InputMessage)
class InputMessageAdmin(admin.ModelAdmin):
    list_display = ("channel", "short_text", "status", "target_module", "ai_confidence", "created_at")
    list_filter = ("channel", "status", "target_module")
    search_fields = ("raw_text",)
    readonly_fields = ("ai_parsed", "metadata")
    ordering = ("-created_at",)

    def short_text(self, obj):
        return obj.raw_text[:80]

    short_text.short_description = "Tekst"


@admin.register(SMSDevice)
class SMSDeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_number", "device_type", "company", "is_active", "last_message_at")
    list_filter = ("device_type", "is_active")
    search_fields = ("name", "phone_number")
