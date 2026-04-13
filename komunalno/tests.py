"""
Testovi za komunalno modul — Reciklažno dvorište / Zeleni otok.
15 testova: kvote, process_delivery, scale integrity, e-ONTO batch.
"""
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from companies.models import Company
from partners.models import Partner
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    WasteStation, WasteCategory, CitizenCard, AnnualQuota,
    WasteDelivery, ScaleReading, OntoExportBatch, WasteQuickButton,
)


class WasteTestBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Općina Zeleni Otok', oib='12345678901')
        self.user = User.objects.create_user(username='operater', password='test1234')
        self.partner = Partner.objects.create(company=self.company, name='Ivan Horvat', oib='98765432101')
        self.station = WasteStation.objects.create(
            company=self.company, name='RD Zeleni Otok',
            station_type='recycling_yard', address='Ulica recikliranja 1',
        )
        self.cat_paper = WasteCategory.objects.create(
            key_number='20 01 01', name='Papir i karton',
            category_group='Komunalni otpad', default_annual_quota=Decimal('0'), unit='kg',
        )
        self.cat_construction = WasteCategory.objects.create(
            key_number='17 01 07', name='Mješavine betona, opeke, crijepa',
            category_group='Građevinski otpad', default_annual_quota=Decimal('200'),
            price_per_unit_over_quota=Decimal('0.50'), unit='kg',
        )
        self.cat_hazardous = WasteCategory.objects.create(
            key_number='20 01 21', name='Fluorescentne cijevi',
            category_group='Opasni otpad', is_hazardous=True,
            default_annual_quota=Decimal('50'), price_per_unit_over_quota=Decimal('2.00'), unit='kg',
        )
        self.card = CitizenCard.objects.create(
            company=self.company, partner=self.partner,
            card_number='ZO-0001', address='Zelena 5, 10000 Zagreb', household_members=3,
        )


class QuotaTests(WasteTestBase):
    def test_unlimited_category_returns_none(self):
        self.assertIsNone(self.card.get_remaining_quota(self.cat_paper))

    def test_initial_quota_is_full(self):
        self.assertEqual(self.card.get_remaining_quota(self.cat_construction), Decimal('200'))

    def test_quota_decreases_with_delivery(self):
        WasteDelivery.objects.create(
            company=self.company, station=self.station,
            citizen=self.card, category=self.cat_construction,
            quantity=Decimal('80'), status='confirmed',
        )
        self.assertEqual(self.card.get_remaining_quota(self.cat_construction), Decimal('120'))

    def test_quota_override_per_municipality(self):
        AnnualQuota.objects.create(
            company=self.company, category=self.cat_construction,
            year=timezone.localdate().year, quota=Decimal('500'),
        )
        self.assertEqual(self.card.get_remaining_quota(self.cat_construction), Decimal('500'))

    def test_quota_zero_after_full_usage(self):
        WasteDelivery.objects.create(
            company=self.company, station=self.station,
            citizen=self.card, category=self.cat_construction,
            quantity=Decimal('200'), status='confirmed',
        )
        self.assertEqual(self.card.get_remaining_quota(self.cat_construction), Decimal('0'))

    def test_pending_deliveries_not_counted(self):
        WasteDelivery.objects.create(
            company=self.company, station=self.station,
            citizen=self.card, category=self.cat_construction,
            quantity=Decimal('150'), status='pending',
        )
        self.assertEqual(self.card.get_remaining_quota(self.cat_construction), Decimal('200'))


class DeliveryProcessTests(WasteTestBase):
    def test_within_quota_no_charge(self):
        d = WasteDelivery(company=self.company, station=self.station,
                          citizen=self.card, category=self.cat_construction, quantity=Decimal('150'))
        d.save()
        d.process_delivery()
        self.assertEqual(d.status, 'confirmed')
        self.assertEqual(d.over_quota, Decimal('0'))
        self.assertEqual(d.charge_amount, Decimal('0'))

    def test_over_quota_charges(self):
        d = WasteDelivery(company=self.company, station=self.station,
                          citizen=self.card, category=self.cat_construction, quantity=Decimal('250'))
        d.save()
        d.process_delivery()
        self.assertEqual(d.over_quota, Decimal('50'))
        self.assertEqual(d.charge_amount, Decimal('25.00'))

    def test_partial_quota_remaining(self):
        WasteDelivery.objects.create(
            company=self.company, station=self.station,
            citizen=self.card, category=self.cat_construction,
            quantity=Decimal('180'), status='confirmed',
        )
        d = WasteDelivery(company=self.company, station=self.station,
                          citizen=self.card, category=self.cat_construction, quantity=Decimal('50'))
        d.save()
        d.process_delivery()
        self.assertEqual(d.over_quota, Decimal('30'))
        self.assertEqual(d.charge_amount, Decimal('15.00'))

    def test_unlimited_no_charge(self):
        d = WasteDelivery(company=self.company, station=self.station,
                          citizen=self.card, category=self.cat_paper, quantity=Decimal('5000'))
        d.save()
        d.process_delivery()
        self.assertEqual(d.charge_amount, Decimal('0'))

    def test_hazardous_higher_rate(self):
        d = WasteDelivery(company=self.company, station=self.station,
                          citizen=self.card, category=self.cat_hazardous, quantity=Decimal('60'))
        d.save()
        d.process_delivery()
        self.assertEqual(d.over_quota, Decimal('10'))
        self.assertEqual(d.charge_amount, Decimal('20.00'))


class ScaleIntegrityTests(WasteTestBase):
    def test_hash_verification(self):
        now = timezone.now()
        raw = 'ST,GS,   152.50 kg'
        h = ScaleReading.compute_hash(raw, now, self.station.pk)
        r = ScaleReading.objects.create(
            company=self.company, station=self.station,
            raw_data=raw, weight_kg=Decimal('152.50'), integrity_hash=h, read_at=now,
        )
        self.assertTrue(r.verify_integrity())

    def test_tampered_fails(self):
        now = timezone.now()
        h = ScaleReading.compute_hash('ST,GS,   152.50 kg', now, self.station.pk)
        r = ScaleReading.objects.create(
            company=self.company, station=self.station,
            raw_data='ST,GS,   50.00 kg', weight_kg=Decimal('50.00'),
            integrity_hash=h, read_at=now,
        )
        self.assertFalse(r.verify_integrity())


class OntoExportTests(WasteTestBase):
    def test_xml_generation(self):
        today = timezone.localdate()
        batch = OntoExportBatch.objects.create(
            company=self.company, station=self.station, date_from=today, date_to=today,
        )
        for _ in range(3):
            WasteDelivery.objects.create(
                company=self.company, station=self.station,
                citizen=self.card, category=self.cat_paper,
                quantity=Decimal('10'), status='confirmed', onto_batch=batch,
            )
        xml = batch.generate_xml()
        self.assertIn('<eONTO', xml)
        self.assertIn('<BrojZapisa>3</BrojZapisa>', xml)
        self.assertEqual(batch.delivery_count, 3)

    def test_retry_logic(self):
        batch = OntoExportBatch.objects.create(
            company=self.company, station=self.station,
            date_from=timezone.localdate(), date_to=timezone.localdate(),
            status='error', retry_count=2, max_retries=3,
        )
        self.assertTrue(batch.can_retry())
        batch.retry_count = 3
        self.assertFalse(batch.can_retry())
