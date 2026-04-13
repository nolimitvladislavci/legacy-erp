from django.contrib import admin

from .models import IncomingMail, MailNotification, VirtualMailbox


@admin.register(VirtualMailbox)
class VirtualMailboxAdmin(admin.ModelAdmin):
    list_display = ('company', 'is_active', 'address_line', 'created_at')
    list_filter = ('is_active',)


@admin.register(IncomingMail)
class IncomingMailAdmin(admin.ModelAdmin):
    list_display = ('company', 'received_date', 'sender', 'mail_type',
                    'status', 'client_viewed', 'processed_by')
    list_filter = ('status', 'mail_type', 'client_viewed', 'company')
    search_fields = ('sender', 'subject', 'notes')
    date_hierarchy = 'received_date'
    readonly_fields = ('created_at', 'client_viewed_at', 'processed_at')


@admin.register(MailNotification)
class MailNotificationAdmin(admin.ModelAdmin):
    list_display = ('mail', 'method', 'sent_to', 'sent_at', 'is_read')
    list_filter = ('method', 'is_read')
