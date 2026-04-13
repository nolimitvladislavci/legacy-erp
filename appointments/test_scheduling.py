"""
appointments/test_scheduling.py
════════════════════════════════════════════════════════════════════════════════
Matrica Loma — Polimorfno Raspoređivanje (Scenariji 9.1, 9.2, 9.3)

Testira tri paradoksa scheduling enginea PRIJE izrade kalendar UI-a.
Koristi PRAVI scheduling.py engine (book_slot + select_for_update).
Nema mocka. Nema komentiranih assertova.

  9.1 Actor Shortage   — 5 stolica, 2 frizera → 3. termin MORA pasti (409)
  9.2 Resource Shortage — 4 mehaničara, 2 dizalice → 3. termin MORA pasti (409)
  9.3 Race Condition   — 2 threada, 1 slot → samo 1 prolazi, drugi dobiva 409

Pokretanje:
    manage.py test appointments.test_scheduling --verbosity=2
"""

import datetime
import threading
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from appointments.models import Appointment, BookingResource, BookingService, WorkingHours
from appointments.scheduling import SchedulingError, book_slot, check_availability
from companies.models import Company

User = get_user_model()

# ── Pomoćne funkcije ──────────────────────────────────────────────────────────


def _make_aware(date_str, time_str):
    """Kreira timezone-aware datetime iz stringa."""
    dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return timezone.make_aware(dt)


def _create_actor(company, name):
    """
    Kreira radnika (BookingResource tipa 'ljudstvo') s radnim satima
    za sva 7 dana tjedna (07:00-20:00) kako bi bio dostupan za svaki test slot.
    """
    actor = BookingResource.objects.create(
        company=company,
        name=name,
        resource_type="ljudstvo",
        is_active=True,
    )
    for day in range(7):
        WorkingHours.objects.create(
            resource=actor,
            day_of_week=day,
            start_time=datetime.time(7, 0),
            end_time=datetime.time(20, 0),
            is_day_off=False,
        )
    return actor


def _create_physical_resource(company, name, res_type):
    """Kreira fizički resurs (stolica, dizalica, kabina...)."""
    return BookingResource.objects.create(
        company=company,
        name=name,
        resource_type=res_type,
        is_active=True,
    )


