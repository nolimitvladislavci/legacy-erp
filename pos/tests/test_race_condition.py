"""
POS Race Condition Tests + Simulation S4
Testira atomarnost receipt_number, session_number i global_number.

pytest pos/tests/test_race_condition.py -v
"""

import threading
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import TransactionTestCase

from companies.models import Company
from pos.models import POSPaymentLine, POSReceipt, POSReceiptItem, POSSession, POSTerminal


class POSRaceConditionTest(TransactionTestCase):
    """
    TransactionTestCase jer select_for_update ne radi u TestCase
    (koji wrapa sve u jednu transakciju).
    """

    def setUp(self):
        self.user = User.objects.create_user("race_tester", password="test1234")
        self.company = Company.objects.create(
            name="Race Test d.o.o.",
            oib="12345678901",
            owner=self.user,
        )
        self.terminal = POSTerminal.objects.create(
            company=self.company,
            name="Kasa Race",
            terminal_code="RACE01",
            is_active=True,
        )
        self.session = POSSession.objects.create(
            terminal=self.terminal,
            operator=self.user,
            session_number=1,
            opening_cash=Decimal("100"),
            status="open",
        )

    def test_concurrent_receipt_numbers_no_duplicates(self):
        """
        S4-RC01: 10 threadova istovremeno kreiraju receipt u istoj sesiji.
        Nijedan receipt_number ne smije biti duplikat.
        """
        results = []
        errors = []
        barrier = threading.Barrier(10, timeout=10)

        def create_receipt(thread_id):
            try:
                from django.db import connection as conn

                conn.ensure_connection()
                barrier.wait()  # svi krecu u isto vrijeme

                from django.db import transaction
                from django.db.models import Max

                with transaction.atomic():
                    sess = POSSession.objects.select_for_update().get(pk=self.session.pk)
                    max_num = sess.receipts.aggregate(m=Max("receipt_number"))["m"] or 0
                    next_num = max_num + 1
                    r = POSReceipt.objects.create(
                        session=sess,
                        receipt_number=next_num,
                    )
                    results.append(r.receipt_number)
            except (IntegrityError, DatabaseError) as e:
                errors.append(str(e))
            finally:
                conn.close()

        threads = [threading.Thread(target=create_receipt, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        # Svi moraju proci
        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        # Svi receipt_number moraju biti unikatni
        self.assertEqual(len(results), len(set(results)), f"DUPLICATE receipt_numbers: {results}")
        # Moraju biti sekvencijalni 1-10
        self.assertEqual(sorted(results), list(range(1, 11)), f"Not sequential: {sorted(results)}")

    def test_concurrent_session_numbers_no_duplicates(self):
        """
        S4-RC02: 5 threadova istovremeno otvaraju sesiju na istom terminalu.
        Nijedan session_number ne smije biti duplikat.
        """
        # Zatvori postojecu sesiju
        self.session.status = "closed"
        self.session.save()

        results = []
        errors = []
        barrier = threading.Barrier(5, timeout=10)

        def create_session(thread_id):
            try:
                from django.db import connection as conn

                conn.ensure_connection()
                barrier.wait()

                from django.db import transaction
                from django.db.models import Max

                with transaction.atomic():
                    term = POSTerminal.objects.select_for_update().get(pk=self.terminal.pk)
                    max_num = term.sessions.aggregate(m=Max("session_number"))["m"] or 0
                    next_num = max_num + 1
                    s = POSSession.objects.create(
                        terminal=term,
                        operator=self.user,
                        session_number=next_num,
                        status="closed",
                    )
                    results.append(s.session_number)
            except (IntegrityError, DatabaseError) as e:
                errors.append(str(e))
            finally:
                conn.close()

        threads = [threading.Thread(target=create_session, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        self.assertEqual(len(results), len(set(results)), f"DUPLICATE session_numbers: {results}")

    def test_concurrent_global_numbers_no_duplicates(self):
        """
        S4-RC03: 10 threadova kreiraju receiptove — global_number mora biti unikatan.
        """
        results = []
        errors = []
        barrier = threading.Barrier(10, timeout=10)

        def create_with_global(thread_id):
            try:
                from django.db import connection as conn

                conn.ensure_connection()
                barrier.wait()

                # Svaki thread kreira u zasebnoj sesiji (izbjegava receipt_number conflict)
                from django.db import transaction
                from django.db.models import Max

                with transaction.atomic():
                    term = POSTerminal.objects.select_for_update().get(pk=self.terminal.pk)
                    sn = term.sessions.aggregate(m=Max("session_number"))["m"] or 0
                    sess = POSSession.objects.create(
                        terminal=term,
                        operator=self.user,
                        session_number=sn + 1,
                        status="open",
                    )

                with transaction.atomic():
                    r = POSReceipt.objects.create(
                        session=sess,
                        receipt_number=1,
                    )
                    results.append(r.global_number)
            except (IntegrityError, DatabaseError) as e:
                errors.append(str(e))
            finally:
                conn.close()

        threads = [threading.Thread(target=create_with_global, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        self.assertEqual(len(results), len(set(results)), f"DUPLICATE global_numbers: {results}")


class POSSimulationS4Test(TransactionTestCase):
    """
    SIMULACIJA S4: Concurrent POS — dva blagajnika na istoj blagajni,
    simultano kreiraju bonove. Provjera konzistentnosti.
    """

    def setUp(self):
        self.user1 = User.objects.create_user("blagajnik_a", password="test")
        self.user2 = User.objects.create_user("blagajnik_b", password="test")
        self.company = Company.objects.create(
            name="S4 Test d.o.o.",
            oib="99988877766",
            owner=self.user1,
        )
        self.terminal = POSTerminal.objects.create(
            company=self.company,
            name="Kasa S4",
            terminal_code="S4-01",
            is_active=True,
        )

    def test_s4_dual_cashier_concurrent_receipts(self):
        """
        S4-SIM01: Dva blagajnika na istoj blagajni, istovremeno.
        20 bonova ukupno (10 svaki). Zero duplikata.
        """
        session = POSSession.objects.create(
            terminal=self.terminal,
            operator=self.user1,
            session_number=1,
            opening_cash=Decimal("200"),
            status="open",
        )

        all_receipt_nums = []
        all_global_nums = []
        errors = []
        barrier = threading.Barrier(20, timeout=15)

        def cashier_work(thread_id):
            try:
                from django.db import connection as conn

                conn.ensure_connection()
                barrier.wait()

                from django.db import transaction
                from django.db.models import Max

                with transaction.atomic():
                    sess = POSSession.objects.select_for_update().get(pk=session.pk)
                    max_num = sess.receipts.aggregate(m=Max("receipt_number"))["m"] or 0
                    r = POSReceipt.objects.create(
                        session=sess,
                        receipt_number=max_num + 1,
                    )
                    POSReceiptItem.objects.create(
                        receipt=r,
                        description=f"Artikl T{thread_id}",
                        quantity=1,
                        unit_price=Decimal("10.00"),
                        tax_rate=Decimal("25"),
                    )
                    r.total = Decimal("12.50")
                    r.status = "paid"
                    r.save(update_fields=["total", "status"])
                    POSPaymentLine.objects.create(
                        receipt=r,
                        method="CASH",
                        amount=Decimal("12.50"),
                    )
                    all_receipt_nums.append(r.receipt_number)
                    all_global_nums.append(r.global_number)
            except (ValueError, TypeError) as e:
                errors.append(f"T{thread_id}: {e}")
            finally:
                conn.close()

        threads = [threading.Thread(target=cashier_work, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

        # Provjere
        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")
        self.assertEqual(len(all_receipt_nums), 20, "Ne svih 20 bonova kreirano")
        self.assertEqual(
            len(all_receipt_nums), len(set(all_receipt_nums)), f"DUPLICATE receipt_numbers! {sorted(all_receipt_nums)}"
        )
        self.assertEqual(
            len(all_global_nums), len(set(all_global_nums)), f"DUPLICATE global_numbers! {sorted(all_global_nums)}"
        )
        self.assertEqual(
            sorted(all_receipt_nums), list(range(1, 21)), f"Receipt numbers not sequential: {sorted(all_receipt_nums)}"
        )
        # Svi bonovi moraju biti PAID
        paid_count = session.receipts.filter(status="paid").count()
        self.assertEqual(paid_count, 20, f"Only {paid_count}/20 paid")

    def test_s4_receipt_integrity_after_concurrent_creation(self):
        """
        S4-SIM02: Nakon concurrent kreiranja, provjeri DB integritet.
        - Nema rupa u sekvenci
        - Total = items * unit_price * (1 + tax/100)
        """
        session = POSSession.objects.create(
            terminal=self.terminal,
            operator=self.user2,
            session_number=1,
            opening_cash=Decimal("0"),
            status="open",
        )

        errors = []
        barrier = threading.Barrier(5, timeout=10)

        def create_full_receipt(tid):
            try:
                from django.db import connection as conn

                conn.ensure_connection()
                barrier.wait()

                from django.db import transaction
                from django.db.models import Max

                with transaction.atomic():
                    sess = POSSession.objects.select_for_update().get(pk=session.pk)
                    max_num = sess.receipts.aggregate(m=Max("receipt_number"))["m"] or 0
                    r = POSReceipt.objects.create(
                        session=sess,
                        receipt_number=max_num + 1,
                    )
                    for j in range(3):
                        POSReceiptItem.objects.create(
                            receipt=r,
                            description=f"Item-{tid}-{j}",
                            quantity=Decimal("2"),
                            unit_price=Decimal("5.00"),
                            tax_rate=Decimal("25"),
                        )
                    r.recalculate()
                    r.status = "paid"
                    r.save()
            except (ValueError, TypeError) as e:
                errors.append(str(e))
            finally:
                conn.close()

        threads = [threading.Thread(target=create_full_receipt, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        self.assertEqual(len(errors), 0, f"Errors: {errors}")

        # Integrity check
        receipts = list(session.receipts.order_by("receipt_number"))
        self.assertEqual(len(receipts), 5)
        nums = [r.receipt_number for r in receipts]
        self.assertEqual(nums, [1, 2, 3, 4, 5], f"Gap in sequence: {nums}")

        for r in receipts:
            # Svaki bon: 3 stavke * qty 2 * 5.00 = 30.00 neto, +25% = 37.50 bruto
            self.assertEqual(r.items.count(), 3)
            self.assertEqual(r.subtotal, Decimal("30.00"), f"Receipt #{r.receipt_number} subtotal wrong: {r.subtotal}")
            self.assertEqual(r.total, Decimal("37.50"), f"Receipt #{r.receipt_number} total wrong: {r.total}")
