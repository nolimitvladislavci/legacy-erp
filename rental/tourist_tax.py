"""
rental/tourist_tax.py — Boravišna pristojba kalkulator

Paušalni iznajmljivač plaća fiksni iznos PO KREVETU tromjesečno.
Odluku o iznosu donosi JLS (grad/općina).
"""

from decimal import Decimal

TOURIST_TAX_RATES = {
    "high": {"adult": Decimal("2.65"), "youth": Decimal("1.33"), "child": Decimal("0")},
    "medium": {"adult": Decimal("1.86"), "youth": Decimal("0.93"), "child": Decimal("0")},
    "low": {"adult": Decimal("1.33"), "youth": Decimal("0.66"), "child": Decimal("0")},
    "undeveloped": {"adult": Decimal("0.53"), "youth": Decimal("0.27"), "child": Decimal("0")},
}


def calculate_quarterly_tax(company, rental_property, quarter: int, year: int) -> dict:
    """
    Izračun tromjesečne boravišne pristojbe za paušalnog iznajmljivača.
    """
    from datetime import date

    settings = getattr(company, "settings", None) or {}
    pausal_per_bed = Decimal(str(settings.get("tourist_tax_pausal_per_bed", "40")))
    beds = rental_property.capacity or 1

    quarterly = (pausal_per_bed * beds / 4).quantize(Decimal("0.01"))

    deadlines = {
        1: date(year, 3, 31),
        2: date(year, 7, 31),
        3: date(year, 8, 31),
        4: date(year, 9, 30),
    }

    return {
        "beds": beds,
        "pausal_per_bed": pausal_per_bed,
        "quarterly_total": quarterly,
        "annual_total": (pausal_per_bed * beds).quantize(Decimal("0.01")),
        "payment_deadline": deadlines.get(quarter),
        "year": year,
        "quarter": quarter,
    }


def calculate_booking_tourist_tax(booking) -> Decimal:
    """Boravišna pristojba za konkretan booking (po noćenju, ne paušal)."""
    nights = (booking.check_out - booking.check_in).days or 1
    guest_count = 0

    if hasattr(booking, "guests"):
        guests = booking.guests.all()
        for g in guests:
            cat = g.tourist_tax_category()
            if cat == "odrasli":
                guest_count += 1
            elif cat == "popust_50":
                guest_count += Decimal("0.5")
            # besplatno = 0
    else:
        guest_count = booking.guest_count or 1

    tax_per_night = booking.rental_property.tourist_tax or Decimal("1.00")
    return (tax_per_night * guest_count * nights).quantize(Decimal("0.01"))


# ═══════════════════════════════════════════════════════════════
#  EU Rental Tax Engine — HR fiksna + DE/AT postotna pristojba
# ═══════════════════════════════════════════════════════════════

# HR razredi mjesta → dnevna pristojba po osobi (EUR, 2026)
HR_RAZRED_RATES = {
    "A": Decimal("2.65"),  # Turisticko mjesto 1. kategorije
    "B": Decimal("1.86"),  # Turisticko mjesto 2. kategorije
    "C": Decimal("1.33"),  # Zagreb, Osijek, Rijeka
    "D": Decimal("0.53"),  # Potpomognuto podrucje
}

# DE City Tax stope po gradu
DE_CITY_TAX = {
    "CITY_TAX_5_PERCENT": Decimal("5"),  # Berlin, Hamburg, etc.
    "CITY_TAX_7_PERCENT": Decimal("7"),  # München
}

# AT Ortstaxe stope
AT_ORTSTAXE = {
    "AT_ORTSTAXE_PERCENT": Decimal("3.2"),  # Beč, Salzburg, Tirol varijable
}


class RentalTaxEngine:
    """
    Univerzalni kalkulator turisticke pristojbe.
    Radi s rental.Property modelom.
    Automatski detektira pravilo po property.tax_calculation_rule.
    """

    def __init__(self, rental_property):
        self.prop = rental_property
        self.rule = getattr(rental_property, "tax_calculation_rule", "HR_FIXED_BORAVISNA")

    def calculate_daily_tax(self, for_date=None, base_price=None, guest_count=1):
        """
        Izracun dnevne pristojbe po osobi.

        Args:
            for_date: datum (za sezonske varijacije)
            base_price: cijena nocenja (za postotne pristojbe)
            guest_count: broj gostiju

        Returns:
            dict: {type, amount, per_person, total, rule, detail}
        """
        if self.rule == "HR_FIXED_BORAVISNA":
            return self._hr_fixed(guest_count)
        elif self.rule in DE_CITY_TAX:
            return self._percentage_tax(base_price, guest_count, DE_CITY_TAX[self.rule], "PERCENTAGE_CITY_TAX")
        elif self.rule in AT_ORTSTAXE:
            return self._percentage_tax(base_price, guest_count, AT_ORTSTAXE[self.rule], "PERCENTAGE_ORTSTAXE")
        elif self.rule == "NONE":
            return {
                "type": "NONE",
                "amount": Decimal("0"),
                "per_person": Decimal("0"),
                "total": Decimal("0"),
                "rule": "NONE",
                "detail": "Bez pristojbe",
            }
        else:
            # Fallback na HR fiksnu
            return self._hr_fixed(guest_count)

    def _hr_fixed(self, guest_count=1):
        razred = getattr(self.prop, "razred_mjesta", "A") or "A"
        per_person = HR_RAZRED_RATES.get(razred, Decimal("1.33"))

        # Override iz property.tourist_tax ako je postavljen
        if self.prop.tourist_tax and self.prop.tourist_tax > 0:
            per_person = Decimal(str(self.prop.tourist_tax))

        total = (per_person * guest_count).quantize(Decimal("0.01"))
        return {
            "type": "FIXED_BORAVISNA",
            "amount": per_person,
            "per_person": per_person,
            "total": total,
            "rule": "HR_FIXED_BORAVISNA",
            "detail": f"Razred {razred}: {per_person} EUR/os/noc x {guest_count} gostiju",
        }

    def _percentage_tax(self, base_price, guest_count, rate, tax_type):
        base = Decimal(str(base_price or 0))
        amount = (base * rate / Decimal("100")).quantize(Decimal("0.01"))
        return {
            "type": tax_type,
            "amount": amount,
            "per_person": amount,  # Per booking, not per person for city tax
            "total": amount,
            "rule": self.rule,
            "detail": f"{rate}% od {base} EUR = {amount} EUR",
        }

    def calculate_stay_tax(self, nights, guest_count=1, base_price_per_night=None):
        """Ukupna pristojba za cijeli boravak."""
        daily = self.calculate_daily_tax(base_price=base_price_per_night, guest_count=guest_count)
        total = (daily["total"] * nights).quantize(Decimal("0.01"))
        return {
            **daily,
            "nights": nights,
            "stay_total": total,
        }
