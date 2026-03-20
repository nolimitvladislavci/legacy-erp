"""
Cold Chain Service — IoT senzor ingest + HACCP enforcement.

Spaja:
  SmartBox.update_from_sensor() → SensorReading → analyze_readings() → HACCPIncident
  → blokada GoodsReceipt → notifikacija dispatchera

Dizajniran za tisuće pingova bez opterećenja baze:
  - Bulk ingest s batch_create
  - Deduplikacija po timestamp
  - SmartBox cache update (last_temp) bez JOIN-ova
  - analyze_readings samo za boxeve s alertima

EU 852/2004, HR NN 81/13
"""
import logging
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils import timezone as tz

logger = logging.getLogger('cold_chain')


class ColdChainError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


class ColdChainService:
    """Centralni servis za hladni lanac — senzor ingest, HACCP, blokade."""

    # ── Sensor Ingest (IoT webhook) ────────────────────────────

    @classmethod
    @transaction.atomic
    def ingest_reading(cls, box_id, temperature, humidity=None,
                       latitude=None, longitude=None, timestamp=None,
                       raw_payload=None):
        """
        Prima jedno očitanje s IoT senzora.
        Koristi SmartBox.update_from_sensor() + analyze_readings().

        Args:
            box_id: SmartBox.box_id ili sensor_device_id
            temperature: float/Decimal
            humidity: float/Decimal (opcionalno)
            latitude, longitude: GPS (opcionalno)
            timestamp: datetime (default: now)
            raw_payload: dict (sirovi JSON od senzora)

        Returns:
            dict: {reading_id, is_alert, incidents: [...]}
        """
        from delivery.models import SmartBox, SensorReading, analyze_readings

        # Nađi box po box_id ili sensor_device_id
        box = SmartBox.objects.filter(box_id=box_id).first()
        if not box:
            box = SmartBox.objects.filter(sensor_device_id=box_id).first()
        if not box:
            raise ColdChainError('BOX_NOT_FOUND', 'SmartBox "%s" nije pronađen.' % box_id)

        try:
            temp = Decimal(str(temperature))
        except (InvalidOperation, ValueError):
            raise ColdChainError('INVALID_TEMP', 'Neispravna temperatura: %s' % temperature)

        ts = timestamp or tz.now()

        # Deduplikacija — ne spremi ako isto očitanje postoji u zadnjih 30s
        recent = SensorReading.objects.filter(
            smart_box=box,
            timestamp__gte=ts - tz.timedelta(seconds=30),
            temperature=temp,
        ).exists()
        if recent:
            return {'reading_id': None, 'is_alert': False, 'incidents': [], 'deduplicated': True}

        # Kreiraj SensorReading
        reading = SensorReading.objects.create(
            smart_box=box,
            consolidated_delivery=box.current_delivery,
            source='delivery' if box.current_delivery else 'zone',
            timestamp=ts,
            temperature=temp,
            humidity=Decimal(str(humidity)) if humidity is not None else None,
            latitude=Decimal(str(latitude)) if latitude is not None else None,
            longitude=Decimal(str(longitude)) if longitude is not None else None,
            raw_payload=raw_payload,
        )

        # Update SmartBox cache
        box.last_temp = temp
        box.last_reading_at = ts
        update_fields = ['last_temp', 'last_reading_at']
        if latitude is not None:
            box.last_lat = Decimal(str(latitude))
            update_fields.append('last_lat')
        if longitude is not None:
            box.last_lng = Decimal(str(longitude))
            update_fields.append('last_lng')
        box.save(update_fields=update_fields)

        # HACCP analiza samo ako je alert
        incidents = []
        if reading.is_alert or temp > box.target_max_temp or temp < box.target_min_temp:
            incidents = analyze_readings(box)

        return {
            'reading_id': reading.pk,
            'is_alert': reading.is_alert,
            'incidents': [
                {'id': inc.pk, 'type': inc.incident_type, 'severity': inc.severity}
                for inc in incidents
            ],
        }

    # ── Bulk Ingest (offline sync / batch) ─────────────────────

    @classmethod
    def bulk_ingest(cls, box_id, readings_data):
        """
        Prima listu očitanja odjednom (offline sync).

        Args:
            box_id: SmartBox.box_id
            readings_data: list of dicts [{temperature, timestamp, humidity?, lat?, lng?}, ...]

        Returns:
            dict: {ingested: int, alerts: int, incidents: int}
        """
        from delivery.models import SmartBox, SensorReading, analyze_readings

        box = SmartBox.objects.filter(box_id=box_id).first()
        if not box:
            box = SmartBox.objects.filter(sensor_device_id=box_id).first()
        if not box:
            raise ColdChainError('BOX_NOT_FOUND', 'SmartBox "%s" nije pronađen.' % box_id)

        # Bulk create readings
        readings_to_create = []
        alert_count = 0

        for r in readings_data:
            try:
                temp = Decimal(str(r.get('temperature', 0)))
            except (InvalidOperation, ValueError):
                continue

            ts = r.get('timestamp', tz.now())
            is_alert = temp > box.target_max_temp or temp < box.target_min_temp
            if is_alert:
                alert_count += 1

            readings_to_create.append(SensorReading(
                smart_box=box,
                consolidated_delivery=box.current_delivery,
                source='delivery' if box.current_delivery else 'zone',
                timestamp=ts,
                temperature=temp,
                humidity=Decimal(str(r['humidity'])) if r.get('humidity') is not None else None,
                latitude=Decimal(str(r['lat'])) if r.get('lat') is not None else None,
                longitude=Decimal(str(r['lng'])) if r.get('lng') is not None else None,
                is_alert=is_alert,
                alert_message='Temp %sC izvan opsega (%s-%sC)' % (
                    temp, box.target_min_temp, box.target_max_temp
                ) if is_alert else '',
                raw_payload=r.get('raw'),
            ))

        created = SensorReading.objects.bulk_create(readings_to_create, batch_size=500)

        # Update box cache s zadnjim očitanjem
        if created:
            last = max(created, key=lambda x: x.timestamp)
            box.last_temp = last.temperature
            box.last_reading_at = last.timestamp
            if last.latitude:
                box.last_lat = last.latitude
            if last.longitude:
                box.last_lng = last.longitude
            box.save(update_fields=['last_temp', 'last_reading_at', 'last_lat', 'last_lng'])

        # HACCP analiza retroaktivno
        incidents = []
        if alert_count > 0:
            incidents = analyze_readings(box)

        logger.info(
            '[COLD CHAIN] Bulk ingest box %s: %d readings, %d alerts, %d incidents',
            box_id, len(created), alert_count, len(incidents)
        )

        return {
            'ingested': len(created),
            'alerts': alert_count,
            'incidents': len(incidents),
        }

    # ── HACCP Enforcement ──────────────────────────────────────

    @staticmethod
    def check_delivery_haccp(delivery_id):
        """
        Provjeri HACCP status za cijelu isporuku.
        Vraća status i listu incidenata.
        """
        from delivery.models import ConsolidatedDelivery, HACCPIncident

        delivery = ConsolidatedDelivery.objects.get(pk=delivery_id)
        incidents = HACCPIncident.objects.filter(
            consolidated_delivery=delivery,
            is_resolved=False,
        ).order_by('-severity', '-created_at')

        blocked = incidents.filter(severity='blocked').exists()
        critical = incidents.filter(severity='critical').exists()

        status = 'blocked' if blocked else ('critical' if critical else 'ok')

        return {
            'delivery_id': delivery_id,
            'status': status,
            'can_accept_goods': status == 'ok',
            'incidents': [
                {
                    'id': inc.pk,
                    'type': inc.incident_type,
                    'severity': inc.severity,
                    'max_temp': str(inc.max_temperature),
                    'duration_min': inc.duration_minutes,
                    'description': inc.description,
                }
                for inc in incidents
            ],
        }

    @staticmethod
    def block_goods_receipt(smart_box_id):
        """
        Blokira primku (GoodsReceipt) za narudžbe vezane uz blokirani SmartBox.
        Poziva se automatski kad HACCP incident eskalira na 'blocked'.

        Returns:
            list of blocked GoodsReceipt IDs
        """
        from delivery.models import SmartBox
        from inventory.models import GoodsReceipt

        box = SmartBox.objects.select_related('current_delivery').get(pk=smart_box_id)
        if not box.current_delivery:
            return []

        # Nađi sve rollwagene u ovoj isporuci vezane na ovaj box
        order_ids = box.current_delivery.rollwagens.filter(
            bound_order__isnull=False
        ).values_list('bound_order_id', flat=True)

        if not order_ids:
            return []

        # Blokiraj GoodsReceipt koji su 'draft' za ove narudžbe
        blocked = []
        receipts = GoodsReceipt.objects.filter(
            status='draft',
            notes__regex=r'(?:^|[,\s])(' + '|'.join(str(i) for i in order_ids) + r')(?:[,\s]|$)',
        )

        for gr in receipts:
            gr.status = 'haccp_blocked'
            gr.notes = (gr.notes or '') + '\n[HACCP BLOKADA] SmartBox %s — prekid hladnog lanca' % box.box_id
            gr.save(update_fields=['status', 'notes'])
            blocked.append(gr.pk)
            logger.warning('[HACCP] GoodsReceipt %s blocked due to SmartBox %s', gr.pk, box.box_id)

        return blocked

    # ── Dashboard Data ─────────────────────────────────────────

    @staticmethod
    def get_fleet_status(company_id):
        """
        Pregled svih SmartBoxeva za kompaniju — za dashboard.
        Vraća grupirane po statusu.
        """
        from delivery.models import SmartBox
        from django.db.models import Count

        boxes = SmartBox.objects.filter(owner_company_id=company_id)

        summary = boxes.values('haccp_status').annotate(count=Count('id'))
        status_map = {s['haccp_status']: s['count'] for s in summary}

        alerts = boxes.filter(
            haccp_status__in=['warning', 'critical', 'blocked']
        ).select_related('current_delivery').order_by('-last_reading_at')[:20]

        return {
            'total': boxes.count(),
            'ok': status_map.get('ok', 0),
            'warning': status_map.get('warning', 0),
            'critical': status_map.get('critical', 0),
            'blocked': status_map.get('blocked', 0),
            'alerts': [
                {
                    'box_id': b.box_id,
                    'status': b.haccp_status,
                    'last_temp': str(b.last_temp) if b.last_temp else None,
                    'last_reading': b.last_reading_at.isoformat() if b.last_reading_at else None,
                    'delivery': str(b.current_delivery) if b.current_delivery else None,
                }
                for b in alerts
            ],
        }
