"""
Seed demo data za Proizvodnju modul.
Usage: python manage.py seed_production <company_uuid>
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Seed demo proizvodnih podataka za firmu"

    def add_arguments(self, parser):
        parser.add_argument("company_id", type=str, help="UUID firme")

    def handle(self, *args, **options):
        from companies.models import Company
        from inventory.models import InventoryItem
        from production.models import (
            BillOfMaterials,
            BOMLine,
            ProductionOrder,
            ProductionStep,
            Workstation,
        )

        company = Company.objects.get(pk=options["company_id"])
        self.stdout.write(f"Seeding production data for: {company.name}")

        # ── Radne stanice ──
        ws1, _ = Workstation.objects.get_or_create(
            company=company,
            code="MIX-01",
            defaults={
                "name": "Miješalica #1",
                "ws_type": "mixing",
                "capacity_per_hour": 100,
                "hourly_cost": Decimal("25.00"),
            },
        )
        ws2, _ = Workstation.objects.get_or_create(
            company=company,
            code="PEC-01",
            defaults={"name": "Peć #1", "ws_type": "oven", "capacity_per_hour": 50, "hourly_cost": Decimal("35.00")},
        )
        ws3, _ = Workstation.objects.get_or_create(
            company=company,
            code="PAK-01",
            defaults={
                "name": "Pakirnica #1",
                "ws_type": "packaging",
                "capacity_per_hour": 200,
                "hourly_cost": Decimal("15.00"),
            },
        )

        # ── Sirovine ──
        def _item(name, sku, price, stock=500):
            obj, _ = InventoryItem.objects.get_or_create(
                company=company,
                sku=sku,
                defaults={"name": name, "unit_price": price, "quantity": stock, "is_active": True},
            )
            return obj

        brasno = _item("Brašno T-550 (kg)", "SIR-001", Decimal("0.80"), 1000)
        kvasac = _item("Kvasac svježi (kg)", "SIR-002", Decimal("4.50"), 50)
        sol = _item("Sol morska (kg)", "SIR-003", Decimal("0.35"), 200)
        voda = _item("Voda (L)", "SIR-004", Decimal("0.01"), 9999)
        secer = _item("Šećer (kg)", "SIR-005", Decimal("1.20"), 300)
        maslac = _item("Maslac (kg)", "SIR-006", Decimal("8.50"), 100)
        jaja = _item("Jaja (kom)", "SIR-007", Decimal("0.25"), 500)
        cokolada = _item("Čokolada couverture (kg)", "SIR-008", Decimal("12.00"), 80)

        # ── Poluproizvod (multi-level BOM) ──
        tijesto_item = _item("Tijesto za kruh (kg)", "POL-001", Decimal("1.50"), 0)
        kruh_item = _item("Kruh bijeli 500g", "GOT-001", Decimal("1.80"), 0)
        pecivo_item = _item("Pecivo maslac 80g", "GOT-002", Decimal("0.60"), 0)
        torta_item = _item("Čokoladna torta", "GOT-003", Decimal("25.00"), 0)

        # ── BOM: Tijesto za kruh (poluproizvod) ──
        bom_tijesto, created = BillOfMaterials.objects.get_or_create(
            company=company,
            code="BOM-TIJ-001",
            defaults={
                "name": "Tijesto za kruh",
                "output_item": tijesto_item,
                "output_quantity": Decimal("10"),
                "output_unit": "kg",
                "status": "active",
                "estimated_duration_minutes": 30,
                "default_workstation": ws1,
                "level": 1,
            },
        )
        if created:
            BOMLine.objects.create(bom=bom_tijesto, item=brasno, quantity=Decimal("6"), unit="kg", waste_percent=2)
            BOMLine.objects.create(bom=bom_tijesto, item=kvasac, quantity=Decimal("0.15"), unit="kg")
            BOMLine.objects.create(bom=bom_tijesto, item=sol, quantity=Decimal("0.12"), unit="kg")
            BOMLine.objects.create(bom=bom_tijesto, item=voda, quantity=Decimal("3.8"), unit="L")

        # ── BOM: Kruh bijeli (multi-level — koristi tijesto) ──
        bom_kruh, created = BillOfMaterials.objects.get_or_create(
            company=company,
            code="BOM-KRH-001",
            defaults={
                "name": "Kruh bijeli 500g",
                "output_item": kruh_item,
                "output_quantity": Decimal("20"),
                "output_unit": "kom",
                "status": "active",
                "estimated_duration_minutes": 90,
                "default_workstation": ws2,
                "parent_bom": None,
                "level": 0,
            },
        )
        if created:
            BOMLine.objects.create(
                bom=bom_kruh, item=tijesto_item, quantity=Decimal("10"), unit="kg", is_subassembly=True, waste_percent=3
            )

        # ── BOM: Pecivo maslac ──
        bom_pecivo, created = BillOfMaterials.objects.get_or_create(
            company=company,
            code="BOM-PEC-001",
            defaults={
                "name": "Pecivo maslac 80g",
                "output_item": pecivo_item,
                "output_quantity": Decimal("50"),
                "output_unit": "kom",
                "status": "active",
                "estimated_duration_minutes": 60,
                "default_workstation": ws2,
            },
        )
        if created:
            BOMLine.objects.create(bom=bom_pecivo, item=brasno, quantity=Decimal("2.5"), unit="kg", waste_percent=1)
            BOMLine.objects.create(bom=bom_pecivo, item=maslac, quantity=Decimal("1.2"), unit="kg")
            BOMLine.objects.create(bom=bom_pecivo, item=jaja, quantity=Decimal("6"), unit="kom")
            BOMLine.objects.create(bom=bom_pecivo, item=secer, quantity=Decimal("0.3"), unit="kg")

        # ── BOM: Čokoladna torta ──
        bom_torta, created = BillOfMaterials.objects.get_or_create(
            company=company,
            code="BOM-TOR-001",
            defaults={
                "name": "Čokoladna torta",
                "output_item": torta_item,
                "output_quantity": Decimal("1"),
                "output_unit": "kom",
                "status": "active",
                "estimated_duration_minutes": 120,
                "default_workstation": ws1,
            },
        )
        if created:
            BOMLine.objects.create(bom=bom_torta, item=brasno, quantity=Decimal("0.4"), unit="kg")
            BOMLine.objects.create(bom=bom_torta, item=cokolada, quantity=Decimal("0.5"), unit="kg")
            BOMLine.objects.create(bom=bom_torta, item=maslac, quantity=Decimal("0.3"), unit="kg")
            BOMLine.objects.create(bom=bom_torta, item=jaja, quantity=Decimal("8"), unit="kom")
            BOMLine.objects.create(bom=bom_torta, item=secer, quantity=Decimal("0.25"), unit="kg")

        # ── Radni nalozi ──
        order1, created = ProductionOrder.objects.get_or_create(
            company=company,
            order_number="RN-202604-001",
            defaults={
                "bom": bom_kruh,
                "planned_quantity": Decimal("100"),
                "status": "confirmed",
                "priority": 3,
                "workstation": ws2,
                "batch_number": "B-20260405-001",
                "planned_start": timezone.now(),
                "planned_end": timezone.now() + timezone.timedelta(hours=8),
            },
        )
        if created:
            ProductionStep.objects.create(
                order=order1, step_number=1, name="Priprema tijesta", workstation=ws1, estimated_minutes=30
            )
            ProductionStep.objects.create(
                order=order1, step_number=2, name="Pečenje", workstation=ws2, estimated_minutes=45
            )
            ProductionStep.objects.create(
                order=order1, step_number=3, name="Hlađenje i pakiranje", workstation=ws3, estimated_minutes=20
            )

        order2, _ = ProductionOrder.objects.get_or_create(
            company=company,
            order_number="RN-202604-002",
            defaults={
                "bom": bom_torta,
                "planned_quantity": Decimal("5"),
                "status": "draft",
                "priority": 2,
                "workstation": ws1,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded: 3 workstations, 4 BOMs (1 multi-level), 8 sirovina, 4 gotova proizvoda, 2 radna naloga"
            )
        )
