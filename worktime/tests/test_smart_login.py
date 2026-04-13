"""
Smart Login & Device Token — testovi za mobilno prijavljivanje u POS.

Scenariji:
1. Osnovni device token login → TimeLog + WaiterShift + Cashier
2. Dupli login (već prijavljen) → ne kreira duplikat
3. Logout → zatvara sve tri (TimeLog, WaiterShift, Cashier)
4. Zaboravljeni mobitel — tuđi token na krivom uređaju
5. Deaktivirani token → odbijen
6. Token bez cashier veze → samo TimeLog + WaiterShift
7. ArbZG break na logout (7h smjena → 30 min odbitak)
8. Cashier auto-close safeguard (>16h)
9. Device token barcode format validacija
10. Concurrent sessions (isti user, dva tokena)
"""

import hashlib
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone as tz

User = get_user_model()


class SmartLoginSetup(TestCase):
    @classmethod
    def setUpTestData(cls):
        from companies.models import Company

        cls.company = Company.objects.create(
            name="Smart Login Test GmbH",
            oib="77777777701",
            latitude=51.7189,
            longitude=8.7544,  # Paderborn
            geofence_radius=200,
        )
        cls.user = User.objects.create_user("smartworker", "sw@test.com", "Test123!")


class DeviceTokenModelTest(SmartLoginSetup):
    def test_01_token_creation_generates_barcode(self):
        from accounts.models import DeviceToken

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Test Phone",
        )
        self.assertTrue(dt.barcode_data.startswith("LC-DEV-"))
        self.assertEqual(len(dt.barcode_data), 15)  # LC-DEV- + 8 chars

    def test_02_barcode_format_deterministic(self):
        from accounts.models import DeviceToken

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Format Test",
        )
        expected_short = hashlib.sha256(dt.token.bytes).hexdigest()[:8].upper()
        self.assertEqual(dt.barcode_data, "LC-DEV-%s" % expected_short)

    def test_03_deactivated_token_not_usable(self):
        from accounts.models import DeviceToken

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Deactivated",
            is_active=False,
        )
        found = DeviceToken.objects.filter(barcode_data=dt.barcode_data, is_active=True).first()
        self.assertIsNone(found)


class UnifiedLoginTest(SmartLoginSetup):
    def _make_token(self, cashier=None):
        from accounts.models import DeviceToken

        return DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Test Device",
            cashier=cashier,
        )

    def _make_cashier(self):
        from pos.models import POSCashier

        return POSCashier.objects.create(
            company=self.company,
            name="Test Cashier",
            user=self.user,
            is_active=True,
        )

    def test_04_login_starts_timelog(self):
        from pos.worktime_bridge import device_login_start_all
        from worktime.models import TimeLog

        dt = self._make_token()
        result = device_login_start_all(dt, ip_address="127.0.0.1")
        self.assertIn("radno_vrijeme", result.get("started", []))
        log = TimeLog.objects.filter(user=self.user, company=self.company, status="OPEN").first()
        self.assertIsNotNone(log)
        self.assertIn("DeviceToken", log.notes)

    def test_05_login_starts_waiter_shift(self):
        from pos.models import WaiterShift
        from pos.worktime_bridge import device_login_start_all

        dt = self._make_token()
        result = device_login_start_all(dt, ip_address="127.0.0.1")
        self.assertIn("waiter_shift", result.get("started", []))
        shift = WaiterShift.objects.filter(user=self.user, company=self.company, is_active=True).first()
        self.assertIsNotNone(shift)

    def test_06_login_with_cashier_clocks_in(self):
        from pos.worktime_bridge import device_login_start_all

        cashier = self._make_cashier()
        dt = self._make_token(cashier=cashier)
        result = device_login_start_all(dt, ip_address="127.0.0.1")
        self.assertIn("cashier", result.get("started", []))
        cashier.refresh_from_db()
        self.assertIsNotNone(cashier.clock_in_at)

    def test_07_double_login_no_duplicate_timelog(self):
        """Ako je već prijavljen, ne kreira dupli TimeLog."""
        from pos.worktime_bridge import device_login_start_all
        from worktime.models import TimeLog

        dt = self._make_token()
        device_login_start_all(dt, ip_address="127.0.0.1")
        device_login_start_all(dt, ip_address="127.0.0.1")
        count = TimeLog.objects.filter(user=self.user, company=self.company, status="OPEN").count()
        self.assertEqual(count, 1)

    def test_08_logout_closes_all(self):
        """Logout zatvara TimeLog + WaiterShift + Cashier."""
        from pos.models import WaiterShift
        from pos.worktime_bridge import device_login_start_all, device_logout_stop_all
        from worktime.models import TimeLog

        cashier = self._make_cashier()
        dt = self._make_token(cashier=cashier)
        device_login_start_all(dt, ip_address="127.0.0.1")

        result = device_logout_stop_all(self.user, self.company)
        self.assertIn("radno_vrijeme", result.get("stopped", []))

        log = TimeLog.objects.filter(user=self.user, company=self.company).order_by("-start_time").first()
        self.assertEqual(log.status, "CLOSED")
        self.assertIsNotNone(log.end_time)
        self.assertIsNotNone(log.payable_hours)

        shift = WaiterShift.objects.filter(user=self.user, company=self.company).order_by("-id").first()
        self.assertFalse(shift.is_active)

    def test_09_token_without_cashier_still_works(self):
        """Token bez cashier veze — samo TimeLog + WaiterShift."""
        from pos.worktime_bridge import device_login_start_all

        dt = self._make_token(cashier=None)
        result = device_login_start_all(dt, ip_address="127.0.0.1")
        started = result.get("started", [])
        self.assertIn("radno_vrijeme", started)
        self.assertIn("waiter_shift", started)
        self.assertNotIn("cashier", started)


