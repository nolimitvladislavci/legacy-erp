"""
Tech Radar — kapacitetni monitoring i tehnološki signali.

TechSignal: zapis o metrikama sustava (DB, disk, memory, sessions, queue).
CapacityThreshold: pragovi za alarme (npr. disk > 85% → warning).
"""
import uuid
from django.db import models, DatabaseError, IntegrityError
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist


class TechSignal(models.Model):
    """
    Jedno očitanje stanja sustava — snima se svakih 15 min.
    Koristi se za trending, kapacitetno planiranje i alarmiranje.
    """
    SEVERITY_CHOICES = [
        ('ok', 'OK'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    SOURCE_CHOICES = [
        ('auto', 'Automatski (Celery)'),
        ('manual', 'Ručni check'),
        ('ai', 'AI analiza'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='auto')

    # ── System Metrics ──
    db_size_mb = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name=_('DB veličina (MB)'))
    db_connections = models.IntegerField(default=0, verbose_name=_('Aktivne DB konekcije'))
    db_table_count = models.IntegerField(default=0, verbose_name=_('Broj tablica'))

    disk_used_pct = models.DecimalField(max_digits=5, decimal_places=1, default=0,
                                        verbose_name=_('Disk korišten (%)'))
    disk_free_gb = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                       verbose_name=_('Disk slobodan (GB)'))

    memory_used_pct = models.DecimalField(max_digits=5, decimal_places=1, default=0,
                                          verbose_name=_('RAM korišten (%)'))
    memory_available_mb = models.IntegerField(default=0, verbose_name=_('RAM dostupan (MB)'))

    cpu_load_1m = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                      verbose_name=_('CPU load (1 min)'))

    # ── Application Metrics ──
    active_sessions = models.IntegerField(default=0, verbose_name=_('Aktivne sesije'))
    celery_queue_size = models.IntegerField(default=0, verbose_name=_('Celery red čekanja'))
    celery_workers = models.IntegerField(default=0, verbose_name=_('Celery radnici'))
    redis_memory_mb = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                          verbose_name=_('Redis memorija (MB)'))
    media_size_mb = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                        verbose_name=_('Media veličina (MB)'))

    # ── Business Metrics ──
    total_companies = models.IntegerField(default=0, verbose_name=_('Ukupno tvrtki'))
    total_users = models.IntegerField(default=0, verbose_name=_('Ukupno korisnika'))
    receipts_today = models.IntegerField(default=0, verbose_name=_('Računa danas'))
    api_calls_today = models.IntegerField(default=0, verbose_name=_('API poziva danas'))

    # ── Severity & Alerts ──
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='ok')
    alerts = models.JSONField(default=list, blank=True, verbose_name=_('Alarmi'))
    ai_summary = models.TextField(blank=True, verbose_name=_('AI sažetak'))

    class Meta:
        db_table = 'tech_radar_signal'
        ordering = ['-timestamp']
        verbose_name = _('Tech Signal')
        verbose_name_plural = _('Tech Signals')
        indexes = [
            models.Index(fields=['severity', '-timestamp']),
        ]

    def __str__(self):
        return '%s [%s] DB:%sMB Disk:%s%% RAM:%s%%' % (
            self.timestamp.strftime('%d.%m %H:%M') if self.timestamp else '?',
            self.severity.upper(),
            self.db_size_mb, self.disk_used_pct, self.memory_used_pct,
        )


class CapacityThreshold(models.Model):
    """
    Konfigurabilni pragovi za alarme.
    Npr: disk_used_pct warning=80, critical=90
    """
    metric = models.CharField(max_length=50, unique=True, verbose_name=_('Metrika'))
    warning_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Warning prag'))
    critical_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Critical prag'))
    is_active = models.BooleanField(default=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'tech_radar_threshold'
        verbose_name = _('Capacity Threshold')
        verbose_name_plural = _('Capacity Thresholds')

    def __str__(self):
        return '%s (warn: %s, crit: %s)' % (self.metric, self.warning_value, self.critical_value)

    @classmethod
    def check_metric(cls, metric_name, value):
        """Provjeri metriku i vrati severity: 'ok', 'warning', ili 'critical'."""
        try:
            t = cls.objects.get(metric=metric_name, is_active=True)
            if value >= t.critical_value:
                return 'critical'
            elif value >= t.warning_value:
                return 'warning'
            return 'ok'
        except cls.DoesNotExist:
            return 'ok'
