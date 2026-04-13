"""
Compliance Tests — LOT Karenca, BOM Normativi, Storno+Konačni Račun
═══════════════════════════════════════════════════════════════════════
Testira 3 kritična compliance flow-a koji štite od:
1. Prodaje proizvoda pod karencom (Zakon o higijeni hrane)
2. Netočnog skidanja zaliha (inspekcija Carine)
3. Dvostrukog oporezivanja depozita (čl.79 ZPDV)
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone


class SplitAllocationTest(TestCase):
    """Dron #1: SplitAllocation generira StockMovement(internal_use)."""

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name='Test OPG', oib='12345678901')
        self.user = User.objects.create_user('testuser', password='test')
        from inventory.models import InventoryItem
        self.item = InventoryItem.objects.create(
            company=self.company, name='Domaća jaja', sku='JAJA-001',
            unit='kom', quantity=Decimal('100'), min_quantity=10,
            unit_price=Decimal('0.50'),
        )

    def test_allocate_to_inhouse_creates_movement(self):
        from inventory.services.split_allocation import allocate_to_inhouse
        movement = allocate_to_inhouse(self.item, qty=Decimal('20'), reason='Za doručak', user=self.user)
        self.assertEqual(movement.movement_type, 'internal_use')
        self.assertEqual(movement.quantity, Decimal('20'))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal('80'))
        self.assertEqual(self.item.reserved_inhouse, Decimal('20'))

    def test_allocate_insufficient_raises(self):
        from inventory.services.split_allocation import allocate_to_inhouse
        with self.assertRaises(ValueError):
            allocate_to_inhouse(self.item, qty=Decimal('200'))

    def test_release_from_inhouse(self):
        from inventory.services.split_allocation import allocate_to_inhouse, release_from_inhouse
        allocate_to_inhouse(self.item, qty=Decimal('30'))
        self.item.refresh_from_db()
        release_from_inhouse(self.item, qty=Decimal('10'))
        self.item.refresh_from_db()
        self.assertEqual(self.item.reserved_inhouse, Decimal('20'))
        self.assertEqual(self.item.quantity, Decimal('80'))  # 100-30+10=80


class KarencaEnforcementTest(TestCase):
    """Dron #2: Karenca blokira prodaju na razini LOT/StockBatch."""

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name='Test OPG', oib='12345678902')
        from udruge.models import Flock, FlockHealthRecord
        self.flock = Flock.objects.create(
            company=self.company, naziv='Jato A', vrsta='kokos',
            broj_komada=50, datum_nabave=timezone.now().date(),
        )
        # Daj antibiotik s karencom 14 dana
        self.health = FlockHealthRecord.objects.create(
            flock=self.flock, vrsta_tretmana='antibiotik',
            datum=timezone.now().date(), lijek='Amoksicilin',
            karenca_dana=14,
        )

    def test_flock_has_active_karenca(self):
        self.assertTrue(self.flock.has_active_karenca)

    def test_karenca_end_date(self):
        expected = timezone.now().date() + timedelta(days=14)
        self.assertEqual(self.flock.karenca_end_date, expected)

    def test_expired_karenca_not_active(self):
        # Postavi datum 20 dana u prošlost
        self.health.datum = timezone.now().date() - timedelta(days=20)
        self.health.save()
        self.assertFalse(self.flock.has_active_karenca)

    def test_stock_batch_source_flock(self):
        from inventory.models import InventoryItem, StockBatch
        item = InventoryItem.objects.create(
            company=self.company, name='Jaja Jato A', sku='JAJA-A',
            unit='kom', quantity=50, source_flock=self.flock,
        )
        batch = StockBatch.objects.create(
            company=self.company, item=item,
            batch_number='FLOCK-1-260328', source_flock=self.flock,
            quantity=30,
        )
        self.assertEqual(batch.source_flock, self.flock)
        self.assertTrue(batch.source_flock.has_active_karenca)


