"""
Propter signali -- automatske veze prema ostalim modulima.

Signali:
    POSReceipt(status=paid) --> create_from_pos_receipt()
    Invoice(status=SENT)    --> create_from_invoice()
    BillingPeriod(INVOICED) --> EkoStats.calculate()
    PayrollRun(PAID)        --> knjizenje u konto (buducnost)
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger("propter.signals")


def connect_pos_signal():
    try:
        from pos.models import POSReceipt
        from propter.services.aggregate import create_from_pos_receipt

        @receiver(post_save, sender=POSReceipt, weak=False, dispatch_uid="propter_pos_receipt_to_otpremnica")
        def pos_receipt_to_otpremnica(sender, instance, created, **kwargs):
            if instance.status == "paid":
                try:
                    create_from_pos_receipt(instance)
                except Exception as e:
                    logger.warning("Signal POS->Otpremnica greska (bon %s): %s", instance.pk, e)
    except ImportError as e:
        logger.debug("POS signal nije registriran: %s", e)


def connect_invoice_signal():
    try:
        from invoicing.models import Invoice
        from propter.services.aggregate import create_from_invoice

        @receiver(post_save, sender=Invoice, weak=False, dispatch_uid="propter_invoice_to_otpremnica")
        def invoice_to_otpremnica(sender, instance, created, **kwargs):
            # Samo B2B fakture koje idu na e-Racun
            if instance.status == "SENT" and getattr(instance, "client_oib", ""):
                try:
                    create_from_invoice(instance)
                except Exception as e:
                    logger.warning("Signal Invoice->Otpremnica greska (%s): %s", instance.pk, e)
    except ImportError as e:
        logger.debug("Invoice signal nije registriran: %s", e)


# Registriraj signale
connect_pos_signal()
connect_invoice_signal()
