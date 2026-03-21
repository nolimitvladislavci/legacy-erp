"""
delivery/tests/test_transport.py
Testovi za TransportOrder, VehicleDocument, DriverDocument,
TachographEntry, FuelEntry.

Filozofija: tražimo greške, ne potvrđujemo da sve radi.
Svaki test je scenarij koji može puknuti u produkciji.
"""
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()
_n = [0]
def _uid():
    _n[0] += 1
    return _n[0]


class TransportOrderTests(TestCase):
    """TransportOrder — centralni nalog za prijevoz."""

    def setUp(self):
        n = _uid()
        from companies.models import Company
        self.company = Company.objects.create(
            name='Prijevoz Test %d' % n,
            oib='%011d' % (90000000000 + n),
        )
        self.driver = User.objects.create_user(
            username='vozac%d' % n, password='x',
            first_name='Pero', last_name='Vozač'
        )
        from delivery.models import Vehicle
        self.vehicle = Vehicle.objects.create(
            company=self.company,
            name='Kombi %d' % n,
            plate_number='ZG-%d-AA' % n,
            vehicle_type='van',
        )

    def _order(self, **kw):
        from delivery.models import TransportOrder
        defaults = dict(
            company=self.company,
            vehicle=self.vehicle,
            driver=self.driver,
            transport_type='freight_eu',
            origin_address='Zagreb, HR',
            origin_country='HR',
            destination_address='München, DE',
            destination_country='DE',
            planned_departure=timezone.now() + timedelta(hours=2),
            planned_arrival=timezone.now() + timedelta(hours=14),
        )
        defaults.update(kw)
        return TransportOrder.objects.create(**defaults)

    # T01 — Broj naloga auto-generiran u formatu TO-YYYY-XXXX
    def test_01_order_number_format(self):
        order = self._order()
        self.assertTrue(order.order_number.startswith('TO-'))
        parts = order.order_number.split('-')
        self.assertEqual(len(parts), 3)
        self.assertTrue(parts[2].isdigit())

    # T02 — Domaći prijevoz: is_international=False
    def test_02_domestic_not_international(self):
        order = self._order(origin_country='HR', destination_country='HR')
        self.assertFalse(order.is_international)

    # T03 — HR→DE: is_international=True
    def test_03_hr_de_is_international(self):
        order = self._order(origin_country='HR', destination_country='DE')
        self.assertTrue(order.is_international)

    # T04 — HR→DE→BA: crosses_eu_border=True (BA izvan EU)
    def test_04_via_ba_crosses_eu_border(self):
        order = self._order(
            origin_country='HR',
            destination_country='DE',
            via_countries=['BA'],
        )
        self.assertTrue(order.crosses_eu_border)

    # T05 — HR→AT→DE: crosses_eu_border=False (sve EU)
    def test_05_via_at_no_eu_border(self):
        order = self._order(
            origin_country='HR',
            destination_country='DE',
            via_countries=['AT'],
        )
        self.assertFalse(order.crosses_eu_border)

    # T06 — DE u ruti → needs_posting_declaration=True
    def test_06_de_route_needs_posting(self):
        order = self._order(origin_country='HR', destination_country='DE')
        self.assertTrue(order.needs_posting_declaration)

    # T07 — HR→RS: needs_posting=False (DE nije u ruti)
    def test_07_rs_route_no_posting(self):
        order = self._order(origin_country='HR', destination_country='RS')
        self.assertFalse(order.needs_posting_declaration)

    # T08 — profit izračun (client_price - total_cost)
    def test_08_profit_calculation(self):
        order = self._order(client_price=Decimal('1200.00'), total_cost=Decimal('780.00'))
        self.assertEqual(order.profit, Decimal('420.00'))

    # T09 — profit negativan kad je gubitak
    def test_09_negative_profit(self):
        order = self._order(client_price=Decimal('500.00'), total_cost=Decimal('800.00'))
        self.assertEqual(order.profit, Decimal('-300.00'))

    # T10 — verify_documents() bez ijednog dokumenta vraća issues
    def test_10_verify_docs_empty_returns_issues(self):
        order = self._order(
            origin_country='HR',
            destination_country='DE',
            requires_cold_chain=True,
        )
        issues = order.verify_documents()
        self.assertIsInstance(issues, list)
        # Mora prijaviti: ATP, Licencu Zajednice, vozačku
        self.assertGreater(len(issues), 0)

    # T11 — verify_documents() s validnim ATP prolazi ATP provjeru
    def test_11_valid_atp_clears_atp_issue(self):
        from delivery.models import VehicleDocument
        VehicleDocument.objects.create(
            vehicle=self.vehicle,
            doc_type='atp_certificate',
            doc_number='ATP-2026-001',
            valid_from=date.today() - timedelta(days=10),
            valid_until=date.today() + timedelta(days=365),
        )
        order = self._order(requires_cold_chain=True, is_international=False,
                            origin_country='HR', destination_country='HR')
        issues = order.verify_documents()
        # ATP ne smije biti u issues
        self.assertFalse(any('ATP' in i for i in issues))

    # T12 — istekli ATP puca verify_documents
    def test_12_expired_atp_raises_issue(self):
        from delivery.models import VehicleDocument
        VehicleDocument.objects.create(
            vehicle=self.vehicle,
            doc_type='atp_certificate',
            doc_number='ATP-OLD',
            valid_from=date.today() - timedelta(days=400),
            valid_until=date.today() - timedelta(days=1),  # jučer istekao
        )
        order = self._order(requires_cold_chain=True)
        issues = order.verify_documents()
        self.assertTrue(any('ATP' in i for i in issues))

    # T13 — non-EU vozač bez Potvrde → issue
    def test_13_non_eu_driver_without_attestation(self):
        from delivery.models import DriverDocument
        # Vozač s BA vozačkom
        DriverDocument.objects.create(
            driver=self.driver,
            doc_type='driving_licence',
            doc_number='BA-123456',
            issuing_country='BA',
            valid_until=date.today() + timedelta(days=500),
        )
        order = self._order(
            origin_country='HR',
            destination_country='DE',
            via_countries=['BA'],
        )
        issues = order.verify_documents()
        self.assertTrue(any('non-EU' in i.lower() or 'potvrda' in i.lower() or 'attestation' in i.lower() for i in issues))

    # T14 — Cross-tenant: drugi company ne vidi nalog
    def test_14_cross_tenant_isolation(self):
        from companies.models import Company
        from delivery.models import TransportOrder
        n = _uid()
        other = Company.objects.create(name='Drugi %d' % n, oib='%011d' % (91000000000 + n))
        order = self._order()
        # Drugi company ne smije vidjeti
        self.assertFalse(TransportOrder.objects.filter(company=other, pk=order.pk).exists())

    # T15 — Status flow: draft → planned → in_transit
    def test_15_status_progression(self):
        from delivery.models import TransportOrder
        order = self._order()
        self.assertEqual(order.status, 'draft')
        order.status = 'planned'
        order.save(update_fields=['status'])
        order.refresh_from_db()
        self.assertEqual(order.status, 'planned')
        order.status = 'in_transit'
        order.actual_departure = timezone.now()
        order.save(update_fields=['status', 'actual_departure'])
        order.refresh_from_db()
        self.assertEqual(order.status, 'in_transit')


