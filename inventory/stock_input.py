"""
inventory/stock_input.py
StockInputProcessor — centralni ulaz u skladište.

Svaki input (POS, Invoice, Camera AI, API, Manual) prolazi ovdje.
Garantira:
1. item.should_track_stock() — usluge ne idu u skladište
2. Math cross-check — Σ(qty×price) + PDV = total ± 0.02 EUR
3. StockMovement kreiran s punim audit trailom
4. item.quantity ažuriran atomski

Dron #4 fix: LLM matematika — crveni ekran ako AI račun ne štima.
"""
import logging
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import List

from django.db import transaction

logger = logging.getLogger('inventory.stock_input')

MATH_TOLERANCE = Decimal('0.02')  # EUR


@dataclass
class StockLine:
    """Jedna stavka ulaza/izlaza."""
    item_id: int
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal = Decimal('25')
    description: str = ''


@dataclass
class StockInputResult:
    """Rezultat procesiranja."""
    success: bool
    movements_created: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    math_check_passed: bool = True


class MathCheckError(Exception):
    """LLM/Camera input ne prolazi matematičku provjeru."""
    pass


class StockInputProcessor:
    """
    Centralni procesor svih ulaza u skladište.

    Korištenje:
        processor = StockInputProcessor(company, user, source='pos')
        result = processor.process(lines, expected_total=125.00)
    """

    VALID_SOURCES = ('pos', 'invoice', 'camera', 'api', 'manual', 'synesis', 'webshop')

    def __init__(self, company, user=None, source='manual'):
        self.company = company
        self.user = user
        self.source = source
        if source not in self.VALID_SOURCES:
            raise ValueError(f'Invalid source: {source}')

    @transaction.atomic
    def process_in(self, lines: List[StockLine], expected_total=None,
                   reason='', invoice=None) -> StockInputResult:
        """Procesira ULAZ u skladište (nabava, primka)."""
        return self._process(lines, 'in', expected_total, reason, invoice)

    @transaction.atomic
    def process_out(self, lines: List[StockLine], expected_total=None,
                    reason='', invoice=None) -> StockInputResult:
        """Procesira IZLAZ iz skladišta (prodaja, izdavanje)."""
        return self._process(lines, 'out', expected_total, reason, invoice)

    def _process(self, lines, movement_type, expected_total, reason, invoice):
        from inventory.models import InventoryItem, StockMovement

        result = StockInputResult(success=True)

        # ── Math cross-check (Dron #4) ───────────────────────────────
        if expected_total is not None:
            expected = Decimal(str(expected_total)).quantize(Decimal('0.01'))
            calculated = Decimal('0')
            for line in lines:
                line_net = (line.quantity * line.unit_price).quantize(Decimal('0.01'), ROUND_HALF_UP)
                line_tax = (line_net * line.tax_rate / 100).quantize(Decimal('0.01'), ROUND_HALF_UP)
                calculated += line_net + line_tax

            diff = abs(calculated - expected)
            if diff > MATH_TOLERANCE:
                msg = (
                    f'MATH CHECK FAILED: calculated={calculated} vs expected={expected} '
                    f'(diff={diff}, tolerance={MATH_TOLERANCE}). '
                    f'Source: {self.source}. StockMovement NOT created.'
                )
                logger.error(msg)
                result.success = False
                result.math_check_passed = False
                result.errors.append(msg)
                return result

            result.math_check_passed = True

        # ── Procesiraj svaku stavku ──────────────────────────────────
        for line in lines:
            try:
                item = InventoryItem.objects.select_for_update().get(
                    pk=line.item_id, company=self.company
                )
            except InventoryItem.DoesNotExist:
                result.errors.append(f'Item {line.item_id} not found')
                continue

            # Guard: usluge ne idu u skladište
            if not item.should_track_stock():
                result.warnings.append(
                    f'{item.name} (item_class={item.item_class}) — skipped, not stockable'
                )
                continue

            # Kreiraj StockMovement
            sm = StockMovement(
                item=item,
                movement_type=movement_type,
                quantity=line.quantity,
                unit_price=line.unit_price,
                reason=reason or f'[{self.source}] {line.description}',
                performed_by=self.user,
                invoice=invoice,
            )
            sm.save()
            result.movements_created += 1

        if result.errors:
            result.success = len(result.errors) == 0

        logger.info(
            'StockInput %s: %s %d movements, %d errors, %d warnings (company=%s)',
            self.source, movement_type, result.movements_created,
            len(result.errors), len(result.warnings), self.company.name
        )

        return result
