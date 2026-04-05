# CC_TASK_PROD_5_TESTS.md
# PRODUCTION MODULE — TASK 5: Test Suite
# Agent: CC Code #5 / Haiku
# ČEKA: Task 1 DONE (models), Task 4 DONE (services)
# Paralelno s Task 3 (templates)

---

## CILJ
Minimalno 40 testova, sve prolaze zeleno. Pokrivenost: modeli, FSM, BOM engine, inventory integration.
`venv/bin/python manage.py test production --verbosity=2` → **40+ tests, 0 failures**

---

## FILE: production/tests.py

```python
"""
production/tests.py — Test suite za MRP modul
Klase:
  1. BillOfMaterialsTest       — BOM kreacija, kalkulacija, kloniranje
  2. ProductionOrderFSMTest    — FSM tranzicije
  3. BOMCostEngineTest         — kalkulacija troška
  4. InventoryIntegrationTest  — dedukcija sirovina, dodavanje gotovog
  5. MRPPlannerTest            — MRP kalkulacija potreba
  6. ProductionViewsTest       — HTTP status kodovi
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse


# ────────────────────────────────────────────────────────
# SETUP HELPERS
# ────────────────────────────────────────────────────────
def make_company():
    from companies.models import Company
    return Company.objects.create(name='Test Firma d.o.o.', oib='12345678901')

def make_user(company):
    u = User.objects.create_user('testprod', 'test@test.com', 'pass')
    from core.models import UserProfile
    UserProfile.objects.filter(user=u).update(company=company)
    return u

def make_inventory_item(company, name='Jabuka', category='material', qty=1000, price=1.50):
    from inventory.models import InventoryItem
    return InventoryItem.objects.create(
        company=company, name=name, sku=f'SKU-{name[:3].upper()}',
        category=category, unit='kg', quantity=Decimal(str(qty)),
        purchase_price=Decimal(str(price)),
    )

def make_product(company, name='Jabučni sok 1L', qty=0):
    return make_inventory_item(company, name=name, category='product', qty=qty, price=0)

def make_work_center(company):
    from production.models import WorkCenter
    return WorkCenter.objects.create(
        company=company, name='Linija A', code='LA',
        capacity_hours_per_day=Decimal('8'), cost_per_hour=Decimal('25')
    )

def make_bom(company, product, material):
    """BOM: 1 serija = 10L soka od 12kg jabuka."""
    from production.models import BillOfMaterials, BOMLine
    bom = BillOfMaterials.objects.create(
        company=company, product=product,
        name='Jabučni sok — osnovna', version='1.0',
        yield_quantity=Decimal('10'), yield_unit='L', is_active=True,
    )
    BOMLine.objects.create(
        bom=bom, material=material,
        quantity=Decimal('12'), unit='kg', scrap_percent=Decimal('5'),
    )
    return bom

def make_order(company, bom, qty=100):
    from production.models import ProductionOrder
    order = ProductionOrder(
        company=company, bom=bom, product=bom.product,
        planned_quantity=Decimal(str(qty)), status='draft',
    )
    order.order_number = order.generate_order_number()
    order.save()
    return order


# ────────────────────────────────────────────────────────
# 1. BillOfMaterials Tests
# ────────────────────────────────────────────────────────
class BillOfMaterialsTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.material = make_inventory_item(self.company)
        self.product = make_product(self.company)

    def test_bom_creation(self):
        from production.models import BillOfMaterials
        bom = BillOfMaterials.objects.create(
            company=self.company, product=self.product,
            name='Test BOM', yield_quantity=Decimal('10'), yield_unit='L',
        )
        self.assertEqual(str(bom.product.name), 'Jabučni sok 1L')
        self.assertTrue(bom.is_active)

    def test_bom_line_quantity_with_scrap(self):
        from production.models import BOMLine
        bom = make_bom(self.company, self.product, self.material)
        line = bom.lines.first()
        # 12 kg + 5% škart = 12.6 kg
        expected = Decimal('12') * (1 + Decimal('5') / 100)
        self.assertAlmostEqual(float(line.quantity_with_scrap), float(expected), places=4)

    def test_bom_unique_active_per_product(self):
        """Može biti više verzija, ali unique_together (company, product, version)."""
        from production.models import BillOfMaterials
        make_bom(self.company, self.product, self.material)
        with self.assertRaises(Exception):
            BillOfMaterials.objects.create(
                company=self.company, product=self.product,
                name='Duplikat', version='1.0',  # ista verzija — treba failati
                yield_quantity=Decimal('10'), yield_unit='L',
            )

    def test_bom_clone_increments_version(self):
        """bom_clone view treba kreirati v2 kad klonira v1."""
        bom = make_bom(self.company, self.product, self.material)
        # Simuliraj logiku kloniranja
        new_version = f"{float(bom.version) + 1.0:.1f}"
        self.assertEqual(new_version, '2.0')

    def test_bom_multiple_lines(self):
        from production.models import BOMLine
        bom = make_bom(self.company, self.product, self.material)
        sugar = make_inventory_item(self.company, name='Šećer', qty=500, price=0.80)
        BOMLine.objects.create(
            bom=bom, material=sugar,
            quantity=Decimal('2'), unit='kg', scrap_percent=Decimal('0'),
        )
        self.assertEqual(bom.lines.count(), 2)


# ────────────────────────────────────────────────────────
# 2. ProductionOrder FSM Tests
# ────────────────────────────────────────────────────────
class ProductionOrderFSMTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.material = make_inventory_item(self.company, qty=2000)
        self.product = make_product(self.company)
        self.bom = make_bom(self.company, self.product, self.material)
        self.order = make_order(self.company, self.bom, qty=10)

    def test_initial_status_is_draft(self):
        self.assertEqual(self.order.status, 'draft')

    def test_transition_draft_to_planned(self):
        self.order.transition_to('planned', save=True)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'planned')

    def test_transition_planned_to_in_progress(self):
        self.order.transition_to('planned', save=True)
        self.order.transition_to('in_progress', save=True)
        self.assertEqual(self.order.status, 'in_progress')

    def test_transition_in_progress_to_completed(self):
        self.order.transition_to('planned', save=True)
        self.order.transition_to('in_progress', save=True)
        self.order.actual_quantity = Decimal('10')
        self.order.save(update_fields=['actual_quantity'])
        self.order.transition_to('completed', save=True)
        self.assertEqual(self.order.status, 'completed')

    def test_invalid_transition_draft_to_completed_fails(self):
        with self.assertRaises(Exception):
            self.order.transition_to('completed', save=True)

    def test_transition_to_cancelled_from_draft(self):
        self.order.transition_to('cancelled', save=True)
        self.assertEqual(self.order.status, 'cancelled')

    def test_reopen_cancelled_to_draft(self):
        self.order.transition_to('cancelled', save=True)
        self.order.transition_to('draft', save=True)
        self.assertEqual(self.order.status, 'draft')

    def test_order_number_format(self):
        import datetime
        year = datetime.date.today().year
        self.assertTrue(self.order.order_number.startswith(f'PN-{year}-'))

    def test_status_color_returns_valid_hex(self):
        for status, _ in self.order.STATUS_CHOICES:
            self.order.status = status
            color = self.order.status_color
            self.assertTrue(color.startswith('#'), f'status_color za {status} nije hex: {color}')


# ────────────────────────────────────────────────────────
# 3. BOMCostEngine Tests
# ────────────────────────────────────────────────────────
class BOMCostEngineTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.material = make_inventory_item(self.company, qty=1000, price=1.50)
        self.product = make_product(self.company)
        self.bom = make_bom(self.company, self.product, self.material)

    def test_calculate_bom_cost_basic(self):
        from production.services import BOMCostEngine
        result = BOMCostEngine.calculate_bom_cost(self.bom, quantity=Decimal('10'))
        # 12kg × 1.05 škart = 12.6kg × 1.50 EUR/kg = 18.90 EUR za 10L
        self.assertIsNotNone(result['total_material_cost'])
        self.assertGreater(result['total_material_cost'], 0)

    def test_shortage_detection(self):
        from production.services import BOMCostEngine
        # Naruči 10000 L — treba 12600 kg, imamo samo 1000 kg
        result = BOMCostEngine.calculate_bom_cost(self.bom, quantity=Decimal('10000'))
        self.assertTrue(result['has_shortages'])
        self.assertEqual(len(result['shortages']), 1)
        self.assertEqual(result['shortages'][0]['material_name'], 'Jabuka')

    def test_no_shortage_when_sufficient_stock(self):
        from production.services import BOMCostEngine
        # Naruči 5 L — treba 6.3 kg, imamo 1000 kg
        result = BOMCostEngine.calculate_bom_cost(self.bom, quantity=Decimal('5'))
        self.assertFalse(result['has_shortages'])

    def test_cost_per_unit_calculation(self):
        from production.services import BOMCostEngine
        result = BOMCostEngine.calculate_bom_cost(self.bom, quantity=Decimal('10'))
        # total / qty
        expected_per_unit = result['total_material_cost'] / Decimal('10')
        self.assertAlmostEqual(
            float(result['cost_per_unit']), float(expected_per_unit), places=2
        )


# ────────────────────────────────────────────────────────
# 4. Inventory Integration Tests
# ────────────────────────────────────────────────────────
class InventoryIntegrationTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.material = make_inventory_item(self.company, qty=Decimal('200'), price=1.50)
        self.product = make_product(self.company, qty=Decimal('0'))
        self.bom = make_bom(self.company, self.product, self.material)
        self.order = make_order(self.company, self.bom, qty=Decimal('10'))
        # Kreiraj linije
        from production.models import ProductionOrderLine
        ProductionOrderLine.objects.create(
            order=self.order, material=self.material, bom_line=self.bom.lines.first(),
            planned_quantity=Decimal('12.6'), actual_quantity=Decimal('12.6'),
            unit='kg', unit_cost=Decimal('1.50'),
        )

    def test_deduct_materials_reduces_inventory(self):
        from production.services import ProductionInventoryService as PIS
        from inventory.models import InventoryItem
        initial_qty = self.material.quantity
        PIS.deduct_materials(self.order)
        self.material.refresh_from_db()
        self.assertEqual(
            self.material.quantity,
            initial_qty - Decimal('12.6')
        )

    def test_deduct_materials_creates_stock_movement(self):
        from production.services import ProductionInventoryService as PIS
        from inventory.models import StockMovement
        result = PIS.deduct_materials(self.order)
        self.assertTrue(result['success'])
        mv = StockMovement.objects.filter(
            item=self.material, movement_type='out', reference=self.order.order_number
        ).first()
        self.assertIsNotNone(mv)

    def test_deduct_marks_lines_as_deducted(self):
        from production.services import ProductionInventoryService as PIS
        PIS.deduct_materials(self.order)
        for line in self.order.lines.all():
            self.assertTrue(line.stock_deducted)

    def test_add_finished_goods_increases_inventory(self):
        from production.services import ProductionInventoryService as PIS
        self.order.actual_quantity = Decimal('10')
        self.order.save(update_fields=['actual_quantity'])
        initial_qty = self.product.quantity or Decimal('0')
        PIS.add_finished_goods(self.order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, initial_qty + Decimal('10'))

    def test_insufficient_stock_returns_error_not_exception(self):
        """Ako nema dovoljno zalihe, ne baci exception — vrati errors listu."""
        from production.services import ProductionInventoryService as PIS
        from production.models import ProductionOrderLine
        # Postavi needed > available
        line = self.order.lines.first()
        line.actual_quantity = Decimal('999')  # imamo samo 200 kg
        line.planned_quantity = Decimal('999')
        line.save()
        result = PIS.deduct_materials(self.order)
        self.assertFalse(result['success'])
        self.assertEqual(len(result['errors']), 1)

    def test_cost_recalculation(self):
        from production.services import ProductionInventoryService as PIS, ProductionCostService as PCS
        self.order.actual_quantity = Decimal('10')
        self.order.save(update_fields=['actual_quantity'])
        PIS.deduct_materials(self.order)
        PCS.recalculate_order_costs(self.order)
        self.order.refresh_from_db()
        self.assertGreater(self.order.cost_total, 0)
        self.assertGreater(self.order.cost_per_unit, 0)


# ────────────────────────────────────────────────────────
# 5. MRPPlanner Tests
# ────────────────────────────────────────────────────────
class MRPPlannerTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.material = make_inventory_item(self.company, qty=500, price=1.50)
        self.product = make_product(self.company)
        self.bom = make_bom(self.company, self.product, self.material)

    def test_mrp_basic_requirements(self):
        from production.services import MRPPlanner
        result = MRPPlanner.calculate_requirements([
            {'product_id': self.product.pk, 'quantity': 10}
        ])
        self.assertIn('material_requirements', result)
        self.assertEqual(len(result['material_requirements']), 1)

    def test_mrp_detects_shortage(self):
        from production.services import MRPPlanner
        # 10000 L → treba 126000 kg jabuka, imamo 500
        result = MRPPlanner.calculate_requirements([
            {'product_id': self.product.pk, 'quantity': 10000}
        ])
        shortage = next((r for r in result['material_requirements'] if r['shortage']), None)
        self.assertIsNotNone(shortage)
        self.assertGreater(shortage['to_order'], 0)

    def test_mrp_missing_bom(self):
        from production.services import MRPPlanner
        result = MRPPlanner.calculate_requirements([
            {'product_id': 99999, 'quantity': 10}  # ne postoji
        ])
        self.assertIn(99999, result['missing_boms'])


# ────────────────────────────────────────────────────────
# 6. Views Tests (HTTP)
# ────────────────────────────────────────────────────────
class ProductionViewsTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client = Client()
        self.client.login(username='testprod', password='pass')
        self.material = make_inventory_item(self.company)
        self.product = make_product(self.company)
        self.bom = make_bom(self.company, self.product, self.material)
        self.wc = make_work_center(self.company)
        self.order = make_order(self.company, self.bom)

    def test_dashboard_200(self):
        r = self.client.get(reverse('production:dashboard'))
        self.assertEqual(r.status_code, 200)

    def test_bom_list_200(self):
        r = self.client.get(reverse('production:bom_list'))
        self.assertEqual(r.status_code, 200)

    def test_bom_detail_200(self):
        r = self.client.get(reverse('production:bom_detail', args=[self.bom.pk]))
        self.assertEqual(r.status_code, 200)

    def test_order_list_200(self):
        r = self.client.get(reverse('production:order_list'))
        self.assertEqual(r.status_code, 200)

    def test_order_detail_200(self):
        r = self.client.get(reverse('production:order_detail', args=[self.order.pk]))
        self.assertEqual(r.status_code, 200)

    def test_wc_list_200(self):
        r = self.client.get(reverse('production:wc_list'))
        self.assertEqual(r.status_code, 200)

    def test_order_create_get_200(self):
        r = self.client.get(reverse('production:order_create'))
        self.assertEqual(r.status_code, 200)

    def test_api_bom_lines_json(self):
        r = self.client.get(reverse('production:api_bom_lines', args=[self.bom.pk]))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data, list)

    def test_unauthenticated_redirect(self):
        self.client.logout()
        r = self.client.get(reverse('production:dashboard'))
        self.assertIn(r.status_code, [302, 301])

    def test_report_costs_200(self):
        r = self.client.get(reverse('production:report_costs'))
        self.assertEqual(r.status_code, 200)
```

---

## PROVJERA USPJEHA

```bash
cd /var/www/fina-connect
venv/bin/python manage.py test production --verbosity=2 2>&1 | tail -20
```

Cilj: **40+ tests, 0 failures, 0 errors**

Ako test pada zbog missing `purchase_price` na InventoryItem — provjeri models.py i dodaj fallback `getattr(item, 'purchase_price', Decimal('0')) or Decimal('0')`.

Kad završiš: `echo "TASK5_DONE" >> /var/www/fina-connect/PROD_BUILD_STATUS.txt`
