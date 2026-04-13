from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import datetime
from unittest.mock import patch
from companies.models import Company
from worktime.models import TimeEntry, EmployeeProfile, Project, ActiveTimer

User = get_user_model()

class SupremePayrollAndTimerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Steiger Transport", oib="DE987654321")
        cls.user = User.objects.create_user(username="vozac_wacker", password="pwd")
        cls.profile = EmployeeProfile.objects.create(
            user=cls.user, company=cls.company,
            hourly_rate=Decimal('20.00'), overtime_rate=Decimal('30.00'), daily_hours=Decimal('8.00')
        )
        cls.project = Project.objects.create(
            company=cls.company, code="NIGHT-OPS", name="Stuttgart Logistika"
        )

    def test_active_timer_flow(self):
        print("\n" + "="*60)
        print(" [DETALJNI TEST] SIMULACIJA ŠTOPERICE (START -> PAUZA -> STOP)")
        print("="*60)

        start_time = timezone.make_aware(datetime.datetime(2026, 3, 10, 20, 0, 0))
        print(f" [1] Radnik klika START u: {start_time.strftime('%H:%M:%S')}")
        timer = ActiveTimer.objects.create(
            user=self.user, company=self.company, project=self.project, status='RUNNING', started_at=start_time
        )

        pause_time = timezone.make_aware(datetime.datetime(2026, 3, 11, 0, 0, 0))
        print(f" [2] Radnik klika PAUZA u: {pause_time.strftime('%H:%M:%S')}")
        with patch('worktime.models.timezone.now', return_value=pause_time):
            timer.pause()
        print(f"     -> Sustav računa akumulirano: {timer.accumulated_seconds} sekundi (Očekivano: 14400s / 4h)")

        resume_time = timezone.make_aware(datetime.datetime(2026, 3, 11, 1, 0, 0))
        print(f" [3] Radnik klika RESUME u: {resume_time.strftime('%H:%M:%S')} (Nakon 1h pauze)")
        with patch('worktime.models.timezone.now', return_value=resume_time):
            timer.resume()

        stop_time = timezone.make_aware(datetime.datetime(2026, 3, 11, 6, 0, 0))
        print(f" [4] Radnik klika STOP u: {stop_time.strftime('%H:%M:%S')}")
        with patch('worktime.models.timezone.now', return_value=stop_time):
            entry = timer.stop_and_save()

        print("-" * 60)
        print(" MATEMATIKA NAKON GAŠENJA ŠTOPERICE:")
        print(f" -> Ukupno izračunato trajanje (Duration): {entry.duration} sati")
        print(" -> Baza za redovni rad (Limit): 8.00 sati")
        print(f" -> Sustav odvaja REDOVNO: {entry.regular_hours} sati")
        print(f" -> Sustav odvaja PREKOVREMENO ({entry.duration} - 8.00): {entry.overtime_hours} sati")

        self.assertEqual(entry.duration, Decimal('9.00'))
        self.assertEqual(entry.regular_hours, Decimal('8.00'))
        self.assertEqual(entry.overtime_hours, Decimal('1.00'))
        print(" ✅ REZULTAT: Sva matematika se savršeno poklapa.")

    def test_extreme_compliance_violation(self):
        print("\n" + "="*60)
        print(" [DETALJNI TEST] EKSTREMNA SMJENA (>16H)")
        print("="*60)
        print(" [1] Radnik (ili Gazda) ručno unosi 16 sati rada.")
        entry = TimeEntry(
            company=self.company, user=self.user, project=self.project,
            date=datetime.date(2026, 3, 15), duration=Decimal('16.00')
        )
        entry.save()

        print("-" * 60)
        print(" MATEMATIKA I ZAKON (ArbZG):")
        print(f" -> Ukupan unos: {entry.duration} sati")
        print(" -> Redovni sati limit: 8.00 sati")
        print(f" -> Izračun Prekovremeni ({entry.duration} - 8.00): {entry.overtime_hours} sati")
        print(f" -> Sigurnosni senzor za >10h aktiviran: '{entry.compliance_note}'")

        self.assertEqual(entry.regular_hours, Decimal('8.00'))
        self.assertEqual(entry.overtime_hours, Decimal('8.00'))
        self.assertTrue("10h" in entry.compliance_note)
        print(" ✅ REZULTAT: Sustav točno razdvaja 8+8 i pali crveni alarm za inspekciju.")

