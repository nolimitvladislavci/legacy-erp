"""
VolunteerTaxGuard — AI Porezni inspektor za volontere.

Stiti udrugu od probijanja neoporezivih limita (cca 238.90 EUR/god).
Poziva se pri odobravanju putnih naloga i naknada volonterima.

Usage:
    from worktime.services.volunteer_guard import VolunteerTaxGuard
    ok, msg = VolunteerTaxGuard.check_expense(travel_order)
"""
import logging
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger('worktime.volunteer')


class VolunteerTaxGuard:
    """Matematicki garantira da volonter ne dobije vise od zakonskog limita."""

    @classmethod
    def check_expense(cls, travel_order):
        """
        Provjeri smije li se odobriti putni nalog volontera.
        Returns: (bool, str) — (odobreno, poruka)
        """
        profile = getattr(travel_order.employee, 'employeeprofile', None)
        if not profile or not profile.is_volunteer:
            return True, 'Odobreno (nije volonter).'

        # Provjeri ugovor
        if not profile.volunteer_contract_date:
            cls._create_anomaly(
                travel_order, 'VOLUNTEER_NO_CONTRACT',
                'Volonter %s nema ugovor o volontiranju!' % travel_order.employee
            )
            return False, 'Volonter nema evidentiran ugovor o volontiranju.'

        current_year = timezone.now().year
        from worktime.models import TravelOrder

        # Koliko je vec isplaceno ove godine?
        already_paid = TravelOrder.objects.filter(
            employee=travel_order.employee,
            status='completed',
            departure_date__year=current_year,
        ).aggregate(total=Sum('total_cost'))['total'] or Decimal('0.00')

        requested = getattr(travel_order, 'total_cost', Decimal('0')) or Decimal('0')
        projected = already_paid + requested
        limit = profile.volunteer_annual_limit

        if projected > limit:
            remaining = max(Decimal('0'), limit - already_paid)
            cls._create_anomaly(
                travel_order, 'VOLUNTEER_LIMIT',
                'BLOKIRANO: Isplata PN #%s (%s EUR) bi probila godisnji limit volontera '
                '(%s EUR). Dosad isplaceno: %s EUR. Preostalo: %s EUR.' % (
                    getattr(travel_order, 'order_number', travel_order.pk),
                    requested, limit, already_paid, remaining,
                )
            )
            return False, 'Probijen limit! Preostali dozvoljeni iznos: %s EUR.' % remaining

        return True, 'Odobreno. Unutar zakonskih limita (%s/%s EUR).' % (projected, limit)

    @classmethod
    def get_volunteer_stats(cls, user, year=None):
        """Dohvati statistiku volontera za godinu."""
        if year is None:
            year = timezone.now().year

        profile = getattr(user, 'employeeprofile', None)
        if not profile or not profile.is_volunteer:
            return None

        from worktime.models import TravelOrder, TimeEntry

        paid = TravelOrder.objects.filter(
            employee=user, status='completed',
            departure_date__year=year,
        ).aggregate(total=Sum('total_cost'))['total'] or Decimal('0')

        hours = TimeEntry.objects.filter(
            user=user, is_volunteer_work=True,
            date__year=year, status='APPROVED',
        ).aggregate(total=Sum('duration'))['total'] or Decimal('0')

        grant_value = TimeEntry.objects.filter(
            user=user, is_volunteer_work=True,
            date__year=year, status='APPROVED',
        ).aggregate(total=Sum('grant_monetary_value'))['total'] or Decimal('0')

        return {
            'year': year,
            'total_hours': hours,
            'grant_monetary_value': grant_value,
            'expenses_paid': paid,
            'expense_limit': profile.volunteer_annual_limit,
            'expense_remaining': max(Decimal('0'), profile.volunteer_annual_limit - paid),
            'hourly_value': profile.volunteer_hourly_value,
        }

    @classmethod
    def monetize_time_entry(cls, time_entry):
        """Automatski monetiziraj volonterski sat za EU fondove."""
        profile = getattr(time_entry.user, 'employeeprofile', None)
        if not profile or not profile.is_volunteer:
            return

        time_entry.is_volunteer_work = True
        if time_entry.duration:
            time_entry.grant_monetary_value = (
                time_entry.duration * profile.volunteer_hourly_value
            )

    @classmethod
    def _create_anomaly(cls, travel_order, anomaly_type, description):
        """Kreiraj AnomalyReport za volonterski prekrsaj."""
        try:
            from worktime.models import AnomalyReport
            AnomalyReport.objects.create(
                user=travel_order.employee,
                company=getattr(travel_order, 'company', None),
                anomaly_type=anomaly_type,
                severity='high',
                description=description,
                ai_confidence=Decimal('100.00'),
            )
        except Exception as e:
            logger.warning('AnomalyReport create failed: %s', e)