def _create_service(company, name, requires_actor, requires_resource, res_type, duration_min=30):
    """Kreira BookingService s točnim flagovima."""
    return BookingService.objects.create(
        name=name,
        duration=datetime.timedelta(minutes=duration_min),
        resource_type=res_type,
        requires_actor=requires_actor,
        requires_resource=requires_resource,
        price=Decimal("25.00"),
        is_active=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIJ 9.1 — Actor Shortage Paradox
#
# Frizerski salon: 5 stolica (oprema), 2 frizera (ljudstvo).
# Booking traži I stolicu I frizera.
# → Treći istovremeni termin mora pasti jer nema slobodnih frizera,
#   čak i ako ima 3 prazne stolice.
# ══════════════════════════════════════════════════════════════════════════════


class Test91_ActorShortageParadox(TestCase):
    """9.1: Manjak izvršitelja — svi resursi slobodni, nema tko raditi."""

    # Datum u budućnosti — utorak (weekday=1)
    SLOT_DATE = "2026-03-10"
    SLOT_TIME = "09:00"

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            name="Frizerski Salon Test",
            oib="91100000001",
        )

        # 2 frizera (actors = BookingResource tipa 'ljudstvo')
        cls.frizer_1 = _create_actor(cls.company, "Frizer Ana")
        cls.frizer_2 = _create_actor(cls.company, "Frizer Marko")

        # 5 stolica (fizički resursi tipa 'oprema')
        cls.stolice = [_create_physical_resource(cls.company, f"Stolica {i}", "oprema") for i in range(1, 6)]

        # Usluga "Šišanje": zahtijeva I frizera I stolicu
        # resource_type='oprema' → engine traži slobodnu stolicu
        # requires_actor=True    → engine traži slobodnog frizera (ljudstvo)
        cls.sisanje = _create_service(
            cls.company,
            name="Šišanje",
            requires_actor=True,
            requires_resource=True,
            res_type="oprema",
            duration_min=30,
        )

    def _book(self):
        start = _make_aware(self.SLOT_DATE, self.SLOT_TIME)
        end = start + datetime.timedelta(minutes=30)
        return book_slot(
            company=self.company,
            service=self.sisanje,
            start_dt=start,
            end_dt=end,
        )

    # ── Test 9.1a: Prvih 2 termina prolaze ───────────────────────────────────

    def test_PASS_prva_dva_termina_prolaze(self):
        """
        Frizer 1 dobiva termin 1, Frizer 2 dobiva termin 2.
        Oba moraju proći bez greške.
        """
        appt1 = self._book()
        appt2 = self._book()

        self.assertIsNotNone(appt1.pk, "Termin 1 nije kreiran")
        self.assertIsNotNone(appt2.pk, "Termin 2 nije kreiran")
        self.assertNotEqual(appt1.resource_id, appt2.resource_id, "Oba termina ne smiju biti na istom frizeru!")
        print("  [PASS] 9.1a: Termin 1 → %s | Termin 2 → %s" % (appt1.resource.name, appt2.resource.name))

    # ── Test 9.1b: TREĆI termin mora pasti — nema frizera ────────────────────

    def test_FAIL_treci_termin_pada_bez_frizera(self):
        """
        KRITIČNI TEST: Nakon što su oba frizera zauzeta, treći termin
        mora biti odbijen s SchedulingError('...izvrsitelja...', code='NO_ACTOR').
        Ima 3 prazne stolice — ali nema tko raditi!
        """
        # Zauzmi oba frizera
        self._book()
        self._book()

        # Treći pokušaj — mora pasti
        with self.assertRaises(SchedulingError) as ctx:
            self._book()

        err = ctx.exception
        self.assertEqual(
            err.code, "NO_ACTOR", "Kritična greška 9.1: Kod greške mora biti NO_ACTOR, dobiven: %s" % err.code
        )
        self.assertIn(
            "izvrs",
            err.message.lower(),
            'Poruka mora sadrzavati "izvrs..." (izvrsitelja/izvrsitelji). Dobiveno: %s' % err.message,
        )
        print('  [PASS] 9.1b: 3. termin odbijen — NO_ACTOR: "%s"' % err.message)
        print("         Stolice slobodne: %d/5, ali frizeri zauzeti: 2/2" % 3)

    # ── Test 9.1c: check_availability vraća False za treći slot ──────────────

    def test_FAIL_check_availability_vraca_false(self):
        """
        check_availability() (za UI slot display) mora vraćati False/NO_ACTOR
        nakon što su oba frizera zauzeta.
        """
        self._book()
        self._book()

        start = _make_aware(self.SLOT_DATE, self.SLOT_TIME)
        end = start + datetime.timedelta(minutes=30)
        available, reason = check_availability(self.company, self.sisanje, start, end)

        self.assertFalse(available, "check_availability mora biti False kad nema slobodnih frizera")
        self.assertEqual(reason, "NO_ACTOR", "Razlog mora biti NO_ACTOR, dobiven: %s" % reason)
        print("  [PASS] 9.1c: check_availability = False / NO_ACTOR (UI zaključa slot)")


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIJ 9.2 — Resource Shortage Paradox
#
# Auto servis: 4 mehaničara, 2 dizalice (oprema).
# Booking traži I mehaničara I dizalicu.
# → Treći termin mora pasti jer nema slobodnih dizalica,
#   čak i ako ima 2 slobodna mehaničara.
# ══════════════════════════════════════════════════════════════════════════════


