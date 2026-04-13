"""
Management command: Create JournalEntry temeljnice for PAID invoices.

Usage:
  venv/bin/python manage.py create_journal_entries --dry-run --company=37590751921
  venv/bin/python manage.py create_journal_entries --dry-run --limit=10
  venv/bin/python manage.py create_journal_entries --company=37590751921  # REAL RUN
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import DatabaseError, IntegrityError, transaction

from companies.models import Company
from invoicing.models import Invoice
from konto.models import JournalEntry, KontoAccount, LedgerLine
from konto.services_file import _next_entry_number

# Default konto plan mapping
KONTO_MAP = {
    "ira": {
        "debit": "1200",  # Potraživanja od kupaca
        "credit_revenue": "7500",  # Prihodi od prodaje
        "credit_vat": "2400",  # Obveze za PDV
    },
    "ura": {
        "debit_expense": "4000",  # Troškovi materijala/usluga
        "debit_vat": "1400",  # Pretporez (ulazni PDV)
        "credit": "2200",  # Obveze prema dobavljačima
    },
}


def _get_or_create_account(company, code, name=""):
    acc = KontoAccount.objects.filter(company=company, code=code).first()
    if not acc:
        acc = KontoAccount.objects.create(
            company=company,
            code=code,
            name=name or f"Konto {code}",
            account_type="asset"
            if code.startswith(("1", "0"))
            else ("liability" if code.startswith("2") else ("revenue" if code.startswith("7") else "expense")),
        )
    return acc


class Command(BaseCommand):
    help = "Create JournalEntry temeljnice for PAID invoices without one."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="Company OIB filter")
        parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
        parser.add_argument("--limit", type=int, default=0, help="Max entries to create")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        company_oib = options.get("company")

        companies = Company.objects.all()
        if company_oib:
            companies = companies.filter(oib=company_oib)

        total_created = 0
        total_skipped = 0

        for company in companies:
            paid_invs = Invoice.objects.filter(company=company, status="PAID", number__startswith="SYN-").exclude(
                pk__in=JournalEntry.objects.filter(company=company, source_invoice__isnull=False).values_list(
                    "source_invoice_id", flat=True
                )
            )

            if not paid_invs.exists():
                continue

            self.stdout.write(f"\n{company.name} ({company.oib}): {paid_invs.count()} bez temeljnice")

            for inv in paid_invs:
                if limit and total_created >= limit:
                    self.stdout.write(self.style.WARNING(f"  Limit {limit} dosegnut"))
                    break

                is_ura = "URA" in inv.number.upper()
                subtotal = Decimal(str(inv.subtotal or 0))
                tax = Decimal(str(inv.tax_amount or 0))
                total = Decimal(str(inv.total or 0))

                if total == 0 and subtotal == 0:
                    total_skipped += 1
                    continue

                if dry_run:
                    if is_ura:
                        self.stdout.write(
                            f"  [DRY] {inv.number}: D {KONTO_MAP['ura']['debit_expense']} {subtotal} "
                            f"+ D {KONTO_MAP['ura']['debit_vat']} {tax} "
                            f"/ C {KONTO_MAP['ura']['credit']} {total}"
                        )
                    else:
                        self.stdout.write(
                            f"  [DRY] {inv.number}: D {KONTO_MAP['ira']['debit']} {total} "
                            f"/ C {KONTO_MAP['ira']['credit_revenue']} {subtotal} "
                            f"+ C {KONTO_MAP['ira']['credit_vat']} {tax}"
                        )
                    total_created += 1
                    continue

                try:
                    with transaction.atomic():
                        prefix = "URA" if is_ura else "IRA"
                        entry_number = _next_entry_number(company, prefix)

                        je = JournalEntry.objects.create(
                            company=company,
                            entry_number=entry_number,
                            date=inv.date_issued or inv.created_at.date(),
                            description=f"{inv.number} — {inv.client_name}"[:300],
                            source_type="synesis",
                            source_invoice=inv,
                            is_posted=True,
                        )

                        if is_ura:
                            # D: Troškovi + Pretporez / C: Obveze
                            if subtotal:
                                LedgerLine.objects.create(
                                    journal_entry=je,
                                    account=_get_or_create_account(
                                        company, KONTO_MAP["ura"]["debit_expense"], "Troškovi"
                                    ),
                                    side="debit",
                                    amount=subtotal,
                                    description=inv.number,
                                )
                            if tax:
                                LedgerLine.objects.create(
                                    journal_entry=je,
                                    account=_get_or_create_account(company, KONTO_MAP["ura"]["debit_vat"], "Pretporez"),
                                    side="debit",
                                    amount=tax,
                                    description=f"PDV {inv.number}",
                                )
                            LedgerLine.objects.create(
                                journal_entry=je,
                                account=_get_or_create_account(
                                    company, KONTO_MAP["ura"]["credit"], "Obveze dobavljačima"
                                ),
                                side="credit",
                                amount=total,
                                description=inv.number,
                            )
                        else:
                            # D: Potraživanja / C: Prihodi + PDV
                            LedgerLine.objects.create(
                                journal_entry=je,
                                account=_get_or_create_account(
                                    company, KONTO_MAP["ira"]["debit"], "Potraživanja kupci"
                                ),
                                side="debit",
                                amount=total,
                                description=inv.number,
                            )
                            if subtotal:
                                LedgerLine.objects.create(
                                    journal_entry=je,
                                    account=_get_or_create_account(
                                        company, KONTO_MAP["ira"]["credit_revenue"], "Prihodi prodaje"
                                    ),
                                    side="credit",
                                    amount=subtotal,
                                    description=inv.number,
                                )
                            if tax:
                                LedgerLine.objects.create(
                                    journal_entry=je,
                                    account=_get_or_create_account(
                                        company, KONTO_MAP["ira"]["credit_vat"], "Obveze PDV"
                                    ),
                                    side="credit",
                                    amount=tax,
                                    description=f"PDV {inv.number}",
                                )

                        total_created += 1

                except (IntegrityError, DatabaseError) as e:
                    self.stderr.write(f"  ERROR {inv.number}: {e}")

        mode = "DRY RUN" if dry_run else "CREATED"
        self.stdout.write(
            self.style.SUCCESS(f"\n{mode}: {total_created} temeljnica, {total_skipped} preskočeno (0 iznos)")
        )