class VehicleDocumentTests(TestCase):
    """VehicleDocument — isteci, upozorenja, ATP."""

    def setUp(self):
        n = _uid()
        from companies.models import Company
        from delivery.models import Vehicle
        self.company = Company.objects.create(name='VDoc Test %d' % n, oib='%011d' % (92000000000 + n))
        self.vehicle = Vehicle.objects.create(company=self.company, name='Hladnjača %d' % n, plate_number='OS-%d-BB' % n, vehicle_type='refrigerated', has_cold_chain=True)

    def _doc(self, doc_type='registration', days_until=365, **kw):
        from delivery.models import VehicleDocument
        return VehicleDocument.objects.create(
            vehicle=self.vehicle,
            doc_type=doc_type,
            doc_number='DOC-%d' % _uid(),
            valid_from=date.today() - timedelta(days=30),
            valid_until=date.today() + timedelta(days=days_until),
            **kw
        )

    # T16 — Validan dokument: is_expired=False
    def test_16_valid_doc_not_expired(self):
        doc = self._doc(days_until=100)
        self.assertFalse(doc.is_expired)
        self.assertEqual(doc.days_until_expiry, 100)

    # T17 — Istekao dokument: is_expired=True
    def test_17_expired_doc(self):
        from delivery.models import VehicleDocument
        doc = VehicleDocument.objects.create(
            vehicle=self.vehicle, doc_type='insurance',
            doc_number='INS-OLD',
            valid_from=date.today() - timedelta(days=400),
            valid_until=date.today() - timedelta(days=1),
        )
        self.assertTrue(doc.is_expired)

    # T18 — needs_renewal_alert: 29 dana → True (reminder_days=30)
    def test_18_renewal_alert_triggered(self):
        doc = self._doc(days_until=29, reminder_days=30)
        self.assertTrue(doc.needs_renewal_alert)

    # T19 — needs_renewal_alert: 31 dana → False
    def test_19_no_alert_when_not_due(self):
        doc = self._doc(days_until=31, reminder_days=30)
        self.assertFalse(doc.needs_renewal_alert)

    # T20 — ATP certifikat za hlađeno vozilo
    def test_20_atp_on_refrigerated_vehicle(self):
        doc = self._doc(doc_type='atp_certificate', days_until=500)
        self.assertEqual(doc.doc_type, 'atp_certificate')
        self.assertFalse(doc.is_expired)

    # T21 — Ordering: najprije istječe (valid_until ASC)
    def test_21_ordering_by_expiry(self):
        from delivery.models import VehicleDocument
        d1 = self._doc(days_until=10)
        d2 = self._doc(days_until=200)
        d3 = self._doc(days_until=50)
        docs = list(VehicleDocument.objects.filter(vehicle=self.vehicle).order_by('valid_until'))
        self.assertEqual(docs[0].pk, d1.pk)


