from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from decimal import Decimal
import datetime
from companies.models import Company
from accounts.models import UserProfile
from registration.models import CompanySubscription
from worktime.models import TimeEntry, EmployeeProfile, Project

User = get_user_model()


class NightHoursTests(TestCase):
    """Testovi za noćne sate — interval overlap matematika."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="NachtTest GmbH", oib="DE111222333")
        cls.user = User.objects.create_user(username="nacht_worker", password="pwd")
        cls.profile = EmployeeProfile.objects.create(
            user=cls.user, company=cls.company,
            hourly_rate=Decimal('20.00'), overtime_rate=Decimal('30.00'),
            daily_hours=Decimal('8.00')
        )
        cls.project = Project.objects.create(
            company=cls.company, code="NACHT", name="Nachtschicht"
        )

    def _make_entry(self, start_h, start_m, end_h, end_m, duration_hours):
        entry = TimeEntry(
            company=self.company, user=self.user, project=self.project,
            date=datetime.date(2026, 3, 15),
            start_time=datetime.time(start_h, start_m),
            end_time=datetime.time(end_h, end_m),
            duration=Decimal(str(duration_hours)),
        )
        entry.save()
        return entry

    def test_full_night_shift_22_to_06(self):
        """Kompletna noćna smjena 22:00-06:00 = 8h noćnih."""
        print("\n" + "=" * 60)
        print(" [TEST] PUNA NOĆNA SMJENA 22:00 - 06:00")
        print("=" * 60)

        entry = self._make_entry(22, 0, 6, 0, 8)

        print(f" -> Trajanje: {entry.duration}h")
        print(f" -> Noćni sati: {entry.night_hours}h (očekivano: 8.0)")
        print(f" -> Redovni: {entry.regular_hours}h | Prekovremeni: {entry.overtime_hours}h")

        self.assertEqual(entry.night_hours, Decimal('8.0'))
        self.assertEqual(entry.regular_hours, Decimal('8.00'))
        self.assertEqual(entry.overtime_hours, Decimal('0'))
        self.assertTrue(entry.is_night_work)
        print(" ✅ Puna noćna smjena — svi sati su noćni.")

    def test_cross_midnight_shift_23_to_03(self):
        """Smjena preko ponoći 23:00-03:00 = 4h, svi noćni."""
        print("\n" + "=" * 60)
        print(" [TEST] SMJENA PREKO PONOĆI 23:00 - 03:00")
        print("=" * 60)

        entry = self._make_entry(23, 0, 3, 0, 4)

        print(f" -> Trajanje: {entry.duration}h")
        print(f" -> Noćni sati: {entry.night_hours}h (očekivano: 4.0)")

        self.assertEqual(entry.night_hours, Decimal('4.0'))
        self.assertTrue(entry.is_night_work)
        print(" ✅ Sve 4 sata su noćne (1h prije ponoći + 3h poslije).")

    def test_partial_night_20_to_23(self):
        """Smjena 20:00-23:00 = 3h, od toga 1h noćni (22-23)."""
        print("\n" + "=" * 60)
        print(" [TEST] DJELOMIČNA NOĆ 20:00 - 23:00")
        print("=" * 60)

        entry = self._make_entry(20, 0, 23, 0, 3)

        print(f" -> Trajanje: {entry.duration}h")
        print(f" -> Noćni sati: {entry.night_hours}h (očekivano: 1.0)")

        self.assertEqual(entry.night_hours, Decimal('1.0'))
        self.assertTrue(entry.is_night_work)
        print(" ✅ Samo 1h noćnog rada (22:00-23:00).")

    def test_early_morning_04_to_08(self):
        """Rana jutarnja 04:00-08:00 = 4h, od toga 2h noćni (04-06)."""
        print("\n" + "=" * 60)
        print(" [TEST] RANO JUTRO 04:00 - 08:00")
        print("=" * 60)

        entry = self._make_entry(4, 0, 8, 0, 4)

        print(f" -> Trajanje: {entry.duration}h")
        print(f" -> Noćni sati: {entry.night_hours}h (očekivano: 2.0)")

        self.assertEqual(entry.night_hours, Decimal('2.0'))
        print(" ✅ 2h noćnog rada (04:00-06:00).")

    def test_day_shift_no_night(self):
        """Dnevna smjena 08:00-16:00 = 0 noćnih sati."""
        print("\n" + "=" * 60)
        print(" [TEST] DNEVNA SMJENA 08:00 - 16:00 (BEZ NOĆNIH)")
        print("=" * 60)

        entry = self._make_entry(8, 0, 16, 0, 8)

        print(f" -> Trajanje: {entry.duration}h")
        print(f" -> Noćni sati: {entry.night_hours}h (očekivano: 0)")

        self.assertEqual(entry.night_hours, Decimal('0'))
        self.assertFalse(entry.is_night_work)
        print(" ✅ Nula noćnih sati — čista dnevna smjena.")


class ShortShiftAndBreakComplianceTests(TestCase):
    """Testovi za kratke smjene i ArbZG pauze."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="BreakTest GmbH", oib="DE444555666")
        cls.user = User.objects.create_user(username="break_worker", password="pwd")
        cls.profile = EmployeeProfile.objects.create(
            user=cls.user, company=cls.company,
            hourly_rate=Decimal('15.00'), overtime_rate=Decimal('22.50'),
            daily_hours=Decimal('8.00')
        )
        cls.project = Project.objects.create(
            company=cls.company, code="BRK", name="Break Tests"
        )

    def test_short_shift_no_warnings(self):
        """Kratka smjena 3h — bez prekovremenih, bez compliance upozorenja."""
        print("\n" + "=" * 60)
        print(" [TEST] KRATKA SMJENA 3H — BEZ UPOZORENJA")
        print("=" * 60)

        entry = TimeEntry(
            company=self.company, user=self.user, project=self.project,
            date=datetime.date(2026, 3, 15), duration=Decimal('3.00'),
        )
        entry.save()

        print(f" -> Trajanje: {entry.duration}h")
        print(f" -> Redovni: {entry.regular_hours}h | Prekovremeni: {entry.overtime_hours}h")
        print(f" -> Compliance: '{entry.compliance_note}'")

        self.assertEqual(entry.regular_hours, Decimal('3.00'))
        self.assertEqual(entry.overtime_hours, Decimal('0'))
        self.assertEqual(entry.compliance_note, '')
        print(" ✅ Kratka smjena bez ikakvih upozorenja.")

    def test_exactly_6h_no_break_warns(self):
        """Točno 6h rada bez pauze — ArbZG §4 upozorenje."""
        print("\n" + "=" * 60)
        print(" [TEST] TOČNO 6H BEZ PAUZE — TREBA UPOZORENJE")
        print("=" * 60)

        entry = TimeEntry(
            company=self.company, user=self.user, project=self.project,
            date=datetime.date(2026, 3, 15), duration=Decimal('6.00'),
            break_minutes=0,
        )
        entry.save()

        print(f" -> Trajanje: {entry.duration}h | Pauza: {entry.break_minutes} min")
        print(f" -> Compliance: '{entry.compliance_note}'")

        self.assertIn('pauza <30min za 6+h', entry.compliance_note)
        print(" ✅ ArbZG §4 upozorenje aktivirano za 6h bez pauze.")

    def test_5h59_no_break_ok(self):
        """5.98h (5h59min) bez pauze — NEMA upozorenja (ispod 6h praga)."""
        print("\n" + "=" * 60)
        print(" [TEST] 5H 59MIN BEZ PAUZE — BEZ UPOZORENJA")
        print("=" * 60)

        entry = TimeEntry(
            company=self.company, user=self.user, project=self.project,
            date=datetime.date(2026, 3, 15), duration=Decimal('5.98'),
            break_minutes=0,
        )
        entry.save()

        print(f" -> Trajanje: {entry.duration}h | Pauza: {entry.break_minutes} min")
        print(f" -> Compliance: '{entry.compliance_note}'")

        self.assertEqual(entry.compliance_note, '')
        print(" ✅ Ispod 6h praga — nema upozorenja.")

    def test_9h_with_30min_break_warns(self):
        """9h rada s 30min pauze — treba upozorenje (ArbZG §4 zahtijeva 45min za 9+h)."""
        print("\n" + "=" * 60)
        print(" [TEST] 9H SA 30MIN PAUZE — TREBA 45MIN UPOZORENJE")
        print("=" * 60)

        entry = TimeEntry(
            company=self.company, user=self.user, project=self.project,
            date=datetime.date(2026, 3, 15), duration=Decimal('9.00'),
            break_minutes=30,
        )
        entry.save()

        print(f" -> Trajanje: {entry.duration}h | Pauza: {entry.break_minutes} min")
        print(f" -> Compliance: '{entry.compliance_note}'")

        self.assertNotIn('pauza <30min za 6+h', entry.compliance_note)
        self.assertIn('pauza <45min za 9+h', entry.compliance_note)
        print(" ✅ 30min zadovoljava 6h prag ali NE 9h prag — točno detektira.")

    def test_9h_with_45min_break_clean(self):
        """9h rada s 45min pauze — čisto, bez upozorenja."""
        print("\n" + "=" * 60)
        print(" [TEST] 9H SA 45MIN PAUZE — ČISTO")
        print("=" * 60)

        entry = TimeEntry(
            company=self.company, user=self.user, project=self.project,
            date=datetime.date(2026, 3, 15), duration=Decimal('9.00'),
            break_minutes=45,
        )
        entry.save()

        print(f" -> Trajanje: {entry.duration}h | Pauza: {entry.break_minutes} min")
        print(f" -> Compliance: '{entry.compliance_note}'")

        self.assertEqual(entry.compliance_note, '')
        self.assertEqual(entry.overtime_hours, Decimal('1.00'))
        print(" ✅ 45min pauze za 9h — sve čisto, 1h prekovremeni.")


