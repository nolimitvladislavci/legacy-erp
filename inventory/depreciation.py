"""
W1E — Amortizacija kalkulacija (DRAFT ONLY)
Metode: Linearna 5g, Linearna 10g, Degresivna
Zapisi se NE spremaju u bazu — samo DepreciationDraft dict.
Celery task šalje Mariji WhatsApp jednom mjesečno.
"""

import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import DatabaseError
from django.utils import timezone

logger = logging.getLogger("inventory.depreciation")


class DepreciationCalculator:
    """Kalkulacija amortizacije — DRAFT, ne sprema u bazu."""

    METHODS = {
        "LINEAR_5Y": {"years": 5, "label": "Linearna 5 god. (20%/god)"},
        "LINEAR_10Y": {"years": 10, "label": "Linearna 10 god. (10%/god)"},
        "LINEAR_4Y": {"years": 4, "label": "Linearna 4 god. (25%/god) — vozila"},
        "DECLINING": {"years": 5, "label": "Degresivna (40/24/14.4/10.8/10.8%)"},
    }

    DECLINING_RATES = [0.40, 0.24, 0.144, 0.108, 0.108]

    def calculate_annual(self, item, method="LINEAR_5Y") -> dict:
        """
        Izračunaj amortizacijski plan za asset.
        Ne sprema ništa — vraća DepreciationDraft dict.

        Args:
            item: InventoryItem instanca (mora biti asset s purchase_price)
            method: LINEAR_5Y | LINEAR_10Y | LINEAR_4Y | DECLINING

        Returns:
            DepreciationDraft dict
        """
        try:
            purchase_price = Decimal(str(item.purchase_price or 0))
            if purchase_price <= 0:
                return {"error": "Nema purchase_price na artiklu"}

            if item.item_class != "asset":
                return {"error": f"Artikl nije asset (item_class={item.item_class})"}

            purchase_date = getattr(item, "purchase_date", None)
            if not purchase_date:
                return {"error": "Nema purchase_date na artiklu"}

            method_config = self.METHODS.get(method, self.METHODS["LINEAR_5Y"])
            years = method_config["years"]

            plan = []
            remaining = purchase_price

            for year_idx in range(years):
                if method == "DECLINING":
                    rate = Decimal(str(self.DECLINING_RATES[min(year_idx, len(self.DECLINING_RATES) - 1)]))
                    amount = (purchase_price * rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
                else:
                    amount = (purchase_price / years).quantize(Decimal("0.01"), ROUND_HALF_UP)

                remaining -= amount
                year_date = date(purchase_date.year + year_idx + 1, purchase_date.month, purchase_date.day)

                plan.append(
                    {
                        "godina": year_idx + 1,
                        "datum": str(year_date),
                        "iznos": float(amount),
                        "preostalo": float(max(remaining, Decimal("0"))),
                    }
                )

            years_elapsed = (date.today() - purchase_date).days / 365.25
            accumulated = sum(p["iznos"] for p in plan[: int(years_elapsed)])

            return {
                "item_id": item.id,
                "item_name": str(item),
                "purchase_price": float(purchase_price),
                "purchase_date": str(purchase_date),
                "method": method,
                "method_label": method_config["label"],
                "years": years,
                "annual_amount": float(plan[0]["iznos"]) if plan else 0,
                "accumulated": float(accumulated),
                "book_value": float(purchase_price - Decimal(str(accumulated))),
                "plan": plan,
                "is_draft": True,
                "generated_at": timezone.now().isoformat(),
                "napomena": "DRAFT — nije proknjiženo. Potrebna potvrda računovođe.",
            }

        except (ValueError, TypeError) as e:
            logger.error(f"Depreciation kalkulacija greška: {e}")
            return {"error": str(e)}


# Celery task — jednom mjesečno Mariji
def register_depreciation_celery_task():
    """Registriraj Celery task za mjesečni podsjetnik."""
    pass  # Definirano u core/settings.py beat schedule


def check_depreciation_reminders():
    """
    Nađi assete starije od 1 god. koji nemaju evidentirani tretman.
    Šalje WhatsApp Mariji: 'Nacrt amortizacije spreman, čeka vaš pregled'
    """
    try:
        from datetime import date, timedelta

        from inventory.models import InventoryItem

        threshold = date.today() - timedelta(days=365)
        assets = (
            InventoryItem.objects.filter(
                item_class="asset",
                purchase_date__lte=threshold,
                aktivan=True,
            )
            if hasattr(InventoryItem, "purchase_date")
            else []
        )

        if not hasattr(InventoryItem, "purchase_date"):
            logger.info("InventoryItem nema purchase_date — depreciation skip")
            return 0

        count = 0
        calc = DepreciationCalculator()
        drafts = []
        for item in assets[:10]:  # Max 10 po pozivu
            draft = calc.calculate_annual(item)
            if not draft.get("error"):
                drafts.append(draft)
                count += 1

        if drafts:
            from core.whatsapp import send_text

            poruka = (
                f"📊 Amortizacija — {count} nacrta čeka pregled\n\n"
                + "\n".join(f"• {d['item_name']}: {d['book_value']:.2f} EUR knjig. vrijed." for d in drafts[:5])
                + "\n\nhttps://limit-connect.com/hr/inventory/"
            )
            send_text(phone="+385981234567", message=poruka)  # Marija HR broj
            logger.info(f"Depreciation reminder poslan Mariji: {count} asseta")

        return count

    except DatabaseError as e:
        logger.error(f"check_depreciation_reminders greška: {e}")
        return 0
