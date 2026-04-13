from django.db import models
from django.contrib.auth.models import User
from core.managers import CompanyManager


class Notification(models.Model):
    TYPE_CHOICES = [
        ('timesheet_approved', 'Timesheet Approved'),
        ('timesheet_rejected', 'Timesheet Rejected'),
        ('invoice_paid', 'Invoice Paid'),
        ('invoice_created', 'Invoice Created'),
        ('intervention_assigned', 'Intervention Assigned'),
        ('intervention_updated', 'Intervention Updated'),
        ('appointment_confirmed', 'Appointment Confirmed'),
        ('appointment_cancelled', 'Appointment Cancelled'),
        ('system', 'System'),
        ('ai_response', 'AI Response'),
        ('ai_request', 'AI Request'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='system')
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f'{self.title} -> {self.recipient.username}'
