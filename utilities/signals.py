"""
utilities/signals.py — Auto-link Arhiva → UtilityBill + anomaly WhatsApp.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger('utilities')


@receiver(post_save, sender='documents.ArhivaEntry')
def auto_link_utility_bill(sender, instance, created, **kwargs):
    """
    When Arhiva processes a new document, check if it matches a utility contract.
    If yes, create a pending UtilityBill automatically.
    """
    if not created:
        return

    try:
        from utilities.models import UtilityBill, UtilityContract
        company = instance.company
        if not company:
            return

        # Get document text for keyword matching
        text = ' '.join([
            getattr(instance, 'original_filename', '') or '',
            getattr(instance, 'ai_description', '') or '',
            getattr(instance, 'sender_name', '') or '',
            getattr(instance, 'ai_summary', '') or '',
        ]).lower()

        if not text.strip():
            return

        # Match against active contracts' keywords
        for contract in UtilityContract.objects.filter(company=company, is_active=True):
            keywords = [k.strip().lower() for k in (contract.archiva_keywords or '').split(',') if k.strip()]
            if not keywords:
                continue

            if any(kw in text for kw in keywords):
                # Check if already linked
                if UtilityBill.objects.filter(archiva_document=instance).exists():
                    return

                # Extract amounts from AI if available
                total = getattr(instance, 'ai_amount', None) or 0
                tax = 0
                if total:
                    from decimal import Decimal
                    total = Decimal(str(total))
                    tax = (total * Decimal('0.2')).quantize(Decimal('0.01'))  # Estimate 20% VAT
                    subtotal = total - tax
                else:
                    subtotal = total = Decimal('0')

                from django.utils import timezone
                bill = UtilityBill.objects.create(
                    contract=contract,
                    company=company,
                    period_from=timezone.now().date().replace(day=1),
                    period_to=timezone.now().date(),
                    issue_date=timezone.now().date(),
                    subtotal=subtotal,
                    tax_amount=tax,
                    total=total,
                    archiva_document=instance,
                    invoice_number=getattr(instance, 'original_filename', '')[:100],
                    status='pending',
                )

                # Anomaly detection
                is_anomaly = bill.detect_anomaly()

                # WhatsApp alert if anomaly
                if is_anomaly:
                    _send_anomaly_alert(company, contract, bill)

                logger.info(
                    'Auto-linked Arhiva %s → UtilityBill %s (%s) anomaly=%s',
                    instance.pk, bill.pk, contract.provider_name, is_anomaly
                )
                return  # Linked to first matching contract

    except Exception as e:
        logger.warning('Utility auto-link failed: %s', e)


def _send_anomaly_alert(company, contract, bill):
    """Send WhatsApp/notification for utility anomaly."""
    try:
        from core.notify import notify
        msg = (
            f"⚠️ *Anomalija režija*\n\n"
            f"*{contract.get_utility_type_display()}* — {contract.provider_name}\n"
            f"Račun: {bill.total:.2f} EUR\n"
            f"Prosjek: {bill.avg_monthly:.2f} EUR\n"
            f"Odstupanje: {bill.deviation_pct:+.0f}%\n\n"
            f"Provjerite račun u režijama."
        )
        notify('WARN', msg)
    except ImportError as e:
        logger.warning('Anomaly alert failed: %s', e)
