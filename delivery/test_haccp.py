from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from companies.models import Company
from delivery.models import SmartBox, SensorReading, HACCPIncident, analyze_readings

User = get_user_model()


class HACCPAnalysisTests(TestCase):
    """Testovi za HACCP Smart Sensor logiku — 4 scenarija."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="HACCP Test GmbH", oib="DE123456789")

    def setUp(self):
        self.box = SmartBox.objects.create(
            owner_company=self.company,
            box_id='BOX-TEST-001',
            box_type='active_cool',
            qr_code='QR-TEST-001',
            has_sensor=True,
            target_min_temp=Decimal('2.0'),
            target_max_temp=Decimal('8.0'),
        )

    def _reading(self, minutes_ago, temp):
        """Helper: create SensorReading at minutes_ago with given temp."""
        ts = timezone.now() - timedelta(minutes=minutes_ago)
        return SensorReading.objects.create(
            smart_box=self.box,
            source='delivery',
            timestamp=ts,
            temperature=Decimal(str(temp)),
        )

    # ════════════════════════════════════════════════════════════
    # SCENARIJ 1: Otvaranje vrata (lazni alarm)
    # ════════════════════════════════════════════════════════════
    def test_scenario1_door_opening_no_alarm(self):
        """Kratki skok temp 4->10->4 za 2 minute — NEMA alarma."""
        print("\n" + "=" * 60)
        print(" [SCENARIJ 1] OTVARANJE VRATA — LAZNI ALARM")
        print("=" * 60)

        self._reading(10, 4.0)  # -10min: 4C
        self._reading(9, 6.0)   # -9min: 6C
        self._reading(8, 10.0)  # -8min: 10C (iznad 8C, ali kratko)
        self._reading(7, 7.0)   # -7min: 7C
        self._reading(6, 4.0)   # -6min: nazad na 4C

        incidents = analyze_readings(self.box)
        self.box.refresh_from_db()

        print(" -> Ocitanja: 4->6->10->7->4 C (2 min iznad praga)")
        print(f" -> Incidenti: {len(incidents)}")
        print(f" -> Box status: {self.box.haccp_status}")

        self.assertEqual(len(incidents), 0)
        self.assertEqual(self.box.haccp_status, 'ok')
        print(" PASS: Nema alarma — trajanje prekrsaja < 10 min")

    # ════════════════════════════════════════════════════════════
    # SCENARIJ 2: Crknut kompresor (sustained breach >10 min)
    # ════════════════════════════════════════════════════════════
    def test_scenario2_compressor_failure(self):
        """Temp raste 12 minuta iznad praga — SUSTAINED BREACH."""
        print("\n" + "=" * 60)
        print(" [SCENARIJ 2] CRKNUT KOMPRESOR — SUSTAINED BREACH")
        print("=" * 60)

        self._reading(20, 4.0)   # -20min: OK
        self._reading(18, 7.0)   # -18min: OK
        self._reading(16, 9.0)   # -16min: iznad 8C — breach pocinje
        self._reading(14, 10.0)  # -14min: raste
        self._reading(12, 11.0)  # -12min: raste
        self._reading(4, 11.5)   # -4min: jos traje (breach = 12 min)
        self._reading(2, 5.0)    # -2min: nazad na normalu

        incidents = analyze_readings(self.box)
        self.box.refresh_from_db()

        print(" -> Ocitanja: 4->7->9->10->11->11.5->5 C")
        print(f" -> Incidenti: {len(incidents)}")
        if incidents:
            inc = incidents[0]
            print(f" -> Tip: {inc.incident_type}")
            print(f" -> Max temp: {inc.max_temperature}C")
            print(f" -> Trajanje: {inc.duration_minutes} min")
            print(f" -> Opis: {inc.description}")
        print(f" -> Box status: {self.box.haccp_status}")

        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].incident_type, 'sustained_breach')
        self.assertGreaterEqual(incidents[0].duration_minutes, 10)
        self.assertEqual(incidents[0].max_temperature, Decimal('11.5'))
        self.assertIn(self.box.haccp_status, ['critical', 'blocked'])
        print(" PASS: Sustained breach detektiran, box u CRITICAL statusu")

    # ════════════════════════════════════════════════════════════
    # SCENARIJ 3: Tunel + retroaktivna analiza (offline bulk)
    # ════════════════════════════════════════════════════════════
    def test_scenario3_offline_retroactive(self):
        """Bulk od 120 ocitanja — retroaktivni scan otkriva prosli prekrsaj."""
        print("\n" + "=" * 60)
        print(" [SCENARIJ 3] TUNEL — OFFLINE RETROAKTIVNA ANALIZA")
        print("=" * 60)

        # Simulacija: 120 ocitanja svakih 1 min (2 sata)
        # Min 120-90: temp OK (4-6C)
        # Min 90-60: temp raste do 12C (30 min breach!)
        # Min 60-0: temp nazad na 3-4C

        readings = []
        for i in range(120, 90, -1):
            readings.append(self._reading(i, 4.0 + (120 - i) * 0.05))  # 4.0 -> 5.5

        for i in range(90, 60, -1):
            temp = 8.5 + (90 - i) * 0.12  # 8.5 -> 12.1
            readings.append(self._reading(i, round(temp, 1)))

        for i in range(60, 0, -1):
            readings.append(self._reading(i, 3.5 + (60 - i) * 0.02))  # 3.5 -> 4.7

        incidents = analyze_readings(self.box)
        self.box.refresh_from_db()

        total_readings = SensorReading.objects.filter(smart_box=self.box).count()
        print(f" -> Ukupno ocitanja: {total_readings}")
        print(f" -> Incidenti: {len(incidents)}")
        if incidents:
            inc = incidents[0]
            print(f" -> Tip: {inc.incident_type}")
            print(f" -> Max temp: {inc.max_temperature}C")
            print(f" -> Trajanje: {inc.duration_minutes} min")
        print(f" -> Box status: {self.box.haccp_status}")

        self.assertGreater(len(incidents), 0)
        # Should be offline_retroactive because >10 readings in batch
        breach_inc = [i for i in incidents if i.incident_type == 'offline_retroactive']
        self.assertGreater(len(breach_inc), 0)
        self.assertGreaterEqual(breach_inc[0].duration_minutes, 20)
        print(" PASS: Retroaktivni scan otkrio 30-minutni prekrsaj iz proslosti")

    # ════════════════════════════════════════════════════════════
    # SCENARIJ 4: Critical Failure (>15C instant)
    # ════════════════════════════════════════════════════════════
    def test_scenario4_critical_failure_instant(self):
        """Temp > 15C — INSTANT alarm, box BLOKIRAN."""
        print("\n" + "=" * 60)
        print(" [SCENARIJ 4] CRITICAL FAILURE — INSTANT BLOKADA")
        print("=" * 60)

        self._reading(5, 4.0)   # OK
        self._reading(3, 8.0)   # OK
        self._reading(1, 16.5)  # CRITICAL!

        incidents = analyze_readings(self.box)
        self.box.refresh_from_db()

        print(" -> Ocitanja: 4->8->16.5 C")
        print(f" -> Incidenti: {len(incidents)}")
        if incidents:
            print(f" -> Tip: {incidents[0].incident_type}")
            print(f" -> Severity: {incidents[0].severity}")
        print(f" -> Box status: {self.box.haccp_status}")

        critical = [i for i in incidents if i.incident_type == 'critical_failure']
        self.assertGreater(len(critical), 0)
        self.assertEqual(critical[0].severity, 'blocked')
        self.assertEqual(self.box.haccp_status, 'blocked')
        print(" PASS: Instant blokada — box BLOCKED, severity BLOCKED")

    # ════════════════════════════════════════════════════════════
    # SCENARIJ 5: Revizijski trag — resolve incident
    # ════════════════════════════════════════════════════════════
    def test_scenario5_resolve_incident(self):
        """Dispatcher zatvara incident — box se odblokira."""
        print("\n" + "=" * 60)
        print(" [SCENARIJ 5] REVIZIJSKI TRAG — RESOLVE INCIDENT")
        print("=" * 60)

        self._reading(1, 16.5)  # CRITICAL
        incidents = analyze_readings(self.box)
        self.box.refresh_from_db()

        self.assertEqual(self.box.haccp_status, 'blocked')
        print(f" -> Box blokiran: {self.box.haccp_status}")

        # Dispatcher resolves
        user = User.objects.create_user(username='dispatcher_test', password='pwd')
        inc = incidents[0]
        inc.resolve(user, 'Vozac prebacio meso u rezervni hladnjak, roba spasena')

        inc.refresh_from_db()
        self.box.refresh_from_db()

        print(f" -> Incident resolved: {inc.is_resolved}")
        print(f" -> Resolution: {inc.resolution_note}")
        print(f" -> Resolved by: {inc.resolved_by}")
        print(f" -> Box status: {self.box.haccp_status}")

        self.assertTrue(inc.is_resolved)
        self.assertEqual(inc.resolution_note, 'Vozac prebacio meso u rezervni hladnjak, roba spasena')
        self.assertEqual(self.box.haccp_status, 'ok')
        print(" PASS: Incident zatvoren, box odblokiran, audit trail sacrvan")

    # ════════════════════════════════════════════════════════════
    # SCENARIJ 6: Duplikat prevencija
    # ════════════════════════════════════════════════════════════
    def test_no_duplicate_incidents(self):
        """analyze_readings pozvan dvaput ne kreira duplikate."""
        print("\n" + "=" * 60)
        print(" [SCENARIJ 6] DUPLIKAT PREVENCIJA")
        print("=" * 60)

        self._reading(1, 16.5)  # CRITICAL
        incidents1 = analyze_readings(self.box)
        incidents2 = analyze_readings(self.box)

        total = HACCPIncident.objects.filter(smart_box=self.box).count()
        print(f" -> Prvi poziv: {len(incidents1)} incident(a)")
        print(f" -> Drugi poziv: {len(incidents2)} incident(a)")
        print(f" -> Ukupno u bazi: {total}")

        self.assertEqual(len(incidents1), 1)
        self.assertEqual(len(incidents2), 0)
        self.assertEqual(total, 1)
        print(" PASS: Nema duplikata")
