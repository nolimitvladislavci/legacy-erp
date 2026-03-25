"""
rental/ai_assistant.py — AI dnevni sažetak + upozorenja za iznajmljivača

Pravni štit: Nikad ne savjetujemo. Samo informiramo.
"""
import logging
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)

PAUSAL_LIMIT = Decimal('40000')


def generate_landlord_daily_brief(company) -> str:
    """Haiku generira dnevni sažetak. Celery beat poziva svako jutro 08:00."""
    from rental.models import Booking
    from datetime import timedelta

    today = timezone.now().date()

    arrivals = Booking.objects.filter(
        rental_property__company=company, check_in=today,
        status__in=['confirmed', 'pending'],
    ).count()

    departures = Booking.objects.filter(
        rental_property__company=company, check_out=today,
        status='checked_in',
    ).count()

    active = Booking.objects.filter(
        rental_property__company=company, status='checked_in',
    ).count()

    week_end = today + timedelta(days=7)
    week_bookings = Booking.objects.filter(
        rental_property__company=company,
        check_in__gte=today, check_in__lte=week_end,
        status__in=['confirmed', 'pending'],
    )
    week_revenue = week_bookings.aggregate(s=Sum('total_price'))['s'] or Decimal('0')

    ytd = Booking.objects.filter(
        rental_property__company=company,
        check_out__year=today.year,
        status__in=['checked_out', 'checked_in'],
    ).aggregate(s=Sum('total_price'))['s'] or Decimal('0')

    pct = int(ytd / PAUSAL_LIMIT * 100) if PAUSAL_LIMIT else 0

    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            messages=[{'role': 'user', 'content': (
                f'Kratki jutarnji sažetak za iznajmljivača ({today}):\n'
                f'- Dolasci: {arrivals}, Odlasci: {departures}, Aktivni: {active}\n'
                f'- Tjedan: {week_revenue:.0f}€, YTD: {ytd:.0f}€ ({pct}% od 40.000€)\n'
                f'Max 4 rečenice, HR jezik, samo informiraj ne savjetuj.\n'
                f'Ako dolasci > 0 → podsjeti na eVisitor 24h rok.\n'
                f'Ako YTD > 35.000€ → istakni upozorenje o pragu.'
            )}],
        )
        return msg.content[0].text
    except Exception as e:
        logger.warning('AI brief generation failed: %s', e)
        # Fallback: structured text
        lines = [f'Dobro jutro! Danas {today.strftime("%d.%m.%Y")}:']
        if arrivals:
            lines.append(f'Dolasci: {arrivals} (eVisitor prijava u roku 24h!)')
        if departures:
            lines.append(f'Odlasci: {departures}')
        if active:
            lines.append(f'Aktivni gosti: {active}')
        lines.append(f'YTD prihod: {ytd:.0f}€ ({pct}% praga)')
        if pct >= 80:
            lines.append(f'UPOZORENJE: Blizu 40.000€ praga!')
        return '\n'.join(lines)


def check_annual_limit_warning(company) -> dict:
    """Provjeri blizinu 40.000€ paušalnog praga."""
    from rental.models import Booking

    year = timezone.now().year
    ytd = Booking.objects.filter(
        rental_property__company=company,
        check_out__year=year,
        status__in=['checked_out', 'checked_in'],
    ).aggregate(s=Sum('total_price'))['s'] or Decimal('0')

    remaining = PAUSAL_LIMIT - ytd
    pct = int(ytd / PAUSAL_LIMIT * 100) if PAUSAL_LIMIT else 0

    result = {
        'ytd': ytd, 'limit': PAUSAL_LIMIT,
        'remaining': remaining, 'percent': pct,
        'warning_level': None, 'message': None,
    }

    if pct >= 95:
        result['warning_level'] = 'CRITICAL'
        result['message'] = (
            f'UPOZORENJE: {pct}% godišnjeg praga ({ytd:.0f}€ od 40.000€). '
            f'Preostalo {remaining:.0f}€ do obveze PDV-a i poslovnih knjiga!'
        )
    elif pct >= 80:
        result['warning_level'] = 'HIGH'
        result['message'] = f'Pažnja: {pct}% praga ({ytd:.0f}€). Ostalo {remaining:.0f}€.'
    elif pct >= 60:
        result['warning_level'] = 'MEDIUM'
        result['message'] = f'Informativno: {pct}% praga ostvareno ({ytd:.0f}€).'

    return result
