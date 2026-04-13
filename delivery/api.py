"""
delivery/api.py - Cold Chain API za primanje temp podataka iz vanjskog sustava.

Veletrznica Osijek (ili bilo koji hub) salje POST s temperaturnim ocitanjima.
Token-based auth — svaki hub ima svoj API token.
"""
from django.db.models import Avg, Max, Min
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ConsolidatedDelivery, SensorReading


class SensorReadingSerializer(serializers.Serializer):
    zone_id = serializers.IntegerField(required=False)
    vehicle_id = serializers.IntegerField(required=False)
    delivery_id = serializers.IntegerField(required=False)
    smart_box_id = serializers.IntegerField(required=False)
    timestamp = serializers.DateTimeField(required=False)
    temperature = serializers.DecimalField(max_digits=5, decimal_places=1)
    humidity = serializers.DecimalField(max_digits=5, decimal_places=1, required=False)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    raw_payload = serializers.JSONField(required=False)


class BulkSensorReadingSerializer(serializers.Serializer):
    readings = SensorReadingSerializer(many=True)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def sensor_reading_ingest(request):
    """
    POST /api/delivery/cold-chain/ingest/

    Primi jedno ili vise ocitanja temperature.

    Jedno ocitanje:
    {"zone_id": 1, "temperature": 3.8, "humidity": 65.2}

    Vise ocitanja:
    {"readings": [{"zone_id": 1, "temperature": 3.8}, {"zone_id": 2, "temperature": -18.1}]}
    """
    if 'readings' in request.data:
        ser = BulkSensorReadingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        readings_data = ser.validated_data['readings']
    else:
        ser = SensorReadingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        readings_data = [ser.validated_data]

    created = []
    for rd in readings_data:
        source = 'zone'
        if rd.get('vehicle_id'):
            source = 'vehicle'
        elif rd.get('delivery_id'):
            source = 'delivery'

        reading = SensorReading.objects.create(
            zone_id=rd.get('zone_id'),
            vehicle_id=rd.get('vehicle_id'),
            consolidated_delivery_id=rd.get('delivery_id'),
            smart_box_id=rd.get('smart_box_id'),
            source=source,
            timestamp=rd.get('timestamp') or timezone.now(),
            temperature=rd['temperature'],
            humidity=rd.get('humidity'),
            latitude=rd.get('latitude'),
            longitude=rd.get('longitude'),
            raw_payload=rd.get('raw_payload'),
        )
        created.append({
            'id': reading.id,
            'is_alert': reading.is_alert,
            'alert_message': reading.alert_message,
        })

    # HACCP Analysis — run for each affected SmartBox
    from .models import SmartBox
    from .models import analyze_readings as haccp_analyze
    box_ids = set()
    for rd in readings_data:
        if rd.get('smart_box_id'):
            box_ids.add(rd['smart_box_id'])
    haccp_incidents = []
    for box_id in box_ids:
        try:
            box = SmartBox.objects.get(pk=box_id)
            incidents = haccp_analyze(box)
            haccp_incidents.extend([{
                'id': inc.id,
                'type': inc.incident_type,
                'severity': inc.severity,
                'description': inc.description,
                'max_temp': float(inc.max_temperature),
                'duration_min': inc.duration_minutes,
            } for inc in incidents])
        except SmartBox.DoesNotExist:
            pass

    return Response({
        'status': 'ok',
        'created': len(created),
        'readings': created,
        'haccp_incidents': haccp_incidents,
        'haccp_blocked_boxes': list(
            SmartBox.objects.filter(pk__in=box_ids, haccp_status='blocked').values_list('box_id', flat=True)
        ),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def cold_chain_public(request, tracking_token):
    """
    GET /api/delivery/cold-chain/{tracking_token}/

    Public endpoint — za prikaz temperature na tracking stranici.
    Ne zahtijeva login.
    """
    try:
        cd = ConsolidatedDelivery.objects.get(
            tracked_item__public_token=tracking_token
        )
    except ConsolidatedDelivery.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    # Zadnjih 10 ocitanja za ovu isporuku
    readings = SensorReading.objects.filter(
        consolidated_delivery=cd
    ).order_by('-timestamp')[:10]

    # Ako nema ocitanja za delivery, pokusaj iz zone
    if not readings.exists() and cd.cold_chain_zone:
        readings = cd.cold_chain_zone.sensor_readings.order_by('-timestamp')[:10]

    if not readings.exists():
        return Response({
            'has_cold_chain': cd.requires_cold_chain,
            'readings_available': False,
        })

    latest = readings.first()
    agg = readings.aggregate(
        min_temp=Min('temperature'),
        max_temp=Max('temperature'),
        avg_temp=Avg('temperature'),
    )

    zone = cd.cold_chain_zone
    target_min = float(zone.target_min_temp) if zone else None
    target_max = float(zone.target_max_temp) if zone else None

    in_range = True
    if zone and latest:
        in_range = zone.target_min_temp <= latest.temperature <= zone.target_max_temp

    return Response({
        'has_cold_chain': True,
        'readings_available': True,
        'current_temp': float(latest.temperature),
        'last_reading_at': latest.timestamp.isoformat(),
        'min_temp': float(agg['min_temp']),
        'max_temp': float(agg['max_temp']),
        'avg_temp': round(float(agg['avg_temp']), 1),
        'target_min': target_min,
        'target_max': target_max,
        'status': 'ok' if in_range else 'alert',
        'zone_name': zone.name if zone else None,
    })
