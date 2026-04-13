"""Asset Depreciation Engine."""
from datetime import date
from decimal import Decimal

from django.db import transaction

from .models import Asset, DepreciationLog


def calculate_monthly_depreciation(asset):
    if asset.depreciation_method == "linear":
        depreciable = asset.purchase_price - asset.salvage_value
        if asset.useful_life_months <= 0:
            return Decimal("0")
        return (depreciable / asset.useful_life_months).quantize(Decimal("0.01"))
    elif asset.depreciation_method == "declining":
        rate = asset.depreciation_rate or Decimal("20")
        annual = asset.current_value * rate / 100
        return (annual / 12).quantize(Decimal("0.01"))
    return Decimal("0")


@transaction.atomic
def run_monthly_depreciation(company, year, month):
    from konto.models import JournalEntry, KontoAccount, LedgerLine
    from konto.services import _next_entry_number
    assets = Asset.objects.filter(company=company, status="active")
    entries = []
    for asset in assets:
        if DepreciationLog.objects.filter(asset=asset, year=year, month=month).exists():
            continue
        monthly_amount = calculate_monthly_depreciation(asset)
        if monthly_amount <= 0:
            continue
        max_dep = asset.purchase_price - asset.salvage_value
        if asset.accumulated_depreciation >= max_dep:
            continue
        remaining = max_dep - asset.accumulated_depreciation
        if monthly_amount > remaining:
            monthly_amount = remaining
        dep_acct, _ = KontoAccount.objects.get_or_create(company=company, code="4300",
            defaults={"name": "Amortizacija dugotrajne imovine", "account_type": "expense"})
        contra_acct, _ = KontoAccount.objects.get_or_create(company=company, code="0290",
            defaults={"name": "Ispravak vrijednosti imovine", "account_type": "asset"})
        entry_number = _next_entry_number(company, "DEP")
        je = JournalEntry.objects.create(company=company, entry_number=entry_number,
            date=date(year, month, 1),
            description=f"Amortizacija: {asset.name} ({asset.asset_code})",
            source_type="depreciation", is_posted=True)
        LedgerLine.objects.create(journal_entry=je, account=dep_acct, side="debit", amount=monthly_amount)
        LedgerLine.objects.create(journal_entry=je, account=contra_acct, side="credit", amount=monthly_amount)
        asset.accumulated_depreciation += monthly_amount
        asset.current_value = asset.purchase_price - asset.accumulated_depreciation
        asset.last_depreciation_date = date(year, month, 1)
        asset.save(update_fields=["accumulated_depreciation", "current_value", "last_depreciation_date"])
        DepreciationLog.objects.create(company=company, asset=asset, year=year, month=month,
            amount=monthly_amount, journal_entry_number=entry_number)
        entries.append(je)
    return entries
