from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Transaction


@receiver(post_save, sender=Transaction)
def transaction_post_save(sender, instance, created, **kwargs):
    # 1. Ažuriraj saldo partnera
    if instance.partner:
        instance.partner.update_balance()

    # 2. Provjeri status dokumenta
    if instance.document:
        check_document_status(instance.document)


@receiver(post_delete, sender=Transaction)
def transaction_post_delete(sender, instance, **kwargs):
    if instance.partner:
        instance.partner.update_balance()

    if instance.document:
        check_document_status(instance.document)


def check_document_status(document):
    """Provjerava je li suma transakcija pokrila iznos dokumenta"""
    paid_amount = document.transactions.aggregate(Sum("amount"))["amount__sum"] or 0
    # Ako je plaćeno >= iznos računa (tolerancija 0.01 zbog decimala)
    if paid_amount >= (document.total_amount - 0.01):
        if not document.is_paid:
            document.is_paid = True
            document.save(update_fields=["is_paid"])
    else:
        if document.is_paid:
            document.is_paid = False
            document.save(update_fields=["is_paid"])


# ── Finance → Konto bridge ───────────────────────────────────────────────────
def _sync_to_konto(instance, delete=False):
    # Sync finance.Transaction -> konto.BankTransaction
    # Runs inside try/except so it never breaks finance saves
    try:
        from konto.models import BankAccount, BankTransaction

        ext_id = "finance-{}".format(instance.pk)
        if delete:
            BankTransaction.objects.filter(external_id=ext_id).delete()
            return
        # Find primary bank account for company
        ba = None
        if instance.payment_account:
            # Try matching by IBAN
            ba = BankAccount.objects.filter(
                company=instance.company, iban__icontains=instance.payment_account[:10]
            ).first()
        if not ba:
            ba = BankAccount.objects.filter(company=instance.company, is_primary=True).first()
        if not ba:
            ba = BankAccount.objects.filter(company=instance.company).first()
        if not ba:
            return  # No bank account configured — skip silently
        txn_type = "inflow" if instance.direction == "income" else "outflow"
        counterparty = ""
        if instance.partner_id:
            try:
                counterparty = instance.partner.name
            except Exception:
                pass
        ref = ""
        if instance.invoice_id:
            try:
                ref = instance.invoice.number
            except Exception:
                pass
        if not ref:
            ref = instance.reference or ""
        # Upsert: update if exists, create if not
        BankTransaction.objects.update_or_create(
            external_id=ext_id,
            defaults=dict(
                bank_account=ba,
                company=instance.company,
                transaction_date=instance.date,
                value_date=instance.value_date or instance.date,
                amount=abs(__import__("decimal").Decimal(str(instance.amount))),
                transaction_type=txn_type,
                counterparty_name=counterparty[:300],
                description=instance.description[:500] if instance.description else "",
                reference_number=ref[:100],
                import_batch="finance-sync",
                status="matched" if instance.is_reconciled else "unmatched",
                matched_invoice=instance.invoice if instance.invoice_id else None,
            ),
        )
        ba.recalculate_balance()
    except (ValueError, TypeError):
        pass  # Never break finance saves due to konto sync


@receiver(post_save, sender=Transaction)
def sync_finance_to_konto(sender, instance, **kwargs):
    _sync_to_konto(instance)


@receiver(post_delete, sender=Transaction)
def unsync_finance_from_konto(sender, instance, **kwargs):
    _sync_to_konto(instance, delete=True)
