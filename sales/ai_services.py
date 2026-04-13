"""
sales/ai_services.py — AI-powered inovacije za prodajni modul

1. SmartPricing — AI preporuča optimalne rabate na osnovu historije kupca
2. OrderPredictor — AI predviđa što će kupac naručiti (basket analysis)
3. PaymentPredictor — AI predviđa kad će kupac platiti (risk scoring)
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


def smart_pricing_suggest(company, partner):
    """
    AI preporuka rabata za kupca na osnovu historije.
    Analizira: ukupan promet, frekvencija narudžbi, prosječna vrijednost,
    promptnost plaćanja.
    Returns: dict s preporučenim discount_percent i confidence.
    """
    from invoicing.models import Invoice
    from sales.models import OpenItem

    # Historija faktura za ovog partnera
    invoices = Invoice.objects.filter(
        company=company,
        partner=partner,
        status="paid",
    )
    total_revenue = invoices.aggregate(s=Sum("total"))["s"] or Decimal("0")
    invoice_count = invoices.count()
    avg_value = invoices.aggregate(a=Avg("total"))["a"] or Decimal("0")

    # Promptnost plaćanja
    paid_items = OpenItem.objects.filter(
        company=company,
        partner=partner,
        is_closed=True,
        direction="receivable",
    )
    avg_days_to_pay = 0
    if paid_items.exists():
        total_days = sum((item.closed_at.date() - item.due_date).days for item in paid_items if item.closed_at)
        avg_days_to_pay = total_days / paid_items.count()

    # Scoring
    score = 0
    if total_revenue > 10000:
        score += 30
    elif total_revenue > 5000:
        score += 20
    elif total_revenue > 1000:
        score += 10

    if invoice_count > 20:
        score += 25
    elif invoice_count > 10:
        score += 15
    elif invoice_count > 5:
        score += 8

    if avg_days_to_pay < 0:  # Plaća prije roka
        score += 25
    elif avg_days_to_pay <= 5:
        score += 15
    elif avg_days_to_pay <= 15:
        score += 5

    # Map score to discount
    if score >= 70:
        discount = Decimal("15")
        tier = "VIP"
    elif score >= 50:
        discount = Decimal("10")
        tier = "Premium"
    elif score >= 30:
        discount = Decimal("5")
        tier = "Standard+"
    elif score >= 15:
        discount = Decimal("3")
        tier = "Standard"
    else:
        discount = Decimal("0")
        tier = "Novi kupac"

    confidence = min(Decimal("95"), Decimal(str(score)))

    return {
        "suggested_discount": discount,
        "tier": tier,
        "confidence": confidence,
        "total_revenue": total_revenue,
        "invoice_count": invoice_count,
        "avg_order_value": avg_value,
        "avg_days_to_pay": round(avg_days_to_pay, 1),
        "score": score,
    }


def order_predictor(company, partner):
    """
    AI predviđa što će kupac naručiti — basket analysis.
    Gleda zadnjih 6 mjeseci faktura i POS računa.
    Returns: lista artikala s predicted_quantity i confidence.
    """
    from django.db.models import Avg, Count

    from invoicing.models import InvoiceItem

    six_months_ago = timezone.now() - timedelta(days=180)

    # Najčešće kupovani artikli
    items = (
        InvoiceItem.objects.filter(
            invoice__company=company,
            invoice__partner=partner,
            invoice__issue_date__gte=six_months_ago,
            invoice__status__in=("paid", "sent"),
        )
        .values(
            "description",
            item_name=F("description"),
        )
        .annotate(
            times_ordered=Count("id"),
            avg_qty=Avg("quantity"),
            avg_price=Avg("unit_price"),
        )
        .order_by("-times_ordered")[:15]
    )

    suggestions = []
    for i, item in enumerate(items):
        confidence = max(30, min(95, item["times_ordered"] * 10))
        suggestions.append(
            {
                "item_name": item["item_name"],
                "predicted_quantity": round(float(item["avg_qty"]), 2),
                "avg_price": round(float(item["avg_price"]), 2),
                "times_ordered": item["times_ordered"],
                "confidence": confidence,
                "rank": i + 1,
            }
        )

    return suggestions


def payment_predictor(company, partner=None):
    """
    AI predviđa kad će kupac platiti — risk scoring.
    Bazira se na historiji plaćanja.
    Returns: dict per open item s predicted_days i risk_score.
    """
    from sales.models import OpenItem

    open_items = OpenItem.objects.filter(
        company=company,
        is_closed=False,
        direction="receivable",
    ).select_related("partner")

    if partner:
        open_items = open_items.filter(partner=partner)

    # Get payment history per partner
    partner_history = {}
    closed = (
        OpenItem.objects.filter(
            company=company,
            is_closed=True,
            direction="receivable",
        )
        .values("partner_id")
        .annotate(
            avg_delay=Avg(
                F("closed_at") - F("due_date"),
            ),
            total_paid=Sum("original_amount"),
            count=Count("id"),
        )
    )
    for h in closed:
        avg_delay_days = h["avg_delay"].days if h["avg_delay"] else 0
        partner_history[h["partner_id"]] = {
            "avg_delay": avg_delay_days,
            "total_paid": h["total_paid"] or 0,
            "count": h["count"],
        }

    predictions = []
    for item in open_items:
        history = partner_history.get(item.partner_id, {})
        avg_delay = history.get("avg_delay", 15)  # Default 15 dana
        payment_count = history.get("count", 0)

        # Risk score: 0 = safe, 100 = high risk
        risk = 20  # Base
        if item.days_overdue > 90:
            risk += 50
        elif item.days_overdue > 60:
            risk += 35
        elif item.days_overdue > 30:
            risk += 20
        elif item.days_overdue > 0:
            risk += 10

        if avg_delay > 30:
            risk += 20
        elif avg_delay > 15:
            risk += 10

        if payment_count < 3:
            risk += 10  # New customer = unknown risk

        risk = min(100, risk)

        predicted_days = max(1, avg_delay - item.days_overdue + 5)

        predictions.append(
            {
                "item": item,
                "predicted_days": predicted_days,
                "risk_score": risk,
                "risk_level": "high" if risk > 60 else "medium" if risk > 30 else "low",
                "partner_history": history,
            }
        )

    return sorted(predictions, key=lambda x: -x["risk_score"])


def resolve_price(company, partner, item, quantity=1):
    """
    Resolve najbolju cijenu za kupca/artikl kombinaciju.
    Hijerarhija: Partner cjenik > Grupa cjenik > Standardna cijena
    """
    from sales.models import CustomerPriceList

    today = timezone.now().date()
    base_price = item.unit_price

    # Find applicable price lists
    price_lists = (
        CustomerPriceList.objects.filter(
            company=company,
            is_active=True,
        )
        .filter(Q(partner=partner) | Q(partner_group=getattr(partner, "group", "")))
        .filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=today),
            Q(valid_until__isnull=True) | Q(valid_until__gte=today),
        )
        .order_by("priority")
    )

    best_price = base_price
    applied_discount = None

    for pl in price_lists:
        # Check item-specific line first
        line = pl.lines.filter(item=item).first()
        if not line:
            # Check rabat group
            rabat_group = getattr(item, "rabat_group", None)
            if rabat_group:
                line = pl.lines.filter(rabat_group=rabat_group).first()

        if line:
            calculated = line.calculate_price(base_price, quantity)
            if calculated < best_price:
                best_price = calculated
                applied_discount = {
                    "price_list": pl.name,
                    "discount_type": line.get_discount_type_display(),
                    "discount_value": line.discount_value,
                    "original_price": base_price,
                    "final_price": calculated,
                    "savings": base_price - calculated,
                    "savings_percent": ((base_price - calculated) / base_price * 100).quantize(Decimal("0.1"))
                    if base_price
                    else 0,
                }
            break  # First matching (by priority) wins

    return {
        "price": best_price,
        "base_price": base_price,
        "discount_applied": applied_discount,
        "has_special_price": applied_discount is not None,
    }
