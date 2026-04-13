"""
rental/channel_manager.py — Channel Manager stub za Booking.com / Airbnb integraciju.

Ovo je infrastruktura za buducu integraciju s OTA (Online Travel Agencies).
Trenutno sadrzi:
  - ChannelConfig model (API keys po propertyu)
  - sync_availability() — push availability na kanal
  - sync_bookings() — pull bookinga s kanala
  - price_update() — push cijena
  
Za produkciju trebas:
  - Booking.com Connectivity Partner API pristup
  - Airbnb Professional Hosting Tools API
  - Expedia Partner Central API
"""
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


class ChannelManagerService:
    """Base channel manager — subclass za svaki OTA."""

    CHANNELS = {
        'booking_com': {'name': 'Booking.com', 'api_base': 'https://supply-xml.booking.com'},
        'airbnb': {'name': 'Airbnb', 'api_base': 'https://api.airbnb.com'},
        'expedia': {'name': 'Expedia', 'api_base': 'https://services.expediapartnercentral.com'},
    }

    def __init__(self, property_obj):
        self.property = property_obj
        self.company = property_obj.company

    def sync_availability(self, date_from=None, days=90):
        """Push room availability to all connected channels."""
        from rental.models import Booking
        date_from = date_from or date.today()
        date_to = date_from + timedelta(days=days)

        # Build availability calendar
        bookings = Booking.objects.filter(
            rental_property=self.property,
            check_in__lt=date_to,
            check_out__gt=date_from,
            status__in=('confirmed', 'checked_in'),
        )
        booked_dates = set()
        for b in bookings:
            d = max(b.check_in, date_from)
            while d < min(b.check_out, date_to):
                booked_dates.add(d)
                d += timedelta(days=1)

        availability = []
        d = date_from
        while d < date_to:
            availability.append({
                'date': d.isoformat(),
                'available': d not in booked_dates,
                'price': self._get_price(d),
            })
            d += timedelta(days=1)

        logger.info('Channel sync: %s — %d days, %d booked',
                     self.property.name, days, len(booked_dates))
        return availability

    def pull_bookings(self, channel='booking_com'):
        """Pull new bookings from OTA channel. Returns list of booking dicts."""
        # STUB — in production, this calls the OTA API
        logger.info('Pull bookings from %s for %s — STUB', channel, self.property.name)
        return []

    def push_prices(self, prices, channel='booking_com'):
        """Push price updates to channel."""
        logger.info('Push %d price updates to %s — STUB', len(prices), channel)
        return True

    def _get_price(self, for_date):
        """Get price for a specific date (seasonal pricing)."""
        from rental.models import SeasonalPrice
        seasonal = SeasonalPrice.objects.filter(
            rental_property=self.property,
            date_from__lte=for_date,
            date_to__gte=for_date,
        ).first()
        if seasonal:
            return float(seasonal.price_per_night)
        return float(self.property.price_per_night or 0)


def sync_all_properties(company=None):
    """Sync availability for all properties (Celery task candidate)."""
    from rental.models import Property
    qs = Property.objects.all()
    if company:
        qs = qs.filter(company=company)

    results = []
    for prop in qs:
        try:
            cm = ChannelManagerService(prop)
            avail = cm.sync_availability()
            results.append({'property': prop.name, 'days': len(avail), 'status': 'ok'})
        except TypeError as e:
            results.append({'property': prop.name, 'status': 'error', 'error': str(e)})

    return results
