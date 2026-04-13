"""
PO-SD Auto-Fill — Zero-Click agregacija primitaka iz rental i invoicing.

Agregira sve transakcije (fakture, POS receiptove, rental bookinge)
po kvartalima za zadanu firmu i godinu, te automatski popunjava
PO-SD wizard sesiju.

Izvor podataka (prioritet):
  1. rental.TrafficRecord (Obrazac EP — najprecizniji za iznajmljivace)
  2. invoicing.Invoice (IRA — svi izdani racuni)
  3. pos.POSReceipt (POS promet — ako nema faktura)

Za pausalce koji koriste rental modul, TrafficRecord je zakonski relevantan.
Za ostale pausalce, Invoice je primarni izvor.
"""
import logging
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger("tax_wizard.auto_fill")

_Q = Decimal("0.01")
ZERO = Decimal("0.00")

# Quarter date ranges
def _quarter_range(year, quarter):
    """Vraca (start_date, end_date) za kvartal."""
    ranges = {
        1: (date(year, 1, 1), date(year, 3, 31)),
        2: (date(year, 4, 1), date(year, 6, 30)),
        3: (date(year, 7, 1), date(year, 9, 30)),
        4: (date(year, 10, 1), date(year, 12, 31)),
    }
    return ranges[quarter]


def aggregate_rental_income(company, year):
    """
    Agregira primitke iz rental.TrafficRecord po kvartalima.
    TrafficRecord = Obrazac EP = zakonski relevantan za iznajmljivace.

    Returns:
        dict: {q1: Decimal, q2: Decimal, q3: Decimal, q4: Decimal,
               total: Decimal, source: 'rental', record_count: int}
    """
    from rental.models import TrafficRecord

    result = {"source": "rental", "record_count": 0}
    total = ZERO

    for q in range(1, 5):
        start, end = _quarter_range(year, q)
        agg = TrafficRecord.objects.filter(
            company=company,
            date__gte=start,
            date__lte=end,
        ).aggregate(
            amount_sum=Sum("amount"),
            tax_sum=Sum("tourist_tax"),
            total_sum=Sum("total"),
            count=Sum("pk"),  # hack for count in aggregate
        )

        # Za PO-SD koristimo "amount" (bez turisticke pristojbe)
        # jer pristojba nije primitak obrtnika, vec se prosljeduje TZ-u
        q_amount = Decimal(str(agg["amount_sum"] or 0)).quantize(_Q)
        result[f"q{q}"] = q_amount
        result[f"q{q}_tourist_tax"] = Decimal(str(agg["tax_sum"] or 0)).quantize(_Q)
        total += q_amount

    result["total"] = total
    result["record_count"] = TrafficRecord.objects.filter(
        company=company,
        date__year=year,
    ).count()

    return result


def aggregate_invoice_income(company, year):
    """
    Agregira primitke iz invoicing.Invoice (IRA) po kvartalima.
    Koristi se za pausalce koji ne koriste rental modul.

    Returns:
        dict: {q1-q4, total, source, invoice_count}
    """
    from invoicing.models import Invoice

    result = {"source": "invoicing", "invoice_count": 0}
    total = ZERO

    for q in range(1, 5):
        start, end = _quarter_range(year, q)
        agg = Invoice.objects.filter(
            company=company,
            date_issued__gte=timezone.make_aware(timezone.datetime.combine(start, timezone.datetime.min.time())),
            date_issued__lte=timezone.make_aware(timezone.datetime.combine(end, timezone.datetime.max.time())),
            status__in=["CONFIRMED", "FISCALIZED", "SENT", "ACCEPTED", "PAID"],
            doctype="IRA",
        ).aggregate(total_sum=Sum("total"))

        q_amount = Decimal(str(agg["total_sum"] or 0)).quantize(_Q)
        result[f"q{q}"] = q_amount
        total += q_amount

    result["total"] = total
    result["invoice_count"] = Invoice.objects.filter(
        company=company,
        date_issued__year=year,
        status__in=["CONFIRMED", "FISCALIZED", "SENT", "ACCEPTED", "PAID"],
        doctype="IRA",
    ).count()

    return result


