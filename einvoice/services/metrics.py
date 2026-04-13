"""Prometheus metrics for e-invoice pipeline monitoring.

Counters and histograms for:
- Invoices sent/received/failed
- Validation errors by type
- Delivery latency
- Transport backend usage
"""

import logging

logger = logging.getLogger("propter.einvoice.metrics")

# Try to import prometheus_client, but don't fail if not installed
try:
    from prometheus_client import Counter, Gauge, Histogram, Info  # noqa: F401

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_client not installed — metrics disabled")


if PROMETHEUS_AVAILABLE:
    # ── Counters ──
    INVOICES_SENT = Counter(
        "propter_invoices_sent_total",
        "Total e-invoices sent (by transport and status)",
        ["transport", "status"],
    )
    INVOICES_RECEIVED = Counter(
        "propter_invoices_received_total",
        "Total e-invoices received",
        ["company"],
    )
    VALIDATION_ERRORS = Counter(
        "propter_validation_errors_total",
        "Validation errors by rule",
        ["rule"],
    )
    DLQ_MESSAGES = Counter(
        "propter_dlq_messages_total",
        "Messages moved to dead letter queue",
        ["reason"],
    )
    RETRY_ATTEMPTS = Counter(
        "propter_retry_attempts_total",
        "Retry attempts",
        ["transport"],
    )

    # ── Histograms ──
    DELIVERY_LATENCY = Histogram(
        "propter_delivery_latency_seconds",
        "Time from submission to delivery",
        buckets=[5, 10, 30, 60, 120, 300, 600, 1800, 3600],
    )
    PIPELINE_DURATION = Histogram(
        "propter_pipeline_duration_seconds",
        "Time for full outbound pipeline",
        ["stage"],
        buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
    )

    # ── Gauges ──
    QUEUE_SIZE = Gauge(
        "propter_queue_size",
        "Current queue size by status",
        ["status"],
    )
    INBOX_PENDING = Gauge(
        "propter_inbox_pending",
        "Pending inbound invoices",
    )

else:
    # Dummy metrics that do nothing
    class _DummyMetric:
        def labels(self, *a, **kw):
            return self

        def inc(self, *a, **kw):
            pass

        def dec(self, *a, **kw):
            pass

        def set(self, *a, **kw):
            pass

        def observe(self, *a, **kw):
            pass

    INVOICES_SENT = _DummyMetric()
    INVOICES_RECEIVED = _DummyMetric()
    VALIDATION_ERRORS = _DummyMetric()
    DLQ_MESSAGES = _DummyMetric()
    RETRY_ATTEMPTS = _DummyMetric()
    DELIVERY_LATENCY = _DummyMetric()
    PIPELINE_DURATION = _DummyMetric()
    QUEUE_SIZE = _DummyMetric()
    INBOX_PENDING = _DummyMetric()


def record_sent(transport, status):
    INVOICES_SENT.labels(transport=transport, status=status).inc()


def record_received(company_name):
    INVOICES_RECEIVED.labels(company=company_name).inc()


def record_validation_error(rule):
    VALIDATION_ERRORS.labels(rule=rule).inc()


def record_dlq(reason):
    DLQ_MESSAGES.labels(reason=reason).inc()


def record_retry(transport):
    RETRY_ATTEMPTS.labels(transport=transport).inc()


def record_delivery_latency(seconds):
    DELIVERY_LATENCY.observe(seconds)


def record_pipeline_stage(stage, duration):
    PIPELINE_DURATION.labels(stage=stage).observe(duration)


def update_queue_gauges():
    """Update queue size gauges from database."""
    from einvoice.models import AS4Message, InboundInvoice

    for status_val in ["QUEUED", "SUBMITTED", "SENT", "RETRY", "SEND_FAIL"]:
        count = AS4Message.objects.filter(status=status_val, direction="OUT").count()
        QUEUE_SIZE.labels(status=status_val).set(count)
    INBOX_PENDING.set(InboundInvoice.objects.filter(status="PENDING").count())
