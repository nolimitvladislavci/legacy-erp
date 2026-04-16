from django.db import models
import hashlib

class ValidationLog(models.Model):
    TYPES = [('oib_hr','OIB HR'),('vat_eu','VAT EU'),('iban','IBAN'),('mbs','MBS'),('cross','Cross')]
    validation_type = models.CharField(max_length=20, choices=TYPES)
    input_hash = models.CharField(max_length=64)
    is_valid = models.BooleanField()
    is_api_call = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    response_ms = models.IntegerField(default=0)
    class Meta:
        db_table = 'evalidator_log'
        indexes = [models.Index(fields=['validation_type','created_at'])]

class APIKey(models.Model):
    PLANS = [('free','Free 100/day'),('starter','1k/day'),('pro','10k/day'),('enterprise','Unlimited')]
    name = models.CharField(max_length=200)
    email = models.EmailField()
    key_hash = models.CharField(max_length=64, unique=True)
    plan = models.CharField(max_length=20, choices=PLANS, default='free')
    daily_limit = models.IntegerField(default=100)
    daily_used = models.IntegerField(default=0)
    last_reset = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'evalidator_apikey'
    def can_use(self):
        from django.utils import timezone
        today = timezone.now().date()
        if self.last_reset < today:
            self.daily_used = 0; self.last_reset = today
            self.save(update_fields=['daily_used','last_reset'])
        return self.is_active and self.daily_used < self.daily_limit