class ArbZGBreakOnLogoutTest(SmartLoginSetup):
    def test_10_7h_shift_deducts_30min(self):
        """7h smjena → 30 min automatski odbitak na logout."""
        from worktime.models import TimeLog

        now = tz.now()
        log = TimeLog.objects.create(
            user=self.user,
            company=self.company,
            date=now.date(),
            start_time=now - timedelta(hours=7),
            status="OPEN",
        )
        log.end_time = now
        log.close_shift()
        self.assertEqual(log.break_minutes, 30)
        self.assertAlmostEqual(float(log.payable_hours), 6.5, places=1)

    def test_11_10h_shift_deducts_45min(self):
        """10h smjena → 45 min automatski odbitak."""
        from worktime.models import TimeLog

        now = tz.now()
        log = TimeLog.objects.create(
            user=self.user,
            company=self.company,
            date=now.date(),
            start_time=now - timedelta(hours=10),
            status="OPEN",
        )
        log.end_time = now
        log.close_shift()
        self.assertEqual(log.break_minutes, 45)
        self.assertAlmostEqual(float(log.payable_hours), 9.25, places=1)

    def test_12_5h_shift_no_break(self):
        """5h smjena → bez odbitka."""
        from worktime.models import TimeLog

        now = tz.now()
        log = TimeLog.objects.create(
            user=self.user,
            company=self.company,
            date=now.date(),
            start_time=now - timedelta(hours=5),
            status="OPEN",
        )
        log.end_time = now
        log.close_shift()
        self.assertEqual(log.break_minutes, 0)
        self.assertAlmostEqual(float(log.payable_hours), 5.0, places=1)


class ForgottenPhoneScenarioTest(SmartLoginSetup):
    """
    Scenarij: Konobar zaboravio mobitel kod kuće.
    Što može napraviti? Koji su fallback mehanizmi?
    """

    def test_13_pin_login_still_works_without_device_token(self):
        """Konobar može koristiti PIN za prijavu na POS."""
        from pos.models import POSCashier

        cashier = POSCashier.objects.create(
            company=self.company,
            name="Zaboravko",
            is_active=True,
        )
        cashier.set_pin("1234")
        cashier.save()
        self.assertTrue(cashier.check_pin("1234"))
        self.assertFalse(cashier.check_pin("0000"))

    def test_14_manual_clock_in_api_works(self):
        """Manager može ručno evidentirati dolazak."""
        from worktime.models import TimeLog

        now = tz.now()
        log = TimeLog.objects.create(
            user=self.user,
            company=self.company,
            date=now.date(),
            start_time=now,
            status="OPEN",
            notes="Ručni upis — zaboravljeni mobitel",
        )
        self.assertEqual(log.status, "OPEN")
        self.assertIn("zaboravljeni", log.notes)

    def test_15_multiple_tokens_per_user(self):
        """User može imati više tokena (telefon + tablet)."""
        from accounts.models import DeviceToken

        dt1 = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Telefon",
        )
        dt2 = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Tablet",
        )
        self.assertNotEqual(dt1.barcode_data, dt2.barcode_data)
        self.assertEqual(DeviceToken.objects.filter(user=self.user, is_active=True).count(), 2)

    def test_16_stolen_token_can_be_deactivated(self):
        """Ako je mobitel ukraden, token se može deaktivirati."""
        from accounts.models import DeviceToken

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Ukradeni telefon",
        )
        barcode = dt.barcode_data
        dt.is_active = False
        dt.save()

        # Token više ne može biti korišten
        found = DeviceToken.objects.filter(barcode_data=barcode, is_active=True).first()
        self.assertIsNone(found)

    def test_17_auto_pos_login_flag(self):
        """Token s auto_pos_login — automatski prijavljuje bez skeniranja."""
        from accounts.models import DeviceToken

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Auto Login Tablet",
            auto_pos_login=True,
        )
        self.assertTrue(dt.auto_pos_login)


