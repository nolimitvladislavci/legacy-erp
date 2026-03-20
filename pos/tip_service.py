"""
Napojnice tracking — HR zakonski limit + DE Trinkgeld razlikovanje.

HR (od 01.01.2024): Napojnice se fiskaliziraju, neoporezivo do 3.360 EUR/god po zaposleniku.
DE (KassenSichV): Arbeitnehmer-Trinkgeld = neoporezivo, Unternehmer-Trinkgeld = PDV.

Usage:
    from pos.tip_service import TipTracker
    stats = TipTracker.get_annual_tips(user, year=2026)
    ok, msg = TipTracker.check_tip_limit(user, new_tip_amount)
"""
import logging
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone

logger = logging.getLogger('pos.tips')

# HR: neoporezivi limit napojnica po zaposleniku godisnje
HR_TIP_ANNUAL_LIMIT = Decimal('3360.00')  # EUR (NN 156/2023)

# DE: napojnice zaposlenika su potpuno neoporezive (bez limita)
# DE: napojnice vlasnika podlijezu PDV-u


class TipTracker:

    @classmethod
    def get_annual_tips(cls, user, year=None):
        """Godisnji pregled napojnica po zaposleniku."""
        if year is None:
            year = timezone.now().year

        from pos.models import POSReceiptItem
        tips = POSReceiptItem.objects.filter(
            is_tip=True,
            receipt__status='paid',
            receipt__paid_at__year=year,
        )

        # Filter by cashier or session operator
        from pos.models import POSCashier
        cashier = POSCashier.objects.filter(user=user).first()
        if cashier:
            tips = tips.filter(receipt__cashier=cashier)
        else:
            tips = tips.filter(receipt__session__operator=user)

        total = tips.aggregate(s=Sum('unit_price'))['s'] or Decimal('0')
        employer_tips = tips.filter(is_tip_employer=True).aggregate(
            s=Sum('unit_price'))['s'] or Decimal('0')
        employee_tips = total - employer_tips

        return {
            'year': year,
            'total': total,
            'employee_tips': employee_tips,  # Neoporezivo (do limita)
            'employer_tips': employer_tips,  # Oporezivo (PDV)
            'limit': HR_TIP_ANNUAL_LIMIT,
            'remaining': max(Decimal('0'), HR_TIP_ANNUAL_LIMIT - employee_tips),
            'over_limit': max(Decimal('0'), employee_tips - HR_TIP_ANNUAL_LIMIT),
            'tax_due_on_excess': max(Decimal('0'), (employee_tips - HR_TIP_ANNUAL_LIMIT) * Decimal('0.20')),
        }

    @classmethod
    def check_tip_limit(cls, user, new_tip_amount, year=None):
        """Provjeri hoce li nova napojnica probiti godisnji limit."""
        stats = cls.get_annual_tips(user, year)
        projected = stats['employee_tips'] + new_tip_amount

        if projected > HR_TIP_ANNUAL_LIMIT:
            excess = projected - HR_TIP_ANNUAL_LIMIT
            return False, (
                'Napojnica bi probila godisnji limit! '
                'Dosad: %s EUR, novo: %s EUR, limit: %s EUR. '
                'Visak od %s EUR podlijeze porezu 20%%.' % (
                    stats['employee_tips'], new_tip_amount,
                    HR_TIP_ANNUAL_LIMIT, excess,
                )
            )
        return True, 'OK (%s/%s EUR)' % (projected, HR_TIP_ANNUAL_LIMIT)