class Test92_ResourceShortageParadox(TestCase):
    """9.2: Manjak fizičkog resursa — mehaničari slobodni, nema dizalice."""

    SLOT_DATE = "2026-03-11"
    SLOT_TIME = "10:00"

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            name="Auto Servis Test",
            oib="92200000002",
        )

        # 4 mehaničara (actors)
        cls.mehanicari = [_create_actor(cls.company, f"Mehaničar {i}") for i in range(1, 5)]

        # 2 dizalice (fizički resursi tipa 'oprema')
        cls.dizalice = [_create_physical_resource(cls.company, f"Dizalica {i}", "oprema") for i in range(1, 3)]

        # Usluga "Veliki servis": zahtijeva I mehaničara I dizalicu
        cls.servis = _create_service(
            cls.company,
            name="Veliki Servis Auta",
            requires_actor=True,
            requires_resource=True,
            res_type="oprema",
            duration_min=120,
        )

    def _book(self):
        start = _make_aware(self.SLOT_DATE, self.SLOT_TIME)
        end = start + datetime.timedelta(minutes=120)
        return book_slot(
            company=self.company,
            service=self.servis,
            start_dt=start,
            end_dt=end,
        )

    # ── Test 9.2a: Prva 2 prolaze ─────────────────────────────────────────────

    def test_PASS_prva_dva_servisa_prolaze(self):
        """
        Dizalica 1 → Mehaničar 1, Dizalica 2 → Mehaničar 2. Oba prolaze.
        """
        appt1 = self._book()
        appt2 = self._book()

        self.assertIsNotNone(appt1.pk)
        self.assertIsNotNone(appt2.pk)
        print("  [PASS] 9.2a: Servis 1 i 2 zakazani (2/2 dizalice zauzete)")

    # ── Test 9.2b: TREĆI termin mora pasti — nema dizalice ───────────────────

    def test_FAIL_treci_servis_pada_bez_dizalice(self):
        """
        KRITIČNI TEST: 2 dizalice zauzete, 2 mehaničara slobodna.
        Treći termin mora biti odbijen s code='NO_RESOURCE'.
        Mehaničar ne može raditi bez dizalice!
        """
        # Zauzmi obje dizalice
        self._book()
        self._book()

        # Treći pokušaj — mora pasti
        with self.assertRaises(SchedulingError) as ctx:
            self._book()

        err = ctx.exception
        self.assertEqual(
            err.code,
            "NO_RESOURCE",
            "Kritična greška 9.2: Kod greške mora biti NO_RESOURCE, dobiven: %s\n"
            "Mehaničar je slobodan, ali booking ne smije proći bez dizalice!" % err.code,
        )
        self.assertIn("resurs", err.message.lower(), 'Poruka mora sadrzavati "resurs". Dobiveno: %s' % err.message)
        print('  [PASS] 9.2b: 3. servis odbijen — NO_RESOURCE: "%s"' % err.message)
        print("         Mehaničari slobodni: 2/4, ali dizalice zauzete: 2/2")

    # ── Test 9.2c: 4. termin prolazi u drugom slotu (dizalice slobodne) ───────

    def test_PASS_drugi_slot_prolazi(self):
        """
        Isti dan, ali 2 sata kasnije — dizalice slobodne → mora proći.
        """
        # Zauzmi oba slota u 10:00
        self._book()
        self._book()

        # Novi slot u 14:00 — dizalice slobodne
        start = _make_aware(self.SLOT_DATE, "14:00")
        end = start + datetime.timedelta(minutes=120)
        appt = book_slot(
            company=self.company,
            service=self.servis,
            start_dt=start,
            end_dt=end,
        )
        self.assertIsNotNone(appt.pk, "Termin u slobodnom slotu mora proći")
        print("  [PASS] 9.2c: Termin u 14:00 prolazi (dizalice slobodne)")


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIJ 9.3 — Race Condition (Concurrency)
#
# 2 threada klikaju na ISTI posljednji slobodni termin u istoj milisekundi.
# select_for_update() mora osigurati da samo 1 prolazi, 2. dobiva 409.
# ══════════════════════════════════════════════════════════════════════════════