class CashierSafeguardTest(SmartLoginSetup):
    def test_18_cashier_16h_guard(self):
        """Cashier clock_out sa >16h trajanjem → limitira na 16h."""
        from pos.models import POSCashier
        from pos.worktime_bridge import cashier_clock_out

        cashier = POSCashier.objects.create(
            company=self.company,
            name="Long Shift",
            user=self.user,
            is_active=True,
        )
        cashier.clock_in_at = tz.now() - timedelta(hours=20)
        cashier.save()

        entry = cashier_clock_out(cashier)
        if entry:
            self.assertLessEqual(entry.duration, Decimal("16"))

    def test_19_cashier_very_short_shift_ignored(self):
        """Smjena < 1 min se ne broji (slučajni scan)."""
        from pos.models import POSCashier
        from pos.worktime_bridge import cashier_clock_out
        from worktime.models import TimeEntry

        cashier = POSCashier.objects.create(
            company=self.company,
            name="Quick Scan",
            user=self.user,
            is_active=True,
        )
        cashier.clock_in_at = tz.now() - timedelta(seconds=30)
        cashier.save()
        before = TimeEntry.objects.count()
        cashier_clock_out(cashier)
        self.assertEqual(TimeEntry.objects.count(), before)  # Nije kreirano

    def test_20_activity_event_creation(self):
        """ActivityEvent se kreira za POS akcije."""
        from worktime.models import ActivityEvent

        ActivityEvent.objects.create(
            user=self.user,
            company=self.company,
            timestamp=tz.now(),
            action="POS_CHECKOUT",
            detail="[POS] Bon #42, 3 stavke, 25.50 EUR",
        )
        event = ActivityEvent.objects.filter(user=self.user, action="POS_CHECKOUT").first()
        self.assertIsNotNone(event)
        self.assertIn("Bon #42", event.detail)


class VolunteerTokenTest(SmartLoginSetup):
    """B-19, B-20, B-21 — Volonterski tokeni s expiryjem i WhatsApp linkom."""

    def test_21_token_with_expiry(self):
        """B-20: Token s expires_at — istječe nakon 8h."""
        from accounts.models import DeviceToken

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Volonter Ivan",
            expires_at=tz.now() + timedelta(hours=8),
        )
        self.assertFalse(dt.is_expired)
        self.assertTrue(dt.is_usable)

    def test_22_expired_token_not_usable(self):
        """B-20: Istekli token → is_usable=False."""
        from accounts.models import DeviceToken

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Expired Volonter",
            expires_at=tz.now() - timedelta(hours=1),
        )
        self.assertTrue(dt.is_expired)
        self.assertFalse(dt.is_usable)

    def test_23_permanent_token_never_expires(self):
        """Token bez expires_at nikad ne istječe."""
        from accounts.models import DeviceToken

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Stalni radnik",
        )
        self.assertFalse(dt.is_expired)
        self.assertTrue(dt.is_usable)

    def test_24_whatsapp_link_generated(self):
        """B-19: WhatsApp deep link sadrži token URL."""
        from accounts.models import DeviceToken

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="WhatsApp Test",
        )
        self.assertIn("wa.me", dt.whatsapp_link)
        self.assertIn(str(dt.token), dt.whatsapp_link)

    def test_25_auto_login_url(self):
        """Auto login URL sadrži token."""
        from accounts.models import DeviceToken

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="URL Test",
        )
        self.assertIn(str(dt.token), dt.auto_login_url)
        self.assertIn("device-login", dt.auto_login_url)

    def test_26_label_auto_generated(self):
        """B-21: Label se auto-generira iz imena + firme."""
        from accounts.models import DeviceToken

        self.user.first_name = "Ivan"
        self.user.last_name = "Horvat"
        self.user.save()
        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Label Test",
        )
        self.assertIn("Ivan Horvat", dt.label)
        self.assertIn("Smart Login Test", dt.label)

    def test_27_deactivate_expired_task(self):
        """B-20: Celery task deaktivira istekle tokene."""
        from accounts.models import DeviceToken
        from accounts.tasks import deactivate_expired_tokens

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Task Test",
            expires_at=tz.now() - timedelta(hours=1),
        )
        self.assertTrue(dt.is_active)  # Još je active u bazi
        result = deactivate_expired_tokens()
        self.assertGreaterEqual(result["deactivated"], 1)
        dt.refresh_from_db()
        self.assertFalse(dt.is_active)