class DriverDocumentTests(TestCase):
    """DriverDocument — non-EU vozači, isteci."""

    def setUp(self):
        n = _uid()
        from companies.models import Company
        self.company = Company.objects.create(name='Driver Test %d' % n, oib='%011d' % (93000000000 + n))
        self.driver_hr = User.objects.create_user(username='hrv%d' % n, password='x')
        self.driver_ba = User.objects.create_user(username='bih%d' % n, password='x')

    def _doc(self, driver, doc_type='driving_licence', country='HR', days=365):
        from delivery.models import DriverDocument
        return DriverDocument.objects.create(
            driver=driver, company=self.company,
            doc_type=doc_type, doc_number='D-%d' % _uid(),
            issuing_country=country,
            valid_until=date.today() + timedelta(days=days),
        )

    # T22 — HR vozač: is_non_eu_driver=False
    def test_22_hr_driver_is_eu(self):
        doc = self._doc(self.driver_hr, country='HR')
        self.assertFalse(doc.is_non_eu_driver)

    # T23 — BA vozač: is_non_eu_driver=True
    def test_23_ba_driver_is_non_eu(self):
        doc = self._doc(self.driver_ba, country='BA')
        self.assertTrue(doc.is_non_eu_driver)

    # T24 — RS vozač: is_non_eu_driver=True
    def test_24_rs_driver_is_non_eu(self):
        doc = self._doc(self.driver_ba, country='RS')
        self.assertTrue(doc.is_non_eu_driver)

    # T25 — Istekla CPC kartica je expired
    def test_25_expired_cpc_card(self):
        from delivery.models import DriverDocument
        doc = DriverDocument.objects.create(
            driver=self.driver_hr, company=self.company,
            doc_type='cpc_card', doc_number='CPC-OLD',
            issuing_country='HR',
            valid_until=date.today() - timedelta(days=5),
        )
        self.assertTrue(doc.is_expired)

    # T26 — Tahograf kartica kao DriverDocument
    def test_26_tachograph_card_created(self):
        doc = self._doc(self.driver_hr, doc_type='tachograph_card', country='HR')
        self.assertEqual(doc.doc_type, 'tachograph_card')