class BOMNormativTest(TestCase):
    """Dron #3: ExperienceInclusion BOM — točna količina po osobi."""

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name='Test OPG', oib='12345678903')
        from experiences.models import Experience, ExperienceInclusion
        from inventory.models import InventoryItem
        self.item_sir = InventoryItem.objects.create(
            company=self.company, name='Sir Paški', sku='SIR-001',
            unit='kg', quantity=Decimal('5.000'), unit_price=Decimal('25'),
        )
        self.item_vino = InventoryItem.objects.create(
            company=self.company, name='Malvazija', sku='VINO-001',
            unit='L', quantity=Decimal('10.000'), unit_price=Decimal('8'),
        )
        self.exp = Experience.objects.create(
            company=self.company, name='Degustacija', slug='test-deg',
            experience_type='degustacija', duration_minutes=60,
            capacity=20, price_per_person=Decimal('35'), deposit_pct=30,
        )
        self.bom_sir = ExperienceInclusion.objects.create(
            experience=self.exp, inventory_item=self.item_sir,
            description='Sir Paški 50g', quantity_per_person=Decimal('0.0500'),
            unit='kg',
        )
        self.bom_vino = ExperienceInclusion.objects.create(
            experience=self.exp, inventory_item=self.item_vino,
            description='Malvazija 0.2L', quantity_per_person=Decimal('0.2000'),
            unit='L',
        )

    def test_total_for_pax(self):
        self.assertEqual(self.bom_sir.total_for_pax(10), Decimal('0.5000'))
        self.assertEqual(self.bom_vino.total_for_pax(10), Decimal('2.0000'))

    def test_stock_sufficient(self):
        self.assertTrue(self.bom_sir.stock_sufficient(10))   # 0.5 < 5.0
        self.assertTrue(self.bom_vino.stock_sufficient(10))  # 2.0 < 10.0

    def test_stock_insufficient(self):
        self.assertFalse(self.bom_sir.stock_sufficient(200))  # 10.0 > 5.0

    def test_stock_deficit(self):
        deficit = self.bom_sir.stock_deficit(200)
        self.assertLess(deficit, 0)  # Negativan = manjak


class NoShowStornoTest(TestCase):
    """Dron #4: No-show generira storno predujma + konačni račun."""

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name='Test OPG', oib='12345678904')
        self.user = User.objects.create_user('testuser2', password='test')
        from experiences.models import Experience, ExperienceBooking, ExperienceSchedule
        self.exp = Experience.objects.create(
            company=self.company, name='Tura', slug='test-tura',
            experience_type='tura', duration_minutes=120,
            capacity=10, price_per_person=Decimal('50'), deposit_pct=30,
        )
        self.sched = ExperienceSchedule.objects.create(
            experience=self.exp, date=timezone.now().date(),
            time_from=__import__('datetime').time(10, 0), time_to=__import__('datetime').time(12, 0), max_pax=10,
        )
        self.booking = ExperienceBooking.objects.create(
            schedule=self.sched, guest_name='Ivan Test',
            guest_email='ivan@test.com', pax_count=2,
        )

    def test_booking_auto_calculates_deposit(self):
        # 2 adults × 50€ = 100€, deposit 30% = 30€
        self.assertEqual(self.booking.price_total, Decimal('100'))
        self.assertEqual(self.booking.deposit_amount, Decimal('30'))

    def test_confirm_deposit_sets_status(self):
        """confirm_deposit postavlja status=confirmed i deposit_paid=True."""
        from unittest.mock import patch
        with patch.object(self.booking, '_generate_deposit_invoice'):
            self.booking.confirm_deposit(method='card')
        self.assertTrue(self.booking.deposit_paid)
        self.assertEqual(self.booking.status, 'confirmed')

    def test_no_show_sets_forfeited(self):
        """mark_no_show postavlja deposit_forfeited=True, refund=0."""
        from unittest.mock import patch
        with patch.object(self.booking, '_generate_deposit_invoice'):
            self.booking.confirm_deposit(method='card')
        with patch.object(self.booking, '_storno_and_final_invoice'):
            self.booking.mark_no_show()
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'no_show')
        self.assertTrue(self.booking.deposit_forfeited)
        self.assertEqual(self.booking.refund_amount, Decimal('0'))

    def test_cancel_free_within_deadline(self):
        """Otkazivanje 2 dana prije → puni povrat depozita."""
        from unittest.mock import patch
        with patch.object(self.booking, '_generate_deposit_invoice'):
            self.booking.confirm_deposit(method='card')
        # Force can_cancel_free: schedule 2 dana u budućnosti
        self.booking.schedule.date = (timezone.now() + timedelta(days=2)).date()
        self.booking.schedule.save()
        self.booking.cancel()
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'cancelled')
        self.assertFalse(self.booking.deposit_forfeited)
        self.assertEqual(self.booking.refund_amount, self.booking.deposit_amount)