class Test93_ConcurrencyRaceCondition(TransactionTestCase):
    """
    9.3: Race Condition — select_for_update() mora spriječiti double-booking.

    Koristimo TransactionTestCase (ne TestCase) jer:
    - TestCase omata sve u jednu transakciju koja se nikad ne commita
    - select_for_update() radi samo unutar commitanih transakcija
    - Threadovi moraju raditi u zasebnim transakcijama
    """

    SLOT_DATE = "2026-03-12"
    SLOT_TIME = "14:00"

    def setUp(self):
        self.company = Company.objects.create(
            name="Race Condition Test Hub",
            oib="93300000003",
        )

        # 1 frizer, 1 stolica — samo JEDAN termin može proći
        self.frizer = _create_actor(self.company, "Jedini Frizer")
        self.stolica = _create_physical_resource(self.company, "Jedina Stolica", "oprema")

        self.sisanje = _create_service(
            self.company,
            name="Šišanje RC Test",
            requires_actor=True,
            requires_resource=True,
            res_type="oprema",
            duration_min=30,
        )

    def test_FAIL_race_condition_sprijecen(self):
        """
        KRITIČNI TEST: 2 threada istovremeno bookaju isti jedini slobodni slot.
        Rezultat MORA biti točno: 1x uspjeh (201/200), 1x konflikt (SchedulingError).
        Ako select_for_update() ne radi → oba prođu → double-booking!
        """
        results = []
        errors = []
        barrier = threading.Barrier(2)  # Sinkronizira start threadova

        def attempt_booking():
            barrier.wait()  # Oba threada čekaju jedan drugog → simulira "isti trenutak"
            try:
                start = _make_aware(self.SLOT_DATE, self.SLOT_TIME)
                end = start + datetime.timedelta(minutes=30)
                appt = book_slot(
                    company=self.company,
                    service=self.sisanje,
                    start_dt=start,
                    end_dt=end,
                )
                results.append(("ok", appt.pk))
            except SchedulingError as e:
                results.append(("conflict", e.code))
            except AttributeError as e:
                errors.append(str(e))

        t1 = threading.Thread(target=attempt_booking)
        t2 = threading.Thread(target=attempt_booking)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Provjera grešaka u threadovima
        self.assertEqual(errors, [], "Neočekivane greške u threadovima: %s" % errors)

        # Mora biti točno 2 rezultata
        self.assertEqual(len(results), 2, "Moramo imati točno 2 rezultata, dobiveno: %d" % len(results))

        statuses = [r[0] for r in results]

        # Točno 1 uspješan booking
        ok_count = statuses.count("ok")
        conflict_count = statuses.count("conflict")

        print("\n  Rezultati threadova: %s" % results)

        self.assertEqual(
            ok_count,
            1,
            "RACE CONDITION PROPUST: %d bookinga prošla umjesto 1!\n"
            "select_for_update() ne radi ispravno — double-booking je moguć!" % ok_count,
        )

        self.assertEqual(conflict_count, 1, "Mora biti točno 1 konflikt, dobiveno: %d" % conflict_count)

        # Provjeri da u bazi postoji SAMO JEDAN appointment
        appt_count = Appointment.objects.filter(
            company=self.company,
            start_time__date=datetime.date(2026, 3, 12),
            status__in=["scheduled", "confirmed"],
        ).count()

        self.assertEqual(appt_count, 1, "DOUBLE BOOKING U BAZI: Pronađeno %d termina za isti slot!" % appt_count)

        print("  [PASS] 9.3: Race condition spriječen — %d booking, %d conflict" % (ok_count, conflict_count))
        print("         Baza sadrži točno 1 termin ✓")

    def test_PASS_sekvencijalni_booking_radi(self):
        """
        Sanity check: sekvencijalni booking (ne paralelni) mora raditi normalno.
        """
        start = _make_aware(self.SLOT_DATE, self.SLOT_TIME)
        end = start + datetime.timedelta(minutes=30)

        appt = book_slot(
            company=self.company,
            service=self.sisanje,
            start_dt=start,
            end_dt=end,
        )
        self.assertIsNotNone(appt.pk)

        # Drugi pokušaj na isti slot → mora pasti
        with self.assertRaises(SchedulingError):
            book_slot(
                company=self.company,
                service=self.sisanje,
                start_dt=start,
                end_dt=end,
            )

        print("  [PASS] 9.3 sanity: Sekvencijalni booking radi ispravno")
