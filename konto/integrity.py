"""
LedgerLine integrity hash chain (GoBD/audit compliance).

Each LedgerLine gets a SHA-256 hash computed from:
  - line ID
  - account code
  - side (debit/credit)
  - amount
  - journal entry number
  - journal entry date
  - previous hash in the chain (per company)

This creates an immutable hash chain — any retroactive modification
of a booked entry breaks the chain and is immediately detectable.
"""

import hashlib

from django.db.models.signals import post_save
from django.dispatch import receiver


def compute_hash(line, previous_hash=""):
    """Compute SHA-256 integrity hash for a LedgerLine."""
    je = line.journal_entry
    payload = "|".join(
        [
            str(line.id),
            str(line.account.code),
            line.side,
            str(line.amount),
            je.entry_number,
            str(je.date),
            previous_hash,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_previous_hash(company_id, exclude_line_id=None):
    """Get the latest integrity_hash for a company's ledger chain."""
    from konto.models import LedgerLine

    qs = LedgerLine.objects.filter(
        journal_entry__company_id=company_id,
        integrity_hash__gt="",
    ).order_by("-id")
    if exclude_line_id:
        qs = qs.exclude(id=exclude_line_id)
    latest = qs.first()
    return latest.integrity_hash if latest else ""


@receiver(post_save, sender="konto.LedgerLine")
def set_integrity_hash(sender, instance, created, **kwargs):
    """After saving a LedgerLine, compute and store its integrity hash."""
    if not created:
        return  # Only hash new entries, never rehash
    if instance.integrity_hash:
        return  # Already hashed

    prev = get_previous_hash(instance.journal_entry.company_id, exclude_line_id=instance.id)
    h = compute_hash(instance, prev)
    # Direct update to avoid recursion
    sender.objects.filter(pk=instance.pk).update(integrity_hash=h)


def verify_chain(company):
    """Verify the entire hash chain for a company. Returns (valid, broken_at_id)."""
    from konto.models import LedgerLine

    lines = (
        LedgerLine.objects.filter(
            journal_entry__company=company,
            integrity_hash__gt="",
        )
        .select_related("account", "journal_entry")
        .order_by("id")
    )

    prev_hash = ""
    for line in lines:
        expected = compute_hash(line, prev_hash)
        if line.integrity_hash != expected:
            return False, line.id
        prev_hash = line.integrity_hash

    return True, None
