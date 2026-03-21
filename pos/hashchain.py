"""
POS Hash Chain — Kriptografski audit trail bez blockchaina.

Svaki fiskalizirani bon dobije hash koji uključuje:
1. Vlastite podatke (receipt_number, total, ZKI, JIR, timestamp)
2. Hash prethodnog bona u lancu

Rezultat: nepromjenjiv lanac unutar PostgreSQL-a.
Ako netko promijeni stari bon, svi kasniji hashevi se raspadaju.
Porezna revizija može verificirati integritet CIJELE povijesti u 1 sekundi.

Princip: Bitcoin mining bez minanja. Merkle chain bez distribuiranog konsenzusa.
GDPR: hash ≠ osobni podatak. SHA256 je jednosmjerna funkcija.

Opcija: dnevni anchor hash → OpenTimestamps (Bitcoin) za neoboriv dokaz.
"""
import hashlib
import json
import logging
from datetime import datetime
from decimal import Decimal

from django.db import models
from django.utils import timezone as tz

logger = logging.getLogger('pos_hashchain')


class ChainLink(models.Model):
    """
    Jedna karika u hash lancu.
    prev_hash + payload_hash = chain_hash (SHA256).
    Ako se BILO ŠTO promijeni u bilo kojoj karici, lanac puca od te točke.
    """
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='chain_links',
    )
    sequence = models.PositiveBigIntegerField(db_index=True)
    receipt = models.OneToOneField(
        'pos.POSReceipt', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='chain_link',
    )
    # Hash data
    payload_hash = models.CharField(max_length=64, verbose_name='SHA256 payload')
    prev_hash = models.CharField(max_length=64, verbose_name='Hash prethodne karike')
    chain_hash = models.CharField(max_length=64, unique=True, verbose_name='Hash ove karike')
    # Metadata
    payload_summary = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=tz.now)

    class Meta:
        verbose_name = 'Hash Chain Link'
        verbose_name_plural = 'Hash Chain Links'
        ordering = ['company', 'sequence']
        unique_together = [('company', 'sequence')]

    def __str__(self):
        return f'#{self.sequence} {self.chain_hash[:12]}… → {self.payload_summary}'


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def _receipt_payload(receipt) -> str:
    """Deterministički string iz receipt podataka."""
    items_hash = _sha256('|'.join(
        f'{i.description}:{i.quantity}:{i.unit_price}:{i.tax_rate}'
        for i in receipt.items.order_by('pk').all()
    ))
    return '|'.join([
        str(receipt.receipt_number),
        str(receipt.total),
        str(receipt.subtotal),
        str(receipt.tax_amount),
        receipt.zki or '',
        receipt.jir or '',
        receipt.paid_at.isoformat() if receipt.paid_at else '',
        receipt.status,
        str(receipt.session.terminal.terminal_code),
        items_hash,
    ])


def append_receipt(receipt):
    """
    Dodaj bon u hash chain.
    Poziva se nakon uspješne fiskalizacije ili naplate.
    Thread-safe: unique_together na (company, sequence).
    """
    company = receipt.session.terminal.company

    # Nadi zadnju kariku za ovu firmu
    last = ChainLink.objects.filter(company=company).order_by('-sequence').first()
    prev_hash = last.chain_hash if last else ('0' * 64)  # Genesis
    next_seq = (last.sequence + 1) if last else 1

    # Izračunaj hash
    payload = _receipt_payload(receipt)
    payload_hash = _sha256(payload)
    chain_hash = _sha256(f'{prev_hash}:{payload_hash}:{next_seq}')

    link = ChainLink.objects.create(
        company=company,
        sequence=next_seq,
        receipt=receipt,
        payload_hash=payload_hash,
        prev_hash=prev_hash,
        chain_hash=chain_hash,
        payload_summary=f'Bon #{receipt.receipt_number} | {receipt.total} EUR | {receipt.status}',
    )

    logger.info(
        'Chain #%d: %s (prev: %s…)',
        next_seq, chain_hash[:16], prev_hash[:8],
    )
    return link


def verify_chain(company, verbose=False):
    """
    Verificiraj integritet cijelog lanca za firmu.
    Vraća (is_valid, break_point, total_links).
    O(n) — ali n je rijedak (1 query, stream).
    """
    links = ChainLink.objects.filter(company=company).order_by('sequence')

    prev_hash = '0' * 64  # Genesis
    total = 0
    for link in links.iterator():
        total += 1
        expected = _sha256(f'{prev_hash}:{link.payload_hash}:{link.sequence}')
        if expected != link.chain_hash:
            if verbose:
                logger.error(
                    'CHAIN BROKEN at #%d! Expected %s, got %s',
                    link.sequence, expected[:16], link.chain_hash[:16],
                )
            return False, link.sequence, total
        prev_hash = link.chain_hash

    return True, None, total


def verify_single(receipt):
    """Brza provjera jednog bona — recompute payload hash i usporedi."""
    try:
        link = receipt.chain_link
    except ChainLink.DoesNotExist:
        return None  # Nije u lancu

    payload = _receipt_payload(receipt)
    payload_hash = _sha256(payload)

    if payload_hash != link.payload_hash:
        return False  # Bon je modificiran nakon upisa u lanac!
    return True


def daily_anchor_hash(company):
    """
    Dnevni anchor — hash svih Z-reportova od danas.
    Može se upisati u OpenTimestamps za Bitcoin dokaz.
    Poziva se iz Celery beat taska (23:59).
    """
    today = tz.now().date()
    links = ChainLink.objects.filter(
        company=company,
        created_at__date=today,
    ).order_by('sequence')

    if not links.exists():
        return None

    # Merkle-like: hash svih dnevnih hasheva
    day_data = '|'.join(l.chain_hash for l in links)
    anchor = _sha256(f'DAILY:{today.isoformat()}:{day_data}')

    logger.info(
        'Daily anchor for %s on %s: %s (%d links)',
        company.name, today, anchor[:16], links.count(),
    )
    return anchor
