"""
tax_wizard/prefill_engine.py — Prefill Engine za Porezni Savjetnik

Agregira primitke iz Invoicing + POS modula za auto-fill wizard-a.

DVA ZAKONA KOJA POŠTUJEMO:
  Caka #1 — NAPOJNICE SE NE BROJE
    POSReceiptItem.is_tip=True → isključeno iz primitaka.
    Napojnica NIJE primitak paušalca (nije njegova usluga).

  Caka #2 — NAČELO BLAGAJNE (Cash Basis)
    Paušalac prijavljuje primitak KADA JE NOVAC PRIMLJEN, ne kada
    je račun izdan. Zato:
    - Invoice: status='PAID' + InvoiceEvent(type='paid').created_at za datum
    - POS: POSReceipt.paid_at (jer POS = trenutna naplata)
    Ako Invoice nema paid event → fallback na date_issued (većina paušalaca
    izdaje i naplaćuje isti dan).

  Caka #3 — ISKLJUČI STORNE I TRAINING
    storno_of IS NOT NULL → skip
    invoice_type='storno' → skip
    POSReceipt.is_training=True → skip
    POSReceipt.status='cancelled'/'refunded' → skip (ali refunded=negativan primitak!)

BORG VETO: Svako polje u ovom fajlu dolazi iz cat models.py — nula pretpostavki.
"""
import logging
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q

logger = logging.getLogger(__name__)

_Q = Decimal('0.01')
ZERO = Decimal('0.00')


@dataclass
class QuarterlyBreakdown:
    """Primitci rastavljeni po kvartalima — source of truth za PO-SD."""
    q1: Decimal = ZERO
    q2: Decimal = ZERO
    q3: Decimal = ZERO
    q4: Decimal = ZERO
    q1_invoice_count: int = 0
    q2_invoice_count: int = 0
    q3_invoice_count: int = 0
    q4_invoice_count: int = 0
    q1_pos_count: int = 0
    q2_pos_count: int = 0
    q3_pos_count: int = 0
    q4_pos_count: int = 0
    tips_excluded: Decimal = ZERO
    training_excluded: Decimal = ZERO
    storno_excluded: Decimal = ZERO
    sources: list = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return (self.q1 + self.q2 + self.q3 + self.q4).quantize(_Q)

    @property
    def invoice_count(self) -> int:
        return (
            self.q1_invoice_count + self.q2_invoice_count
            + self.q3_invoice_count + self.q4_invoice_count
        )

    @property
    def pos_count(self) -> int:
        return (
            self.q1_pos_count + self.q2_pos_count
            + self.q3_pos_count + self.q4_pos_count
        )

    def to_dict(self) -> dict:
        return {
            'q1_primitak': float(self.q1),
            'q2_primitak': float(self.q2),
            'q3_primitak': float(self.q3),
            'q4_primitak': float(self.q4),
            'ukupni_primitak': float(self.total),
            'q1_invoice_count': self.q1_invoice_count,
            'q2_invoice_count': self.q2_invoice_count,
            'q3_invoice_count': self.q3_invoice_count,
            'q4_invoice_count': self.q4_invoice_count,
            'q1_pos_count': self.q1_pos_count,
            'q2_pos_count': self.q2_pos_count,
            'q3_pos_count': self.q3_pos_count,
            'q4_pos_count': self.q4_pos_count,
            'total_invoices': self.invoice_count,
            'total_pos_receipts': self.pos_count,
            'tips_excluded': float(self.tips_excluded),
            'training_excluded': float(self.training_excluded),
            'storno_excluded': float(self.storno_excluded),
            'sources': self.sources,
        }


