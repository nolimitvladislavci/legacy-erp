"""
AML Guard — Anti-Money Laundering provjera za udruge.
ZSPNFT (NN 108/17) — prag 10.000 EUR za dubinsku analizu.

Usage:
    from udruge.aml_guard import AMLGuard
    status, msg = AMLGuard.check_donation(donacija)
"""
import logging
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger('udruge.aml')

# Zakonski pragovi
AML_SINGLE_THRESHOLD = Decimal('10000.00')  # Jedna transakcija >= 10k
AML_ANNUAL_THRESHOLD = Decimal('10000.00')  # Kumulativno od istog donatora >= 10k
AML_CASH_THRESHOLD = Decimal('1000.00')     # Gotovina >= 1k trazi evidenciju
AML_CRYPTO_THRESHOLD = Decimal('1000.00')   # Crypto >= 1k = pojacani nadzor


class AMLGuard:
    """Automatska AML provjera za donacije udrugama."""

    @classmethod
    def check_donation(cls, donacija):
        """
        Provjeri donaciju protiv AML pravila.
        Poziva se PRIJE spremanja donacije ili pri primanju uplate.

        Returns: (aml_status, message)
        """
        flags = []

        # 1. Pojedinacna donacija >= 10.000 EUR
        if donacija.amount >= AML_SINGLE_THRESHOLD:
            flags.append('Donacija >= %s EUR — obvezna dubinska analiza (KYC)' % AML_SINGLE_THRESHOLD)

        # 2. Kumulativno od istog donatora >= 10.000 EUR u kalendarskoj godini
        if donacija.donor_oib:
            from udruge.models import Donacija
            year = donacija.date.year if donacija.date else timezone.now().year
            cumulative = Donacija.objects.filter(
                company=donacija.company,
                donor_oib=donacija.donor_oib,
                date__year=year,
                aml_status__in=['clear', 'review'],
            ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

            total_projected = cumulative + donacija.amount
            if total_projected >= AML_ANNUAL_THRESHOLD:
                flags.append(
                    'Kumulativne donacije od OIB %s = %s EUR (prag: %s EUR)' % (
                        donacija.donor_oib, total_projected, AML_ANNUAL_THRESHOLD,
                    )
                )

        # 3. Anonimna donacija (bez OIB-a) >= 1.000 EUR
        if not donacija.donor_oib and donacija.amount >= AML_CASH_THRESHOLD:
            flags.append('Anonimna donacija >= %s EUR bez OIB-a donatora' % AML_CASH_THRESHOLD)

        # 4. Crypto donacija >= 1.000 EUR
        if donacija.donor_type == 'anonimno' and donacija.amount >= AML_CRYPTO_THRESHOLD:
            flags.append('Anonimna/crypto donacija >= %s EUR — pojacani nadzor' % AML_CRYPTO_THRESHOLD)

        # Odluka
        if not flags:
            return 'clear', 'Donacija unutar zakonskih limita.'

        reason = ' | '.join(flags)

        if donacija.amount >= AML_SINGLE_THRESHOLD:
            status = 'kyc_pending'
            cls._send_alert(donacija, reason)
        else:
            status = 'review'

        # Update donacija
        donacija.aml_status = status
        donacija.aml_flag_reason = reason[:255]
        donacija.aml_flagged_at = timezone.now()

        logger.warning('AML FLAG [%s]: %s — %s EUR od %s. Razlog: %s',
                       status, donacija.company.name, donacija.amount,
                       donacija.donor_name, reason)

        return status, reason

    @classmethod
    def _send_alert(cls, donacija, reason):
        """Posalji hitan alarm superadminu."""
        try:
            from django.core.mail import mail_admins
            mail_admins(
                subject='AML ALERT: Donacija %s EUR — %s' % (donacija.amount, donacija.company.name),
                message=(
                    'AUTOMATSKI AML ALARM\n\n'
                    'Tvrtka: %s (OIB: %s)\n'
                    'Donator: %s (OIB: %s)\n'
                    'Iznos: %s EUR\n'
                    'Datum: %s\n'
                    'Razlog: %s\n\n'
                    'AKCIJA: Provesti dubinsku analizu (KYC) prije prihvacanja donacije.\n'
                    'Zakonska osnova: ZSPNFT cl. 16 (NN 108/17)'
                ) % (
                    donacija.company.name, donacija.company.oib,
                    donacija.donor_name, donacija.donor_oib or 'ANONIMNO',
                    donacija.amount, donacija.date,
                    reason,
                ),
                fail_silently=True,
            )
        except ImportError as e:
            logger.error('AML alert email failed: %s', e)

    @classmethod
    def bulk_check_year(cls, company, year=None):
        """Godisnja provjera svih donacija — za audit."""
        if year is None:
            year = timezone.now().year

        from udruge.models import Donacija
        donacije = Donacija.objects.filter(company=company, date__year=year)

        results = {'clear': 0, 'review': 0, 'kyc_pending': 0, 'blocked': 0}
        for d in donacije:
            status, _ = cls.check_donation(d)
            d.save(update_fields=['aml_status', 'aml_flag_reason', 'aml_flagged_at'])
            results[status] = results.get(status, 0) + 1

        return results