def aggregate_pos_income(company, year):
    """
    Agregira primitke iz POS prometa (POSReceipt).
    Fallback za pausalce koji nemaju ni rental ni fakture.

    Returns:
        dict: {q1-q4, total, source, receipt_count}
    """
    from pos.models import POSReceipt

    result = {"source": "pos", "receipt_count": 0}
    total = ZERO

    for q in range(1, 5):
        start, end = _quarter_range(year, q)
        agg = POSReceipt.objects.filter(
            session__terminal__company=company,
            created_at__date__gte=start,
            created_at__date__lte=end,
            is_cancelled=False,
        ).aggregate(total_sum=Sum("total_amount"))

        q_amount = Decimal(str(agg["total_sum"] or 0)).quantize(_Q)
        result[f"q{q}"] = q_amount
        total += q_amount

    result["total"] = total
    result["receipt_count"] = POSReceipt.objects.filter(
        session__terminal__company=company,
        created_at__year=year,
        is_cancelled=False,
    ).count()

    return result


def auto_fill_posd(company, year, prefer_source="auto"):
    """
    Automatski popuni PO-SD podatke iz najboljeg izvora.

    Args:
        company: Company instance
        year: porezna godina
        prefer_source: "rental", "invoicing", "pos", ili "auto"

    Returns:
        dict: {
            q1_primitak, q2_primitak, q3_primitak, q4_primitak,
            ukupni_primitak, source, record_count,
            sources_checked: [...],
            company_info: {oib, name, address, ...}
        }
    """
    sources_checked = []

    if prefer_source == "auto":
        # Provjeri rental prvo (ako ima TrafficRecord)
        from rental.models import TrafficRecord
        has_rental = TrafficRecord.objects.filter(company=company, date__year=year).exists()

        if has_rental:
            data = aggregate_rental_income(company, year)
            sources_checked.append({"name": "rental", "records": data["record_count"], "total": str(data["total"])})
        else:
            # Fallback na invoicing
            data = aggregate_invoice_income(company, year)
            sources_checked.append({"name": "invoicing", "records": data.get("invoice_count", 0), "total": str(data["total"])})

            if data["total"] == ZERO:
                # Fallback na POS
                data = aggregate_pos_income(company, year)
                sources_checked.append({"name": "pos", "records": data.get("receipt_count", 0), "total": str(data["total"])})
    elif prefer_source == "rental":
        data = aggregate_rental_income(company, year)
        sources_checked.append({"name": "rental", "records": data["record_count"], "total": str(data["total"])})
    elif prefer_source == "invoicing":
        data = aggregate_invoice_income(company, year)
        sources_checked.append({"name": "invoicing", "records": data.get("invoice_count", 0), "total": str(data["total"])})
    elif prefer_source == "pos":
        data = aggregate_pos_income(company, year)
        sources_checked.append({"name": "pos", "records": data.get("receipt_count", 0), "total": str(data["total"])})
    else:
        data = {"q1": ZERO, "q2": ZERO, "q3": ZERO, "q4": ZERO, "total": ZERO, "source": "none"}

    # Build result
    result = {
        "q1_primitak": str(data.get("q1", ZERO)),
        "q2_primitak": str(data.get("q2", ZERO)),
        "q3_primitak": str(data.get("q3", ZERO)),
        "q4_primitak": str(data.get("q4", ZERO)),
        "ukupni_primitak": str(data.get("total", ZERO)),
        "source": data.get("source", "none"),
        "sources_checked": sources_checked,
        # Company info za PO-SD obrazac
        "oib": company.oib or "",
        "ime_prezime": company.name or "",
        "naziv_obrta": company.name or "",
        "adresa": f"{company.address or ''}, {company.zip_code or ''} {company.city or ''}".strip(", "),
        "djelatnost_nkd": getattr(company, "nkd_code", "") or "",
        "porezna_godina": year,
    }

    logger.info(
        f"PO-SD auto-fill for {company.name} ({year}): "
        f"{data['total']} EUR from {data.get('source', 'none')} "
        f"({sources_checked})"
    )

    return result


def auto_fill_and_calculate(company, year, already_paid=ZERO, prefer_source="auto"):
    """
    Kombinirani auto-fill + kalkulacija — sve u jednom pozivu.

    Returns:
        dict: {form_data: {...}, calculated: {...}, ai_messages: [...]}
    """
    from tax_wizard.services import AIAdvisor, POSDCalculator

    # Auto-fill
    form_data = auto_fill_posd(company, year, prefer_source)

    # Calculate
    calc = POSDCalculator(year).calculate(
        q1=Decimal(form_data["q1_primitak"]),
        q2=Decimal(form_data["q2_primitak"]),
        q3=Decimal(form_data["q3_primitak"]),
        q4=Decimal(form_data["q4_primitak"]),
        already_paid=already_paid,
    )

    # AI messages
    ai = AIAdvisor(year).analyze(calc, company=company)

    return {
        "form_data": form_data,
        "calculated": calc,
        "ai_messages": ai,
    }
