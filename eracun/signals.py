"""
Signal: ERacun status → 'accepted' → auto-create JournalEntry in konto.

Knjizenje:
  Duguje: 1200 (Potraživanja od kupaca) — bruto iznos
  Potrazuje: 7500 (Prihodi od prodaje) — neto iznos
  Potrazuje: 2400 (Obveze za PDV) — PDV iznos
"""

from decimal import Decimal

from django.db import DatabaseError
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(pre_save, sender="eracun.ERacun")
def eracun_accepted_to_journal(sender, instance, **kwargs):
    """When ERacun status changes to 'accepted', create JournalEntry."""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    # Only trigger when status changes TO accepted
    if old.status == instance.status or instance.status != "accepted":
        return

    # B-23: Guard — skip journal ako tvrtka nema konto kontni plan
    try:
        from konto.models import KontoAccount

        if not KontoAccount.objects.filter(company=instance.company).exists():
            return  # Nema kontnog plana — tiho preskoči
    except DatabaseError:
        return

    try:
        _create_journal_entry(instance)
    except Exception:
        # Don't block e-racun acceptance if konto booking fails
        import logging

        logging.getLogger("eracun.signals").exception("Failed to create JournalEntry for ERacun %s", instance.pk)


def _create_journal_entry(eracun):
    """Create a balanced JournalEntry for an accepted e-Racun."""
    from konto.models import JournalEntry, KontoAccount, LedgerLine

    company = eracun.company
    now = timezone.now()

    # Get or create standard konto accounts
    acct_receivable, _ = KontoAccount.objects.get_or_create(
        company=company, code="1200", defaults={"name": "Potraživanja od kupaca", "account_type": "asset"}
    )
    acct_revenue, _ = KontoAccount.objects.get_or_create(
        company=company, code="7500", defaults={"name": "Prihodi od prodaje robe i usluga", "account_type": "revenue"}
    )
    acct_vat, _ = KontoAccount.objects.get_or_create(
        company=company, code="2400", defaults={"name": "Obveze za PDV", "account_type": "liability"}
    )

    # Amounts
    total = eracun.total or Decimal("0")
    tax = eracun.tax_amount or Decimal("0")
    net = total - tax

    if total <= 0:
        return

    # Generate entry number
    count = JournalEntry.objects.filter(company=company, date__year=now.year).count() + 1
    entry_number = "ER-{}-{:04d}".format(now.year, count)

    # Check for duplicate
    if JournalEntry.objects.filter(company=company, entry_number=entry_number, source_type="invoice").exists():
        return

    je = JournalEntry.objects.create(
        company=company,
        entry_number=entry_number,
        date=eracun.accepted_at.date() if eracun.accepted_at else now.date(),
        description="e-Račun {} — {}".format(eracun.invoice_number, eracun.recipient_name),
        source_type="invoice",
        is_posted=True,
    )

    # Debit: Receivables (full amount)
    LedgerLine.objects.create(
        journal_entry=je,
        account=acct_receivable,
        side="debit",
        amount=total,
        description=eracun.recipient_name,
    )

    # Credit: Revenue (net amount)
    if net > 0:
        LedgerLine.objects.create(
            journal_entry=je,
            account=acct_revenue,
            side="credit",
            amount=net,
            description="Prihod: {}".format(eracun.invoice_number),
        )

    # Credit: VAT (tax amount)
    if tax > 0:
        LedgerLine.objects.create(
            journal_entry=je,
            account=acct_vat,
            side="credit",
            amount=tax,
            description="PDV: {}".format(eracun.invoice_number),
        )