from django.test import override_settings

@override_settings(SECURE_SSL_REDIRECT=False)
class PayrollViewTests(TestCase):
    """HTTP testovi za inspector print i payroll summary viewove."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="ViewTest GmbH", oib="DE777888999")
        cls.user = User.objects.create_user(username="view_tester", password="pwd")
        cls.user_profile, _ = UserProfile.objects.get_or_create(
            user=cls.user, defaults={'company': cls.company, 'role': 'company_admin'}
        )
        cls.user_profile.company = cls.company
        cls.user_profile.save()
        cls.emp_profile = EmployeeProfile.objects.create(
            user=cls.user, company=cls.company,
            hourly_rate=Decimal('20.00'), overtime_rate=Decimal('30.00'),
            daily_hours=Decimal('8.00')
        )
        cls.subscription = CompanySubscription.objects.create(
            company=cls.company, plan='enterprise',
            valid_from=datetime.date(2026, 1, 1),
            monthly_fee=Decimal('0'),
            is_active=True,
            modules_override=['worktime'],
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_inspector_print_200(self):
        """Inspector print stranica vraća HTTP 200."""
        print("\n" + "=" * 60)
        print(" [TEST] GET /worktime/inspector/ — HTTP 200")
        print("=" * 60)

        response = self.client.get('/worktime/inspector/', secure=False)

        print(f" -> Status: {response.status_code}")
        self.assertEqual(response.status_code, 200)
        print(" ✅ Inspector print view radi.")

    def test_payroll_summary_200(self):
        """Payroll summary stranica vraća HTTP 200."""
        print("\n" + "=" * 60)
        print(" [TEST] GET /worktime/payroll/ — HTTP 200")
        print("=" * 60)

        response = self.client.get('/worktime/payroll/', secure=False)

        print(f" -> Status: {response.status_code}")
        self.assertEqual(response.status_code, 200)
        print(" ✅ Payroll summary view radi.")

    def test_inspector_print_unauthenticated_redirects(self):
        """Neautenticirani korisnik dobiva redirect na login."""
        print("\n" + "=" * 60)
        print(" [TEST] GET /worktime/inspector/ BEZ LOGINA — REDIRECT")
        print("=" * 60)

        client = Client()  # fresh, not logged in
        response = client.get('/worktime/inspector/', secure=False)

        print(f" -> Status: {response.status_code}")
        self.assertEqual(response.status_code, 302)
        print(" ✅ Bez logina — redirect na login stranicu.")
