"""
core/management/commands/seed_demo_data.py

Popunjava bazu realističnim demo podacima za firmu VISKOVIC NIKSA.
Idempotent: koristi get_or_create. Sve fakture/partneri nose oznaku DEMO_DATA.

Upotreba:
    python manage.py seed_demo_data          # dodaj demo podatke
    python manage.py seed_demo_data --reset  # briši stare i dodaj nove
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import DatabaseError, IntegrityError
from django.utils import timezone

User = get_user_model()

DEMO_TAG = "DEMO_DATA"


class Command(BaseCommand):
    help = "Seed demo data for VISKOVIC NIKSA (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing DEMO_DATA objects before seeding",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        self.stdout.write("=== seed_demo_data START ===")

        company = self._get_company()
        if company is None:
            self.stderr.write("ERROR: VISKOVIC NIKSA not found in DB")
            return

        self.stdout.write(f"Company: {company.name} (pk={company.pk})")

        if reset:
            self._reset(company)

        admin_user = self._get_or_create_admin(company)
        manager_user = self._get_or_create_manager(company)
        worker_user = self._get_or_create_worker(company)
        self.stdout.write("Users OK")

        tax_std, tax_red = self._ensure_tax_rates(company)
        self.stdout.write("TaxRates OK")

        profile = self._ensure_invoice_profile(company, tax_std)
        self.stdout.write("InvoiceProfile OK")

        partners = self._ensure_partners(company)
        self.stdout.write(f"Partners OK ({len(partners)})")

        items = self._ensure_inventory(company, tax_std, tax_red)
        self.stdout.write(f"InventoryItems OK ({len(items)})")

        invoices = self._ensure_invoices(company, partners, items, profile, tax_std, tax_red)
        self.stdout.write(f"Invoices OK ({len(invoices)})")

        terminal, session = self._ensure_pos(company, admin_user)
        self.stdout.write("POS OK")

        self._ensure_pos_receipts(session, items, tax_std)
        self.stdout.write("POSReceipts OK")

        projects = self._ensure_projects(company, manager_user, partners)
        self.stdout.write(f"Projects OK ({len(projects)})")

        self._ensure_time_entries(company, projects, worker_user, manager_user)
        self.stdout.write("TimeEntries OK")

        self._ensure_appointments(company, partners, manager_user)
        self.stdout.write("Appointments OK")

        self._ensure_leads(company, admin_user)
        self.stdout.write("ProjectLeads OK")

        self._ensure_interventions(company, worker_user)
        self.stdout.write("HitnaIntervencija OK")

        self._ensure_bank(company, invoices)
        self.stdout.write("BankTransactions OK")

        self.stdout.write(self.style.SUCCESS("=== seed_demo_data DONE ==="))

    # ── helpers ────────────────────────────────────────────────────────────────

    def _get_company(self):
        from companies.models import Company
        return (
            Company.objects.filter(name__icontains="VISKOVIC").first()
            or Company.objects.filter(name__icontains="Viskovic").first()
        )

    def _days_ago(self, n):
        return timezone.now() - timedelta(days=n)

    def _date_ago(self, n):
        return date.today() - timedelta(days=n)

    # ── reset ──────────────────────────────────────────────────────────────────

    def _reset(self, company):
        from invoicing.models import Invoice
        from partners.models import Partner

        deleted_inv = Invoice.objects.filter(
            company=company, internal_note=DEMO_TAG
        ).count()
        Invoice.objects.filter(company=company, internal_note=DEMO_TAG).delete()
        self.stdout.write(f"Deleted {deleted_inv} demo invoices")

        deleted_p = Partner.objects.filter(company=company, notes=DEMO_TAG).count()
        Partner.objects.filter(company=company, notes=DEMO_TAG).delete()
        self.stdout.write(f"Deleted {deleted_p} demo partners")

        try:
            from burza.models import ProjectLead
            ProjectLead.objects.filter(company=company, internal_notes=DEMO_TAG).delete()
        except (IntegrityError, DatabaseError):
            pass

    # ── users ──────────────────────────────────────────────────────────────────

    def _get_or_create_admin(self, company):
        from accounts.models import UserProfile
        user, _ = User.objects.get_or_create(
            username="admin_viskovic",
            defaults=dict(email="admin@viskovic.de", first_name="Admin", last_name="Viskovic"),
        )
        if not user.has_usable_password():
            user.set_password("AdminDemo2026!")
            user.save()
        UserProfile.objects.get_or_create(
            user=user,
            defaults=dict(company=company, role="company_admin"),
        )
        return user

    def _get_or_create_manager(self, company):
        from accounts.models import UserProfile
        user, _ = User.objects.get_or_create(
            username="manager_viskovic",
            defaults=dict(email="manager@viskovic.de", first_name="Mark", last_name="Manager"),
        )
        if not user.has_usable_password():
            user.set_password("ManagerDemo2026!")
            user.save()
        UserProfile.objects.get_or_create(
            user=user,
            defaults=dict(company=company, role="project_manager"),
        )
        return user

    def _get_or_create_worker(self, company):
        from accounts.models import UserProfile
        user, created = User.objects.get_or_create(
            username="arbeiter_viskovic",
            defaults=dict(email="arbeiter@viskovic.de", first_name="Hans", last_name="Arbeiter"),
        )
        if created or not user.has_usable_password():
            user.set_password("ArbeiterDemo2026!")
            user.save()
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults=dict(company=company, role="worker", must_change_password=True),
        )
        if not profile.must_change_password:
            profile.must_change_password = True
            profile.save(update_fields=["must_change_password"])
        return user

    # ── tax rates ──────────────────────────────────────────────────────────────

    def _ensure_tax_rates(self, company):
        from companies.models import TaxRate
        std, _ = TaxRate.objects.get_or_create(
            country="DE", rate=Decimal("19.00"),
            defaults=dict(name="MwSt Standard 19%"),
        )
        red, _ = TaxRate.objects.get_or_create(
            country="DE", rate=Decimal("7.00"),
            defaults=dict(name="MwSt Ermassigt 7%"),
        )
        return std, red

    # ── invoice profile ────────────────────────────────────────────────────────

    def _ensure_invoice_profile(self, company, tax_std):
        from invoicing.fiscal_models import InvoiceProfile
        profile, _ = InvoiceProfile.objects.get_or_create(
            company=company,
            invoice_prefix="VIS",
            defaults=dict(
                name="VIS — Viskovic Fakturiranje",
                is_default=True,
                is_active=True,
                company_name=company.name,
                country="DE",
                currency="EUR",
                default_tax_rate=tax_std,
                default_due_days=14,
                default_payment_method="UBERWEISUNG",
            ),
        )
        return profile

    # ── partners ───────────────────────────────────────────────────────────────

    def _ensure_partners(self, company):
        from partners.models import Partner
        data = [
            dict(name="Muller Bau GmbH", partner_type="client",
                 city="Munchen", country="DE", email="muller@bau.de",
                 oib="DE-DEMO-0001"),
            dict(name="Weber Renovierungen", partner_type="client",
                 city="Stuttgart", country="DE", email="info@weber-ren.de",
                 oib="DE-DEMO-0002"),
            dict(name="Schmidt und Partner", partner_type="client",
                 city="Nurnberg", country="DE", email="schmidt@partner.de",
                 oib="DE-DEMO-0003"),
            dict(name="Baumarkt Express", partner_type="supplier",
                 city="Augsburg", country="DE", email="orders@baumarkt-express.de",
                 oib="DE-DEMO-0004"),
        ]
        partners = []
        for d in data:
            # Use oib as idempotency key (unique per company)
            obj = Partner.objects.filter(company=company, oib=d["oib"]).first()
            if obj is None:
                obj = Partner.objects.create(company=company, notes=DEMO_TAG, **d)
            partners.append(obj)
        return partners

    # ── inventory ──────────────────────────────────────────────────────────────

    def _ensure_inventory(self, company, tax_std, tax_red):
        from inventory.models import InventoryItem
        items_data = [
            dict(name="Fliesen 60x60 cm", sku="FLI-6060", category="material",
                 unit="m2", quantity=200, unit_price=Decimal("18.50"), purchase_price=Decimal("12.00"),
                 description="Bodenfliesen grau matt"),
            dict(name="Fugenmasse weiss", sku="FUG-WEI", category="consumable",
                 unit="kg", quantity=50, unit_price=Decimal("4.90"), purchase_price=Decimal("2.80")),
            dict(name="Zement 25kg", sku="ZEM-25", category="material",
                 unit="vr", quantity=100, unit_price=Decimal("8.90"), purchase_price=Decimal("5.50")),
            dict(name="Silikon transparent", sku="SIL-TRA", category="consumable",
                 unit="kom", quantity=40, unit_price=Decimal("6.50"), purchase_price=Decimal("3.20")),
            dict(name="Duschkabine 90x90", sku="DUS-90", category="product",
                 unit="kom", quantity=5, unit_price=Decimal("389.00"), purchase_price=Decimal("220.00")),
            dict(name="Badewanne 170cm", sku="BAD-170", category="product",
                 unit="kom", quantity=3, unit_price=Decimal("499.00"), purchase_price=Decimal("280.00")),
            dict(name="Montage-Stunde", sku="MON-STD", category="service",
                 unit="h", quantity=999, unit_price=Decimal("65.00"), purchase_price=Decimal("0")),
            dict(name="Werkzeugvermietung", sku="WRK-MIE", category="service",
                 unit="dan", quantity=999, unit_price=Decimal("35.00"), purchase_price=Decimal("0")),
            dict(name="Klebemörtel 25kg", sku="KLE-25", category="material",
                 unit="vr", quantity=80, unit_price=Decimal("12.50"), purchase_price=Decimal("7.00")),
            dict(name="Wannenabdichtung Set", sku="WAB-SET", category="consumable",
                 unit="kom", quantity=20, unit_price=Decimal("24.90"), purchase_price=Decimal("14.00")),
        ]
        items = []
        for d in items_data:
            obj, _ = InventoryItem.objects.get_or_create(
                company=company,
                sku=d["sku"],
                defaults={**d, "company": company, "is_active": True},
            )
            items.append(obj)
        return items

    # ── invoices ───────────────────────────────────────────────────────────────

    def _ensure_invoices(self, company, partners, items, profile, tax_std, tax_red):
        from invoicing.models import Invoice, InvoiceItem
        muller, weber, schmidt, baumarkt = partners[:4]

        specs = [
            # (number, doctype, status, partner, days_ago, item_pairs)
            ("VIS-2026-0001", "R", "PAID",   muller,   85, [(items[0], 20, Decimal("18.50")), (items[6], 8, Decimal("65.00"))]),
            ("VIS-2026-0002", "R", "PAID",   weber,    70, [(items[4], 1, Decimal("389.00")), (items[6], 6, Decimal("65.00"))]),
            ("VIS-2026-0003", "R", "PAID",   schmidt,  55, [(items[1], 10, Decimal("4.90")), (items[2], 5, Decimal("8.90"))]),
            ("VIS-2026-0004", "R", "SENT",   muller,   30, [(items[5], 1, Decimal("499.00")), (items[6], 12, Decimal("65.00"))]),
            ("VIS-2026-0005", "R", "SENT",   weber,    20, [(items[0], 15, Decimal("18.50")), (items[8], 10, Decimal("12.50"))]),
            ("VIS-2026-0006", "R", "OVERDUE",schmidt,  35, [(items[6], 20, Decimal("65.00")), (items[3], 5, Decimal("6.50"))]),
            ("VIS-2026-0007", "R", "DRAFT",  muller,   5,  [(items[9], 4, Decimal("24.90")), (items[6], 4, Decimal("65.00"))]),
            ("VIS-2026-0008", "R", "DRAFT",  weber,    2,  [(items[4], 2, Decimal("389.00"))]),
            ("VIS-2026-0009", "PO","ACCEPTED",muller,  45, [(items[6], 40, Decimal("65.00")), (items[0], 30, Decimal("18.50"))]),
            ("VIS-2026-0010", "P", "SENT",   schmidt,  25, [(items[5], 2, Decimal("499.00")), (items[6], 8, Decimal("65.00"))]),
        ]

        invoices = []
        for number, doctype, status, partner, days, item_specs in specs:
            inv, created = Invoice.objects.get_or_create(
                number=number,
                defaults=dict(
                    company=company,
                    invoice_profile=profile,
                    partner=partner,
                    doctype=doctype,
                    country="DE",
                    status=status,
                    date_issued=self._days_ago(days),
                    date_due=self._date_ago(days - 14),
                    client_name=partner.name,
                    client_city=partner.city,
                    client_country="Deutschland",
                    payment_method="UBERWEISUNG",
                    currency="EUR",
                    internal_note=DEMO_TAG,
                ),
            )
            if created:
                subtotal = Decimal("0")
                tax_sum = Decimal("0")
                for idx, (item, qty, price) in enumerate(item_specs):
                    net = Decimal(str(qty)) * price
                    tax = round(net * Decimal("19") / Decimal("100"), 2)
                    InvoiceItem.objects.create(
                        invoice=inv,
                        description=item.name,
                        quantity=qty,
                        unit_price=price,
                        total_price=net,
                        gross_total=net + tax,
                        tax_rate=Decimal("19.00"),
                        tax_rate_obj=tax_std,
                        discount_percent=Decimal("0"),
                    )
                    subtotal += net
                    tax_sum += tax
                inv.subtotal = subtotal
                inv.tax_amount = tax_sum
                inv.total = subtotal + tax_sum
                inv.save(update_fields=["subtotal", "tax_amount", "total"])
            invoices.append(inv)
        return invoices

    # ── POS ────────────────────────────────────────────────────────────────────

    def _ensure_pos(self, company, operator):
        from pos.models import POSSession, POSTerminal
        terminal, _ = POSTerminal.objects.get_or_create(
            company=company,
            terminal_code="VIS-POS-001",
            defaults=dict(
                name="Kasa 1",
                pos_type="retail",
                is_active=True,
                description="Demo blagajna",
            ),
        )
        session, _ = POSSession.objects.get_or_create(
            terminal=terminal,
            session_number=1,
            defaults=dict(
                operator=operator,
                status="open",
                opening_cash=Decimal("200.00"),
            ),
        )
        return terminal, session

    def _ensure_pos_receipts(self, session, items, tax_std):
        from pos.models import POSReceipt, POSReceiptItem
        montage = next((i for i in items if "Montage" in i.name), items[6])
        fliesen = next((i for i in items if "Fliesen" in i.name), items[0])

        receipt_specs = [
            # (receipt_number, status, item1, qty1, item2, qty2)
            (1, "paid",  montage, 2, fliesen,  5),
            (2, "paid",  montage, 3, None,     0),
            (3, "paid",  fliesen, 8, montage,  1),
            (4, "paid",  montage, 4, fliesen,  3),
            (5, "paid",  fliesen, 10, None,    0),
            (6, "paid",  montage, 2, fliesen,  4),
            (7, "open",  montage, 1, None,     0),
            (8, "open",  fliesen, 6, montage,  2),
        ]

        for rn, status, item1, qty1, item2, qty2 in receipt_specs:
            receipt, created = POSReceipt.objects.get_or_create(
                session=session,
                receipt_number=rn,
                defaults=dict(status=status, subtotal=Decimal("0"), tax_amount=Decimal("0"), total=Decimal("0")),
            )
            if created:
                total = Decimal("0")
                tax_total = Decimal("0")
                for item, qty in [(item1, qty1), (item2, qty2)]:
                    if item is None or qty == 0:
                        continue
                    net = item.unit_price * qty
                    tax = round(net * Decimal("19") / Decimal("100"), 2)
                    gross = net + tax
                    POSReceiptItem.objects.create(
                        receipt=receipt,
                        description=item.name,
                        quantity=qty,
                        unit_price=item.unit_price,
                        tax_rate=Decimal("19.00"),
                        total_price=gross,
                    )
                    total += gross
                    tax_total += tax
                subtotal = total - tax_total
                receipt.subtotal = subtotal
                receipt.tax_amount = tax_total
                receipt.total = total
                receipt.save(update_fields=["subtotal", "tax_amount", "total"])

    # ── projects ───────────────────────────────────────────────────────────────

    def _ensure_projects(self, company, manager, partners):
        # TimeEntry.project FK points to worktime.Project, not projects.Project
        from worktime.models import Project as WTProject
        muller, weber = partners[0], partners[1]
        specs = [
            dict(name="Badezimmer Muller", code="BAD-001", status="ACTIVE",
                 client_name=muller.name, company=company,
                 budget_hours=Decimal("130.00"), hourly_rate=Decimal("65.00")),
            dict(name="Renovierung Weber", code="REN-001", status="ACTIVE",
                 client_name=weber.name, company=company,
                 budget_hours=Decimal("185.00"), hourly_rate=Decimal("65.00")),
        ]
        projects = []
        for d in specs:
            obj, _ = WTProject.objects.get_or_create(code=d["code"], defaults=d)
            projects.append(obj)
        return projects

    # ── time entries ────────────────────────────────────────────────────────────

    def _ensure_time_entries(self, company, projects, worker, manager):
        from worktime.models import TimeEntry
        proj = projects[0]  # BAD-001
        entries = [
            # (user, days_ago, hours, status, task_type)
            (worker,  60, Decimal("8.0"),  "APPROVED", "DEVELOPMENT"),
            (worker,  59, Decimal("8.0"),  "APPROVED", "DEVELOPMENT"),
            (worker,  58, Decimal("7.5"),  "APPROVED", "DEVELOPMENT"),
            (worker,  53, Decimal("8.0"),  "APPROVED", "DEVELOPMENT"),
            (worker,  52, Decimal("8.0"),  "APPROVED", "DEVELOPMENT"),
            (worker,  45, Decimal("6.0"),  "APPROVED", "OTHER"),
            (worker,  44, Decimal("8.0"),  "PENDING",  "DEVELOPMENT"),
            (worker,  43, Decimal("8.0"),  "PENDING",  "DEVELOPMENT"),
            (worker,  30, Decimal("8.0"),  "PENDING",  "DEVELOPMENT"),
            (worker,  29, Decimal("7.0"),  "PENDING",  "DEVELOPMENT"),
            (worker,  15, Decimal("8.0"),  "DRAFT",    "DEVELOPMENT"),
            (worker,  14, Decimal("8.0"),  "DRAFT",    "DEVELOPMENT"),
            (manager, 60, Decimal("2.0"),  "APPROVED", "PLANNING"),
            (manager, 53, Decimal("1.5"),  "APPROVED", "MEETING"),
            (manager, 30, Decimal("2.0"),  "APPROVED", "PLANNING"),
        ]
        for user, days_ago, hours, status, task_type in entries:
            entry_date = self._date_ago(days_ago)
            TimeEntry.objects.get_or_create(
                company=company,
                user=user,
                project=proj,
                date=entry_date,
                defaults=dict(
                    duration=hours,
                    status=status,
                    task_type=task_type,
                    description=f"Rad na projektu {proj.name} - {entry_date}",
                    billing_amount=Decimal("0"),
                ),
            )

    # ── appointments ───────────────────────────────────────────────────────────

    def _ensure_appointments(self, company, partners, employee):
        from datetime import time

        from appointments.models import Appointment
        muller, weber, schmidt = partners[0], partners[1], partners[2]

        def dt(days_delta, hour=10):
            d = date.today() + timedelta(days=days_delta)
            return timezone.make_aware(datetime.combine(d, time(hour, 0)))

        specs = [
            dict(title="Erstgesprach - Muller", status="completed",
                 start_time=dt(-30), end_time=dt(-30, 11), client=muller),
            dict(title="Baubesichtigung - Weber", status="completed",
                 start_time=dt(-14), end_time=dt(-14, 12), client=weber),
            dict(title="Angebotsbesprechung - Schmidt", status="confirmed",
                 start_time=dt(1), end_time=dt(1, 11), client=schmidt),
            dict(title="Projektmeeting - Muller", status="scheduled",
                 start_time=dt(7), end_time=dt(7, 11), client=muller),
            dict(title="Abnahme - Weber", status="scheduled",
                 start_time=dt(14), end_time=dt(14, 13), client=weber),
        ]
        for d in specs:
            Appointment.objects.get_or_create(
                company=company,
                title=d["title"],
                defaults={**d, "company": company, "employee": employee},
            )

    # ── project leads (burza) ──────────────────────────────────────────────────

    def _ensure_leads(self, company, created_by):
        from burza.models import ProjectLead
        specs = [
            dict(title="Badezimmer Komplettrenovierung",
                 description="Komplette Badsanierung 8m2, Fliesen + Sanitaer",
                 category="kupaonica", location="Munchen, BY",
                 contact_name="Klaus Fischer", contact_phone="+4989123456",
                 budget_from=Decimal("5000"), budget_to=Decimal("8000"),
                 status="NOVI_UPIT"),
            dict(title="Kellerausbau mit Fliesen",
                 description="Keller 40m2, Boden und Wand Fliesen",
                 category="plocice", location="Stuttgart, BW",
                 contact_name="Petra Bauer", contact_phone="+49711987654",
                 budget_from=Decimal("3000"), budget_to=Decimal("5000"),
                 status="INTERNA_PROCJENA"),
            dict(title="Dachsanierung Einfamilienhaus",
                 description="Dach 120m2, komplett neu eindecken",
                 category="fasada", location="Augsburg, BY",
                 contact_name="Thomas Keller", contact_phone="+49821555666",
                 budget_from=Decimal("15000"), budget_to=Decimal("25000"),
                 status="NA_BURZI", is_public=True),
        ]
        for d in specs:
            ProjectLead.objects.get_or_create(
                company=company,
                title=d["title"],
                defaults={**d, "company": company, "internal_notes": DEMO_TAG},
            )

    # ── interventions ──────────────────────────────────────────────────────────

    def _ensure_interventions(self, company, worker):
        from interventions.models import HitnaIntervencija
        specs = [
            dict(title="Rohrbruch Keller - Muller", category="voda",
                 address="Hauptstr. 12, Munchen", client_name="Klaus Muller",
                 client_phone="+4989111222", status="RIJESENO",
                 assigned_to=worker),
            dict(title="Heizungsausfall - Weber", category="plin",
                 address="Schillerstr. 45, Stuttgart", client_name="Maria Weber",
                 client_phone="+49711333444", status="NA_PUTU",
                 assigned_to=worker),
        ]
        for d in specs:
            HitnaIntervencija.objects.get_or_create(
                company=company,
                title=d["title"],
                defaults={**d, "company": company},
            )

    # ── bank transactions ──────────────────────────────────────────────────────

    def _ensure_bank(self, company, invoices):
        from konto.models import BankAccount, BankTransaction
        account, _ = BankAccount.objects.get_or_create(
            company=company,
            iban="DE89370400440532013000",
            defaults=dict(
                name="Geschäftskonto Viskovic",
                bank_name="Deutsche Bank",
                currency="EUR",
                opening_balance=Decimal("5000.00"),
                current_balance=Decimal("5000.00"),
            ),
        )
        # 3 inflow matched to PAID invoices, 2 outflow
        paid_invoices = [inv for inv in invoices if inv.status == "PAID"]
        tx_specs = []
        for i, inv in enumerate(paid_invoices[:3]):
            tx_specs.append(dict(
                transaction_date=self._date_ago(70 - i * 15),
                amount=inv.total,
                transaction_type="inflow",
                counterparty_name=inv.client_name,
                description=f"Zahlung Rechnung {inv.number}",
                reference_number=inv.number,
                status="matched",
                matched_invoice=inv,
            ))
        tx_specs += [
            dict(
                transaction_date=self._date_ago(50),
                amount=Decimal("750.00"),
                transaction_type="outflow",
                counterparty_name="Baumarkt Express GmbH",
                description="Materialeinkauf Fliesen und Fugenmasse",
                status="unmatched",
            ),
            dict(
                transaction_date=self._date_ago(25),
                amount=Decimal("320.00"),
                transaction_type="outflow",
                counterparty_name="Werkzeugvermietung Bayern",
                description="Werkzeugmiete Monat November",
                status="unmatched",
            ),
        ]
        for d in tx_specs:
            BankTransaction.objects.get_or_create(
                bank_account=account,
                company=company,
                transaction_date=d["transaction_date"],
                amount=d["amount"],
                defaults=d,
            )