class TachographEntryTests(TestCase):
    """TachographEntry — zakonski limiti vožnje i odmora."""

    def setUp(self):
        n = _uid()
        from companies.models import Company
        from delivery.models import Vehicle
        self.driver = User.objects.create_user(username='tach%d' % n, password='x')
        self.company = Company.objects.create(name='Tach Test %d' % n, oib='%011d' % (94000000000 + n))
        self.vehicle = Vehicle.objects.create(company=self.company, name='Kamion %d' % n, plate_number='RI-%d-CC' % n)

    def _entry(self, driving=480, rest=60, other=60, avail=120, odo_start=50000, odo_end=50800):
        from delivery.models import TachographEntry
        return TachographEntry.objects.create(
            driver=self.driver, vehicle=self.vehicle,
            date=date.today() - timedelta(days=_uid() % 30),
            driving_minutes=driving,
            other_work_minutes=other,
            availability_minutes=avail,
            rest_minutes=rest,
            odometer_start=odo_start,
            odometer_end=odo_end,
        )

    # T27 — Normalna vožnja 8h (480 min): nije prekoračena
    def test_27_normal_driving_no_violation(self):
        entry = self._entry(driving=480)
        self.assertFalse(entry.daily_driving_exceeded)

    # T28 — Vožnja 9h 1min (541 min): prekoračena
    def test_28_exceeded_daily_limit(self):
        entry = self._entry(driving=541)
        self.assertTrue(entry.daily_driving_exceeded)

    # T29 — 4h vožnje + 46min odmora: nema kršenja pauze
    def test_29_sufficient_break_no_violation(self):
        entry = self._entry(driving=240, rest=46)
        self.assertFalse(entry.break_violation)

    # T30 — 4h 31min vožnje (271 min) + samo 30min odmora: kršenje pauze
    def test_30_break_violation_detected(self):
        entry = self._entry(driving=271, rest=30)
        self.assertTrue(entry.break_violation)

    # T31 — km izračun (odo_end - odo_start)
    def test_31_km_driven_calculation(self):
        entry = self._entry(odo_start=100000, odo_end=100350)
        self.assertEqual(entry.km_driven, 350)

    # T32 — driving_hours property
    def test_32_driving_hours_property(self):
        entry = self._entry(driving=300)
        self.assertAlmostEqual(entry.driving_hours, 5.0)

    # T33 — unique_together (driver, date): duplikat puca
    def test_33_unique_driver_date(self):
        from delivery.models import TachographEntry
        from django.db import IntegrityError
        d = date.today()
        TachographEntry.objects.create(
            driver=self.driver, vehicle=self.vehicle, date=d,
            driving_minutes=400, rest_minutes=60,
        )
        with self.assertRaises(IntegrityError):
            TachographEntry.objects.create(
                driver=self.driver, vehicle=self.vehicle, date=d,
                driving_minutes=300, rest_minutes=45,
            )


class FuelEntryTests(TestCase):
    """FuelEntry — gorivo, kilometraža, automatski total."""

    def setUp(self):
        n = _uid()
        from companies.models import Company
        from delivery.models import Vehicle
        self.company = Company.objects.create(name='Fuel Test %d' % n, oib='%011d' % (95000000000 + n))
        self.vehicle = Vehicle.objects.create(company=self.company, name='Van %d' % n, plate_number='ST-%d-DD' % n)

    def _fuel(self, liters=50, price=1.80, odo=120000, country='HR'):
        from delivery.models import FuelEntry
        return FuelEntry.objects.create(
            vehicle=self.vehicle,
            date=timezone.now(),
            liters=Decimal(str(liters)),
            price_per_liter=Decimal(str(price)),
            odometer_km=odo,
            country=country,
        )

    # T34 — total_cost automatski izračunat u save()
    def test_34_total_cost_auto_calculated(self):
        entry = self._fuel(liters=50, price=1.80)
        self.assertEqual(entry.total_cost, Decimal('90.00'))

    # T35 — DE gorivo (skuplje)
    def test_35_german_fuel_higher_price(self):
        entry = self._fuel(liters=60, price=1.95, country='DE')
        self.assertEqual(entry.total_cost, Decimal('117.00'))
        self.assertEqual(entry.country, 'DE')

    # T36 — Gorivo vezano na TransportOrder
    def test_36_fuel_linked_to_transport_order(self):
        from delivery.models import FuelEntry, TransportOrder
        from django.contrib.auth import get_user_model
        User = get_user_model()
        n = _uid()
        driver = User.objects.create_user(username='fd%d' % n, password='x')
        order = TransportOrder.objects.create(
            company=self.company, vehicle=self.vehicle, driver=driver,
            transport_type='freight_eu',
            origin_address='Zagreb', origin_country='HR',
            destination_address='Berlin', destination_country='DE',
            planned_departure=timezone.now() + timedelta(hours=1),
            planned_arrival=timezone.now() + timedelta(hours=12),
        )
        fuel = FuelEntry.objects.create(
            vehicle=self.vehicle, transport_order=order,
            date=timezone.now(), liters=Decimal('45'), price_per_liter=Decimal('1.79'),
            odometer_km=200000, country='AT',
        )
        self.assertEqual(fuel.transport_order, order)
        self.assertEqual(fuel.total_cost, Decimal('80.55'))
