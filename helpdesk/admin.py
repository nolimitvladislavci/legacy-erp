from django.contrib import admin
from .models import Ticket, TicketMessage, TicketTemplate

class MsgInline(admin.TabularInline):
    model = TicketMessage
    extra = 0

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'subject', 'client', 'category', 'priority', 'status', 'assigned_to', 'company']
    list_filter = ['status', 'priority', 'category', 'company']
    search_fields = ['ticket_number', 'subject', 'client__name']
    inlines = [MsgInline]

@admin.register(TicketTemplate)
class TicketTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active', 'company']


from .models import VIPContact

@admin.register(VIPContact)
class VIPContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'priority', 'auto_assign_to', 'is_active', 'note']
    list_filter = ['priority', 'is_active']
    search_fields = ['name', 'phone', 'note']
    list_editable = ['priority', 'is_active']