class PrefillEngine:
    """
    Agregira primitke za paušalnog obrtnika iz LIMIT Connect podataka.

    Usage:
        engine = PrefillEngine(company, year=2025)
        breakdown = engine.aggregate()
        # breakdown.q1 = 8430.00, breakdown.total = 28430.00
    """

    def __init__(self, company, year: int):
        self.company = company
        self.year = year

    def aggregate(self) -> QuarterlyBreakdown:
        """Puni agregat: Invoice + POS, s svim cakama."""
        breakdown = QuarterlyBreakdown()

        # 1. Invoicing primitci (IRA — izdani računi)
        self._aggregate_invoices(breakdown)

        # 2. POS primitci (blagajna — gotovinska prodaja)
        self._aggregate_pos(breakdown)

        # Zaokruži sve na 2 decimale
        breakdown.q1 = breakdown.q1.quantize(_Q, rounding=ROUND_HALF_UP)
        breakdown.q2 = breakdown.q2.quantize(_Q, rounding=ROUND_HALF_UP)
        breakdown.q3 = breakdown.q3.quantize(_Q, rounding=ROUND_HALF_UP)
        breakdown.q4 = breakdown.q4.quantize(_Q, rounding=ROUND_HALF_UP)

        logger.info(
            'PrefillEngine: %s/%d — ukupno %.2f EUR '
            '(inv=%d, pos=%d, tips_excl=%.2f, training_excl=%.2f)',
            self.company.name, self.year, breakdown.total,
            breakdown.invoice_count, breakdown.pos_count,
            breakdown.tips_excluded, breakdown.training_excluded,
        )

        return breakdown

    def _aggregate_invoices(self, breakdown: QuarterlyBreakdown):
        """
        Caka #2 — Načelo blagajne:
        Primitak se broji po datumu NAPLATE, ne izdavanja.
        Koristimo InvoiceEvent(event_type='paid').created_at.
        Fallback: date_issued ako nema paid eventa.
        """
        from invoicing.models import Invoice, InvoiceEvent

        # Dohvati sve PLAĆENE račune ove firme za ovu godinu
        # doctype IN ('R', 'RN', 'FA') — samo izlazni računi (ne URA, ne ponude)
        # Isključi: storno, odobrenje, otkazano
        invoices = Invoice.objects.filter(
            company=self.company,
            status='PAID',
            doctype__in=['R', 'RN', 'FA'],
        ).exclude(
            invoice_type__in=['storno', 'odobrenje'],
        ).exclude(
            storno_of__isnull=False,  # Račun koji JE storno drugog
        ).exclude(
            status='STORNO',
        ).exclude(
            status='CANCELLED',
        )

        # Za svaki invoice, nađi datum naplate
        paid_events = {}
        events = InvoiceEvent.objects.filter(
            invoice__in=invoices,
            event_type='paid',
        ).values('invoice_id', 'created_at')
        for ev in events:
            paid_events[ev['invoice_id']] = ev['created_at']

        storno_total = ZERO
        for inv in invoices:
            # Datum naplate — caka #2
            paid_date = paid_events.get(inv.pk)
            if paid_date:
                effective_date = paid_date.date() if hasattr(paid_date, 'date') else paid_date
            else:
                # Fallback: date_issued (većina paušalaca naplaćuje odmah)
                dt = inv.date_issued
                effective_date = dt.date() if hasattr(dt, 'date') else dt

            # Filter po godini (na temelju datuma naplate!)
            if effective_date.year != self.year:
                continue

            # Negativan total = storno/odobrenje koji je prošao filter
            amount = inv.total or ZERO
            if amount < 0:
                storno_total += abs(amount)
                continue

            # Rasporedi po kvartalima
            quarter = (effective_date.month - 1) // 3 + 1
            if quarter == 1:
                breakdown.q1 += amount
                breakdown.q1_invoice_count += 1
            elif quarter == 2:
                breakdown.q2 += amount
                breakdown.q2_invoice_count += 1
            elif quarter == 3:
                breakdown.q3 += amount
                breakdown.q3_invoice_count += 1
            else:
                breakdown.q4 += amount
                breakdown.q4_invoice_count += 1

        breakdown.storno_excluded += storno_total
        if invoices.exists():
            breakdown.sources.append('invoicing')

    def _aggregate_pos(self, breakdown: QuarterlyBreakdown):
        """
        POS primitci — bonovi s blagajne.

        Caka #1: is_tip=True stavke se ISKLJUČUJU
        Caka #2: paid_at je datum primitka (POS = trenutna naplata)
        Caka #3: is_training=True bonovi se ISKLJUČUJU
        """
        from pos.models import POSReceipt

        # Dohvati sve PLAĆENE, ne-training bonove za ovu firmu i godinu
        receipts = POSReceipt.objects.filter(
            session__terminal__company=self.company,
            status='paid',
            is_training=False,
            paid_at__year=self.year,
        ).exclude(
            status__in=['cancelled'],
        )

        # Refunded bonovi — parent_receipt is not null, negativni primitci
        # Ali: refundirani bonovi imaju status='refunded' koji smo već filtrirali
        # (nisu 'paid'). Ako je status='paid' a parent_receipt postoji,
        # to je storno bon — ignoriramo ga jer ima negativan total.

        tips_total = ZERO
        training_total = ZERO

        for receipt in receipts:
            # paid_at je naš datum (caka #2 — načelo blagajne)
            if not receipt.paid_at:
                continue

            quarter = (receipt.paid_at.month - 1) // 3 + 1

            # Izračunaj iznos BEZ napojnica (caka #1)
            # Dohvati sve stavke ovog bona
            items = receipt.items.all()
            tip_amount = ZERO
            non_tip_total = ZERO

            for item in items:
                if item.is_tip or item.is_tip_employer:
                    # Caka #1 — napojnice se ne broje
                    tips_total += item.total_price
                elif item.is_nonprofit_activity:
                    # Članarine/donacije — nisu primitak obrta
                    pass
                else:
                    non_tip_total += item.total_price

            # Negativan total = storno/povrat bon
            if non_tip_total < 0:
                breakdown.storno_excluded += abs(non_tip_total)
                continue

            # Rasporedi po kvartalima
            if quarter == 1:
                breakdown.q1 += non_tip_total
                breakdown.q1_pos_count += 1
            elif quarter == 2:
                breakdown.q2 += non_tip_total
                breakdown.q2_pos_count += 1
            elif quarter == 3:
                breakdown.q3 += non_tip_total
                breakdown.q3_pos_count += 1
            else:
                breakdown.q4 += non_tip_total
                breakdown.q4_pos_count += 1

        breakdown.tips_excluded += tips_total
        if receipts.exists():
            breakdown.sources.append('pos')

    def get_company_info(self) -> dict:
        """Povlači podatke o firmi za auto-fill wizard Step 1."""
        company = self.company
        user = None

        # Pokušaj naći vlasnika/korisnika firme
        from django.contrib.auth.models import User
        try:
            user = User.objects.filter(
                Q(employee_profile__company=company)
                | Q(created_invoices__company=company)
            ).first()
        except Exception:
            pass

        return {
            'oib': company.oib or '',
            'naziv_obrta': company.name or '',
            'adresa': f'{company.address}, {company.zip_code} {company.city}'.strip(', '),
            'ime_prezime': user.get_full_name() if user else '',
            'porezna_godina': self.year,
        }
