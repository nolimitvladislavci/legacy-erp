"""
production/konto.py — Automatsko knjiženje proizvodnje u konto

Knjiženja pri završetku radnog naloga:
  D 630 Utrošak materijala      → materijal_cost
  P 310 Sirovine i materijal    → materijal_cost
  D 631 Troškovi rada           → labor_cost
  P 240 Obveze za plaće         → labor_cost
  D 632 Režijski troškovi       → overhead_cost
  P 490 Razgraničenje troškova  → overhead_cost
  D 600 Gotovi proizvodi (zalihe) → total_cost
  P 790 Aktivacija gotovih proizvoda → total_cost

Konta se mogu prilagoditi per company putem ProductionKontoConfig.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger(__name__)

# Default konta (HR kontni plan)
DEFAULT_ACCOUNTS = {
    'material_debit': '630',     # Utrošak materijala
    'material_credit': '310',    # Sirovine i materijal (skladište)
    'labor_debit': '631',        # Troškovi rada
    'labor_credit': '240',       # Obveze za plaće
    'overhead_debit': '632',     # Režijski troškovi proizvodnje
    'overhead_credit': '490',    # Razgraničenje troškova
    'output_debit': '600',       # Gotovi proizvodi (zalihe)
    'output_credit': '790',      # Prihod — aktivacija gotovih proizvoda
}

# DE konta (SKR03)
DE_ACCOUNTS = {
    'material_debit': '4800',    # Aufwendungen für Roh-, Hilfs- und Betriebsstoffe
    'material_credit': '3000',   # Roh-, Hilfs- und Betriebsstoffe (Bestand)
    'labor_debit': '4100',       # Löhne
    'labor_credit': '1740',      # Verbindlichkeiten Lohn/Gehalt
    'overhead_debit': '4900',    # Sonstige Aufwendungen
    'overhead_credit': '0980',   # Aktive Rechnungsabgrenzung
    'output_debit': '7000',      # Bestandsveränderungen fertige Erzeugnisse
    'output_credit': '3980',     # Fertige Erzeugnisse (Bestand)
}


def get_accounts(company):
    """Dohvati konta za firmu — custom ili default."""
    country = getattr(company, 'country', 'HR')
    defaults = DE_ACCOUNTS if country == 'DE' else DEFAULT_ACCOUNTS

    # Check for custom config
    try:
        from production.models import ProductionOrder
        # Future: ProductionKontoConfig model per company
        # config = ProductionKontoConfig.objects.filter(company=company).first()
        # if config: return config.as_dict()
    except DatabaseError:
        pass

    return defaults


@transaction.atomic
def book_production_order(order, user=None):
    """
    Proknjiži završeni radni nalog u konto.
    Kreira JournalEntry s 4 para knjiženja (8 LedgerLine-ova).
    """
    from konto.models import JournalEntry, LedgerLine, KontoAccount

    company = order.company
    accounts = get_accounts(company)

    if order.total_cost <= 0:
        logger.warning(f'Production order {order.order_number} has zero cost, skipping booking')
        return None

    # Create journal entry
    entry = JournalEntry.objects.create(
        company=company,
        date=timezone.now().date(),
        document_type='production',
        document_number=order.order_number,
        description=f'Proizvodni nalog {order.order_number} — {order.bom.output_item.name} × {order.produced_quantity}',
        created_by=user,
        is_auto=True,
    )

    lines_to_create = []

    def _add_pair(debit_code, credit_code, amount, desc):
        if amount <= 0:
            return
        # Find or create accounts
        d_acc, _ = KontoAccount.objects.get_or_create(
            company=company, code=debit_code,
            defaults={'name': desc + ' (D)', 'account_type': 'expense'}
        )
        c_acc, _ = KontoAccount.objects.get_or_create(
            company=company, code=credit_code,
            defaults={'name': desc + ' (P)', 'account_type': 'liability'}
        )
        lines_to_create.append(LedgerLine(
            entry=entry, account=d_acc,
            debit=amount, credit=Decimal('0'),
            description=desc,
        ))
        lines_to_create.append(LedgerLine(
            entry=entry, account=c_acc,
            debit=Decimal('0'), credit=amount,
            description=desc,
        ))

    # 1. Materijal
    _add_pair(
        accounts['material_debit'], accounts['material_credit'],
        order.material_cost,
        f'Utrošak materijala — {order.order_number}'
    )

    # 2. Rad
    _add_pair(
        accounts['labor_debit'], accounts['labor_credit'],
        order.labor_cost,
        f'Troškovi rada — {order.order_number}'
    )

    # 3. Režija
    _add_pair(
        accounts['overhead_debit'], accounts['overhead_credit'],
        order.overhead_cost,
        f'Režijski troškovi — {order.order_number}'
    )

    # 4. Aktivacija gotovih proizvoda
    _add_pair(
        accounts['output_debit'], accounts['output_credit'],
        order.total_cost,
        f'Gotovi proizvodi — {order.bom.output_item.name} × {order.produced_quantity}'
    )

    LedgerLine.objects.bulk_create(lines_to_create)

    logger.info(
        f'Production booking: {order.order_number} → JournalEntry #{entry.pk}, '
        f'{len(lines_to_create)} lines, total {order.total_cost} EUR'
    )

    # Log in production
    from production.models import ProductionLog
    ProductionLog.objects.create(
        order=order,
        action='cost_updated',
        description=f'Proknjiženo u konto: temeljnica #{entry.pk}, {order.total_cost} EUR',
        metadata={'journal_entry_id': str(entry.pk), 'total': float(order.total_cost)},
        user=user,
    )

    return entry
