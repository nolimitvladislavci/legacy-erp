"""
core/management/commands/seed_demo_scenarios.py

Kreira 3 demo firme + realistične podatke za prodajnu turneju (14.03.2026.):
  1. Auto Servis Kovač d.o.o.  — radni nalog → BOM → faktura
  2. Salon Elegance j.d.o.o.  — termin → POS naplata
  3. Konoba Dalmatino d.o.o.  — restoran POS + gastro narudžbe

Upotreba:
    python manage.py seed_demo_scenarios
    python manage.py seed_demo_scenarios --reset
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()
DEMO_TAG = "SEED_DEMO_SCENARIO"
TODAY = datetime.date.today()


class Command(BaseCommand):
    help = "Seed 3 demo scenario companies for sales tour"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Delete existing scenario companies before seeding")

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset_all()

        self.stdout.write("\n=== SEED DEMO SCENARIOS ===\n")

        co1, u1 = self._setup_company(
            oib="11223344551",
            name="Auto Servis Kovač d.o.o.",
            city="Osijek",
            address="Vukovarska 42",
            username="kovac_demo",
            label="[1/3] Autoservis"
        )
        self._seed_autoservis(co1, u1)

        co2, u2 = self._setup_company(
            oib="22334455662",
            name="Salon Elegance j.d.o.o.",
            city="Split",
            address="Marmontova 15",
            username="elegance_demo",
            label="[2/3] Frizerski salon"
        )
        self._seed_salon(co2, u2)

        co3, u3 = self._setup_company(
            oib="33445566773",
            name="Konoba Dalmatino d.o.o.",
            city="Split",
            address="Obala kneza Branimira 7",
            username="dalmatino_demo",
            label="[3/3] Restoran"
        )
        self._seed_restoran(co3, u3)

        self.stdout.write("\n=== GOTOVO ===")
        self.stdout.write("Logini:")
        self.stdout.write("  kovac_demo    / demo1234  → Auto Servis Kovač")
        self.stdout.write("  elegance_demo / demo1234  → Salon Elegance")
        self.stdout.write("  dalmatino_demo/ demo1234  → Konoba Dalmatino")

    # ─── Setup helpers ────────────────────────────────────────────────────────

    def _get_tax_rate(self, rate_pct, name=None):
        from companies.models import TaxRate
        tr, _ = TaxRate.objects.get_or_create(
            country="HR", rate=Decimal(str(rate_pct)),
            defaults=dict(name=name or f"PDV {rate_pct}%", is_active=True))
        return tr

    def _setup_company(self, oib, name, city, address, username, label):
        from accounts.models import UserProfile
        from companies.models import Company

        self.stdout.write(f"\n{label}: {name}")
        company, created = Company.objects.get_or_create(
            oib=oib,
            defaults=dict(
                name=name,
                city=city,
                address=address,
                is_platform_owner=True,
                is_vat_registered=True,
                country="HR",
            )
        )
        if not created:
            self.stdout.write("  Firma već postoji — koristi se postojeća")

        user, ucreated = User.objects.get_or_create(
            username=username,
            defaults=dict(is_staff=True, is_superuser=False, email=f"{username}@demo.hr")
        )
        if ucreated:
            user.set_password("demo1234")
            user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.company = company
        profile.save()

        self.stdout.write(f"  Firma: {company.name} (id={company.pk})")
        self.stdout.write(f"  User:  {username} / demo1234")
        return company, user

    def _reset_all(self):
        from companies.models import Company
        for oib in ["11223344551", "22334455662", "33445566773"]:
            try:
                co = Company.objects.get(oib=oib)
                username = {
                    "11223344551": "kovac_demo",
                    "22334455662": "elegance_demo",
                    "33445566773": "dalmatino_demo",
                }[oib]
                User.objects.filter(username=username).delete()
                co.delete()
                self.stdout.write(f"  Reset: {oib} obrisana")
            except Company.DoesNotExist:
                pass

    # ─── SCENARIJ 1: Auto servis ──────────────────────────────────────────────

    def _seed_autoservis(self, company, user):
        from calculator.models import BOM, BOMItem
        from inventory.models import InventoryItem
        from invoicing.models import Invoice
        from partners.models import Partner
        from work_orders.models import WorkOrder, WorkOrderItem

        # Partneri — klijenti servisa
        klijenti_data = [
            dict(name="Marko Petrović", oib="12345678901", partner_type="client",
                 city="Osijek", address="Strossmayerova 12", email="marko.p@email.hr",
                 phone="091 234 5678", notes=DEMO_TAG),
            dict(name="Ana Jurić", oib="23456789012", partner_type="client",
                 city="Osijek", address="Kapucinska 5", email="ana.j@email.hr",
                 phone="098 765 4321", notes=DEMO_TAG),
            dict(name="Tomislav Šimić", oib="34567890123", partner_type="client",
                 city="Đakovo", address="Kralja Tomislava 3", email="t.simic@email.hr",
                 phone="095 111 2233", notes=DEMO_TAG),
            dict(name="Europart d.o.o.", oib="45678901234", partner_type="supplier",
                 city="Zagreb", address="Slavonska avenija 22", email="nabava@europart.hr",
                 phone="01 234 5678", notes=DEMO_TAG),
        ]
        klijenti = []
        for d in klijenti_data:
            obj, _ = Partner.objects.get_or_create(
                company=company, oib=d["oib"], defaults=d)
            klijenti.append(obj)
        marko, ana, tomislav, europart = klijenti
        self.stdout.write(f"  Partneri: {len(klijenti)}")

        # Tax rates
        tax25 = self._get_tax_rate(25, "PDV 25% - standardna")

        # Artikli / zalihe
        artikli_data = [
            dict(name="Motorno ulje 5W-40 (1L)", sku="ULJ-5W40-1L", unit="L",
                 quantity=Decimal("48"), unit_price=Decimal("12.50"),
                 purchase_price=Decimal("8.00"), tax_rate=tax25),
            dict(name="Filter ulja - Peugeot 308", sku="FIL-ULJ-PEU308", unit="kom",
                 quantity=Decimal("15"), unit_price=Decimal("18.00"),
                 purchase_price=Decimal("10.00"), tax_rate=tax25),
            dict(name="Filter zraka - Peugeot 308", sku="FIL-ZRK-PEU308", unit="kom",
                 quantity=Decimal("12"), unit_price=Decimal("22.00"),
                 purchase_price=Decimal("12.00"), tax_rate=tax25),
            dict(name="Disk kočnica prednji (par)", sku="DISK-KOC-PV", unit="par",
                 quantity=Decimal("8"), unit_price=Decimal("85.00"),
                 purchase_price=Decimal("50.00"), tax_rate=tax25),
            dict(name="Svjećice NGK (set/4)", sku="SVJEC-NGK-4", unit="set",
                 quantity=Decimal("20"), unit_price=Decimal("32.00"),
                 purchase_price=Decimal("18.00"), tax_rate=tax25),
            dict(name="Rashladna tekućina (1L)", sku="RASH-TEK-1L", unit="L",
                 quantity=Decimal("30"), unit_price=Decimal("8.50"),
                 purchase_price=Decimal("5.00"), tax_rate=tax25),
            dict(name="Rad - dijagnostika", sku="RAD-DIAG", unit="sat",
                 quantity=Decimal("100"), unit_price=Decimal("45.00"),
                 purchase_price=Decimal("0"), tax_rate=tax25),
            dict(name="Rad - servis/popravak", sku="RAD-SERV", unit="sat",
                 quantity=Decimal("100"), unit_price=Decimal("55.00"),
                 purchase_price=Decimal("0"), tax_rate=tax25),
        ]
        artikli = []
        for d in artikli_data:
            obj, _ = InventoryItem.objects.get_or_create(
                company=company, sku=d["sku"],
                defaults=dict(company=company, **d))
            artikli.append(obj)
        ulje, fil_ulja, fil_zraka, diskovi, svjecice, rashladna, rad_diag, rad_serv = artikli
        self.stdout.write(f"  Artikli: {len(artikli)}")

        # BOM — "Veliki servis Peugeot 308"
        bom, bom_created = BOM.objects.get_or_create(
            company=company,
            name="Veliki servis - Peugeot 308",
            defaults=dict(article=fil_ulja)
        )
        if bom_created:
            BOMItem.objects.create(bom=bom, material=ulje,      quantity=Decimal("4"), unit="L")
            BOMItem.objects.create(bom=bom, material=fil_ulja,  quantity=Decimal("1"), unit="kom")
            BOMItem.objects.create(bom=bom, material=fil_zraka, quantity=Decimal("1"), unit="kom")
            BOMItem.objects.create(bom=bom, material=svjecice,  quantity=Decimal("1"), unit="set")
        self.stdout.write(f"  BOM: {bom.name}")

        # Radni nalozi
        wo_data = [
            dict(
                order_number="RN-2026-0001",
                client=marko,
                description="Veliki servis Peugeot 308 1.6 HDi, 2018. god., reg. OS-123-AA\n"
                            "Zamjena ulja i filtera, svjećice, provjera kočnica.",
                status="in_progress",
                priority="normal",
                scheduled_date=TODAY,
                notes="Vozilo dovedeno u 08:00h. Klijent čeka do 11h.",
            ),
            dict(
                order_number="RN-2026-0002",
                client=ana,
                description="Zamjena disk kočnica - prednji par\nVW Golf VII 2.0 TDI, 2019.",
                status="completed",
                priority="high",
                scheduled_date=TODAY - datetime.timedelta(days=1),
            ),
            dict(
                order_number="RN-2026-0003",
                client=tomislav,
                description="Dijagnostika - pali check engine\nFord Focus 1.5 EcoBoost, 2020.",
                status="draft",
                priority="normal",
                scheduled_date=TODAY + datetime.timedelta(days=2),
            ),
        ]
        work_orders = []
        for d in wo_data:
            wo, created = WorkOrder.objects.get_or_create(
                company=company,
                order_number=d["order_number"],
                defaults=dict(company=company, assigned_to=user, **d)
            )
            work_orders.append(wo)

        # Stavke prvog radnog naloga (in_progress)
        wo1 = work_orders[0]
        if not wo1.items.exists():
            WorkOrderItem.objects.create(
                work_order=wo1, item_type="labor",
                description="Dijagnostika i pregled vozila",
                quantity=Decimal("1"), unit="sat", unit_price=Decimal("45.00"), tax_rate=Decimal("25"))
            WorkOrderItem.objects.create(
                work_order=wo1, item_type="material",
                description="Motorno ulje 5W-40", article=ulje,
                quantity=Decimal("4"), unit="L", unit_price=Decimal("12.50"), tax_rate=Decimal("25"))
            WorkOrderItem.objects.create(
                work_order=wo1, item_type="material",
                description="Filter ulja Peugeot 308", article=fil_ulja,
                quantity=Decimal("1"), unit="kom", unit_price=Decimal("18.00"), tax_rate=Decimal("25"))
            WorkOrderItem.objects.create(
                work_order=wo1, item_type="material",
                description="Filter zraka Peugeot 308", article=fil_zraka,
                quantity=Decimal("1"), unit="kom", unit_price=Decimal("22.00"), tax_rate=Decimal("25"))
            WorkOrderItem.objects.create(
                work_order=wo1, item_type="material",
                description="Svjećice NGK (set/4)", article=svjecice,
                quantity=Decimal("1"), unit="set", unit_price=Decimal("32.00"), tax_rate=Decimal("25"))
            WorkOrderItem.objects.create(
                work_order=wo1, item_type="labor",
                description="Servis - zamjena ulja i filtera",
                quantity=Decimal("1.5"), unit="sat", unit_price=Decimal("55.00"), tax_rate=Decimal("25"))
            wo1.recalculate_totals()

        # Stavke drugog radnog naloga (completed)
        wo2 = work_orders[1]
        if not wo2.items.exists():
            WorkOrderItem.objects.create(
                work_order=wo2, item_type="material",
                description="Disk kočnica prednji par", article=diskovi,
                quantity=Decimal("1"), unit="par", unit_price=Decimal("85.00"), tax_rate=Decimal("25"))
            WorkOrderItem.objects.create(
                work_order=wo2, item_type="labor",
                description="Ugradnja disk kočnica",
                quantity=Decimal("1"), unit="sat", unit_price=Decimal("55.00"), tax_rate=Decimal("25"))
            wo2.recalculate_totals()

        self.stdout.write(f"  Radni nalozi: {len(work_orders)}")

        # Fakture
        inv_data = [
            dict(
                number="R-2026-0001",
                client=ana,
                subtotal=Decimal("113.00"),
                tax_amount=Decimal("28.25"),
                total=Decimal("141.25"),
                status="PAID",
                payment_method="GOTOVINA",
                note="Zamjena disk kočnica VW Golf VII",
                date_due=TODAY - datetime.timedelta(days=1),
            ),
            dict(
                number="R-2026-0002",
                client=tomislav,
                subtotal=Decimal("45.00"),
                tax_amount=Decimal("11.25"),
                total=Decimal("56.25"),
                status="SENT",
                payment_method="TRANSAKCIJSKI",
                note="Dijagnostika Ford Focus - check engine",
                date_due=TODAY + datetime.timedelta(days=15),
            ),
            dict(
                number="PO-2026-0001",
                client=marko,
                subtotal=Decimal("176.00"),
                tax_amount=Decimal("44.00"),
                total=Decimal("220.00"),
                status="DRAFT",
                payment_method="TRANSAKCIJSKI",
                note="Ponuda - veliki servis Peugeot 308",
                date_due=TODAY + datetime.timedelta(days=30),
            ),
        ]
        for d in inv_data:
            client = d.pop("client")
            date_due = d.pop("date_due")
            _, created = Invoice.objects.get_or_create(
                number=d["number"],
                defaults=dict(
                    company=company,
                    client_name=client.name,
                    client_oib=client.oib or "",
                    client_address=client.address or "",
                    client_city=client.city or "",
                    date_issued=timezone.now(),
                    date_due=date_due,
                    internal_note=DEMO_TAG,
                    **d
                )
            )
        self.stdout.write(f"  Fakture: {len(inv_data)}")
        self.stdout.write("  ✓ Autoservis seed završen")

    # ─── SCENARIJ 2: Frizerski salon ──────────────────────────────────────────

    def _seed_salon(self, company, user):
        from appointments.models import Appointment, BookingResource, BookingService
        from inventory.models import InventoryItem
        from partners.models import Partner
        from pos.models import POSReceipt, POSReceiptItem, POSSession, POSTerminal

        # Partneri — klijentice
        klijenti_data = [
            dict(name="Ana Novak", oib="56789012345", partner_type="client",
                 city="Split", phone="091 456 7890", email="ana.novak@email.hr", notes=DEMO_TAG),
            dict(name="Petra Horvat", oib="67890123456", partner_type="client",
                 city="Split", phone="095 234 5678", email="petra.h@email.hr", notes=DEMO_TAG),
            dict(name="Maja Blažević", oib="78901234567", partner_type="client",
                 city="Split", phone="098 876 5432", email="maja.b@email.hr", notes=DEMO_TAG),
            dict(name="Ivan Kovač", oib="89012345678", partner_type="client",
                 city="Split", phone="091 111 2233", email="ivan.k@email.hr", notes=DEMO_TAG),
        ]
        klijenti = []
        for d in klijenti_data:
            obj, _ = Partner.objects.get_or_create(
                company=company, oib=d["oib"], defaults=d)
            klijenti.append(obj)
        ana, petra, maja, ivan = klijenti
        self.stdout.write(f"  Partneri: {len(klijenti)}")

        # Resursi (fotelje)
        fotelja1, _ = BookingResource.objects.get_or_create(
            company=company, name="Fotelja 1",
            defaults=dict(description="Glavna fotelja", is_active=True, capacity=1))
        fotelja2, _ = BookingResource.objects.get_or_create(
            company=company, name="Fotelja 2",
            defaults=dict(description="Fotelja kod ulaza", is_active=True, capacity=1))

        # Usluge
        usluge_data = [
            dict(name="Žensko šišanje", duration=datetime.timedelta(minutes=60), price=Decimal("45.00"), is_active=True),
            dict(name="Muško šišanje", duration=datetime.timedelta(minutes=30), price=Decimal("25.00"), is_active=True),
            dict(name="Bojenje kose (cijela glava)", duration=datetime.timedelta(minutes=120), price=Decimal("85.00"), is_active=True),
            dict(name="Pranje + sušenje", duration=datetime.timedelta(minutes=30), price=Decimal("20.00"), is_active=True),
            dict(name="Ombre / Balayage", duration=datetime.timedelta(minutes=180), price=Decimal("120.00"), is_active=True),
            dict(name="Keratinski tretman", duration=datetime.timedelta(minutes=150), price=Decimal("95.00"), is_active=True),
        ]
        usluge = []
        for d in usluge_data:
            obj, _ = BookingService.objects.get_or_create(
                name=d["name"], defaults=d)
            usluge.append(obj)
        sisanje_z, sisanje_m, bojenje, pranje, ombre, keratin = usluge
        self.stdout.write(f"  Usluge: {len(usluge)}")

        # Termini (iduća 3 dana)
        def _appt(client, resource, service, day_offset, hour, minute, mins, status, desc=""):
            st = timezone.make_aware(datetime.datetime.combine(
                TODAY + datetime.timedelta(days=day_offset), datetime.time(hour, minute)))
            et = st + datetime.timedelta(minutes=mins)
            Appointment.objects.get_or_create(
                company=company, client=client, start_time=st,
                defaults=dict(
                    company=company, resource=resource, service=service,
                    title=service.name, end_time=et, status=status,
                    description=desc, appointment_type="service",
                    total_price=service.price, employee=user))

        _appt(ana,   fotelja1, sisanje_z, 1, 9,  0,  60,  "confirmed", "Redovni termin")
        _appt(petra, fotelja2, bojenje,   1, 10, 0,  120, "confirmed", "Bojenje + pranje")
        _appt(maja,  fotelja1, ombre,     2, 11, 0,  180, "scheduled", "Balayage efekt")
        _appt(ivan,  fotelja2, sisanje_m, 2, 10, 0,  30,  "confirmed")
        _appt(ana,   fotelja1, keratin,   3, 9,  0,  150, "confirmed", "Keratinski tretman - 2. put")
        termini_data = [1, 2, 3, 4, 5]  # samo za count
        self.stdout.write(f"  Termini: {len(termini_data)}")

        # POS
        terminal, _ = POSTerminal.objects.get_or_create(
            company=company, terminal_code="ELE-KAS-001",
            defaults=dict(name="Kasa 1", pos_type="quick", is_active=True,
                          description="Blagajna salon"))
        session, _ = POSSession.objects.get_or_create(
            terminal=terminal, session_number=1,
            defaults=dict(operator=user, status="open", opening_cash=Decimal("100.00")))

        # Tax rates
        tax25 = self._get_tax_rate(25, "PDV 25% - standardna")

        # Artikli za POS (usluge kao artikli)
        pos_artikli = [
            dict(sku="SLG-SIS-Z", name="Žensko šišanje", unit_price=Decimal("45.00"),
                 unit="usl", quantity=Decimal("99"), purchase_price=Decimal("0"), tax_rate=tax25),
            dict(sku="SLG-SIS-M", name="Muško šišanje", unit_price=Decimal("25.00"),
                 unit="usl", quantity=Decimal("99"), purchase_price=Decimal("0"), tax_rate=tax25),
            dict(sku="SLG-BOJ",   name="Bojenje kose", unit_price=Decimal("85.00"),
                 unit="usl", quantity=Decimal("99"), purchase_price=Decimal("0"), tax_rate=tax25),
            dict(sku="SLG-PRA",   name="Pranje + sušenje", unit_price=Decimal("20.00"),
                 unit="usl", quantity=Decimal("99"), purchase_price=Decimal("0"), tax_rate=tax25),
        ]
        pos_items = []
        for d in pos_artikli:
            obj, _ = InventoryItem.objects.get_or_create(
                company=company, sku=d["sku"],
                defaults=dict(company=company, **d))
            pos_items.append(obj)
        sis_z_item, sis_m_item, boj_item, pra_item = pos_items

        # POS računi (plaćeni danas)
        receipt_specs = [
            (1, "paid",  [(sis_z_item, 1), (pra_item, 1)]),
            (2, "paid",  [(boj_item, 1), (pra_item, 1)]),
            (3, "paid",  [(sis_m_item, 1)]),
            (4, "paid",  [(sis_z_item, 1)]),
            (5, "open",  [(boj_item, 1)]),
        ]
        for rn, status, items_qty in receipt_specs:
            receipt, created = POSReceipt.objects.get_or_create(
                session=session, receipt_number=rn,
                defaults=dict(status=status, subtotal=Decimal("0"),
                              tax_amount=Decimal("0"), total=Decimal("0")))
            if created:
                total = Decimal("0")
                tax_total = Decimal("0")
                for item, qty in items_qty:
                    net = item.unit_price * qty
                    tax = (net * Decimal("25") / Decimal("100")).quantize(Decimal("0.01"))
                    gross = net + tax
                    POSReceiptItem.objects.create(
                        receipt=receipt, description=item.name,
                        quantity=qty, unit_price=item.unit_price,
                        tax_rate=Decimal("25.00"), total_price=gross)
                    total += gross
                    tax_total += tax
                receipt.subtotal = total - tax_total
                receipt.tax_amount = tax_total
                receipt.total = total
                if status == "paid":
                    receipt.paid_at = timezone.now()
                receipt.save(update_fields=["subtotal", "tax_amount", "total", "paid_at"])

        self.stdout.write(f"  POS receipts: {len(receipt_specs)}")
        self.stdout.write("  ✓ Salon seed završen")

    # ─── SCENARIJ 3: Restoran ─────────────────────────────────────────────────

    def _seed_restoran(self, company, user):
        from inventory.models import InventoryItem
        from pos.models import GastroOrder, GastroOrderItem, POSReceipt, POSReceiptItem, POSSession, POSTerminal, Table

        # Tax rates
        tax13 = self._get_tax_rate(13, "PDV 13% - ugostiteljstvo")

        # Artikli jelovnika
        jelovnik_data = [
            # Hladna predjela
            dict(sku="DAL-PRSUT",  name="Dalmatinski pršut (150g)", unit_price=Decimal("14.00"),
                 unit="porcija", quantity=Decimal("50"), purchase_price=Decimal("7.00")),
            dict(sku="DAL-SIR",    name="Domaći sir s maslinovima", unit_price=Decimal("9.00"),
                 unit="porcija", quantity=Decimal("50"), purchase_price=Decimal("4.00")),
            # Riba
            dict(sku="DAL-BRAN",   name="Brancin na žaru (450g)", unit_price=Decimal("28.00"),
                 unit="porcija", quantity=Decimal("20"), purchase_price=Decimal("14.00")),
            dict(sku="DAL-PRST",   name="Prstaci brudet s palentom", unit_price=Decimal("24.00"),
                 unit="porcija", quantity=Decimal("15"), purchase_price=Decimal("12.00")),
            dict(sku="DAL-LIGNJE", name="Lignje na žaru", unit_price=Decimal("18.00"),
                 unit="porcija", quantity=Decimal("25"), purchase_price=Decimal("9.00")),
            # Meso
            dict(sku="DAL-JANJET", name="Janjetina s ražnja (300g)", unit_price=Decimal("22.00"),
                 unit="porcija", quantity=Decimal("30"), purchase_price=Decimal("11.00")),
            dict(sku="DAL-TELEC",  name="Teletina pod pekom", unit_price=Decimal("26.00"),
                 unit="porcija", quantity=Decimal("20"), purchase_price=Decimal("13.00")),
            # Piće
            dict(sku="DAL-PLAVAC", name="Plavac Mali (0.75L)", unit_price=Decimal("22.00"),
                 unit="boca", quantity=Decimal("60"), purchase_price=Decimal("8.00")),
            dict(sku="DAL-POSIP",  name="Pošip bijelo (0.75L)", unit_price=Decimal("20.00"),
                 unit="boca", quantity=Decimal("60"), purchase_price=Decimal("7.50")),
            dict(sku="DAL-LIMUN",  name="Domaća limonada (1L)", unit_price=Decimal("6.00"),
                 unit="bokal", quantity=Decimal("100"), purchase_price=Decimal("1.50")),
            dict(sku="DAL-PIVO",   name="Craft pivo Pale Ale (0.5L)", unit_price=Decimal("5.50"),
                 unit="boca", quantity=Decimal("100"), purchase_price=Decimal("2.00")),
            # Deserti
            dict(sku="DAL-ROZATA", name="Rožata (domaća)", unit_price=Decimal("7.00"),
                 unit="porcija", quantity=Decimal("30"), purchase_price=Decimal("2.50")),
        ]
        artikli = []
        for d in jelovnik_data:
            obj, _ = InventoryItem.objects.get_or_create(
                company=company, sku=d["sku"],
                defaults=dict(company=company, tax_rate=tax13, **d))
            artikli.append(obj)
        prsut, sir, bran, prst, lignje, janjet, telec, plavac, posip, limun, pivo, rozata = artikli
        self.stdout.write(f"  Jelovnik: {len(artikli)} artikala")

        # POS terminal (restaurant type)
        terminal, _ = POSTerminal.objects.get_or_create(
            company=company, terminal_code="DAL-KAS-001",
            defaults=dict(name="Kasa 1", pos_type="restaurant", is_active=True,
                          description="Glavna kasa - konoba"))
        session, _ = POSSession.objects.get_or_create(
            terminal=terminal, session_number=1,
            defaults=dict(operator=user, status="open", opening_cash=Decimal("500.00")))

        # Stolovi
        stolovi = []
        for i in range(1, 9):
            stol, _ = Table.objects.get_or_create(
                company=company, name=f"Stol {i}",
                defaults=dict(capacity=4,
                              is_occupied=(i <= 3),
                              floor="Terasa" if i <= 4 else "Unutra"))
            stolovi.append(stol)
        self.stdout.write(f"  Stolovi: {len(stolovi)}")

        # Aktivne gastro narudžbe
        gastro_specs = [
            dict(table=stolovi[0], notes="Alergija na gluten - stol 1", items=[
                (prsut, 2), (bran, 2), (plavac, 1), (limun, 1)]),
            dict(table=stolovi[1], notes="", items=[
                (sir, 1), (janjet, 3), (lignje, 1), (plavac, 2)]),
            dict(table=stolovi[2], notes="Djeca — bez alkohola", items=[
                (prst, 2), (telec, 2), (limun, 2), (rozata, 2)]),
        ]
        for spec in gastro_specs:
            order, created = GastroOrder.objects.get_or_create(
                company=company, table=spec["table"],
                defaults=dict(status="open", notes=spec["notes"]))
            if created:
                for item, qty in spec["items"]:
                    GastroOrderItem.objects.create(
                        order=order, inventory_item=item,
                        quantity=qty, notes="", is_ready=False)
        self.stdout.write(f"  Gastro narudžbe: {len(gastro_specs)} aktivne")

        # POS računi (plaćeni)
        receipt_specs = [
            (1, "paid", [(bran, 2), (plavac, 1), (limun, 2)]),
            (2, "paid", [(janjet, 2), (prsut, 1), (pivo, 3), (rozata, 2)]),
            (3, "paid", [(lignje, 2), (sir, 1), (posip, 1)]),
        ]
        for rn, status, items_qty in receipt_specs:
            receipt, created = POSReceipt.objects.get_or_create(
                session=session, receipt_number=rn,
                defaults=dict(status=status, subtotal=Decimal("0"),
                              tax_amount=Decimal("0"), total=Decimal("0")))
            if created:
                total = Decimal("0")
                tax_total = Decimal("0")
                for item, qty in items_qty:
                    net = item.unit_price * qty
                    tax = (net * Decimal("13") / Decimal("100")).quantize(Decimal("0.01"))
                    gross = net + tax
                    POSReceiptItem.objects.create(
                        receipt=receipt, description=item.name,
                        quantity=qty, unit_price=item.unit_price,
                        tax_rate=Decimal("13.00"), total_price=gross)
                    total += gross
                    tax_total += tax
                receipt.subtotal = total - tax_total
                receipt.tax_amount = tax_total
                receipt.total = total
                receipt.paid_at = timezone.now()
                receipt.save(update_fields=["subtotal", "tax_amount", "total", "paid_at"])

        self.stdout.write(f"  POS receipts: {len(receipt_specs)}")
        self.stdout.write("  ✓ Restoran seed završen")
