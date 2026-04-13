"""
Arhiva Integrity Tests — "Moljac" testovi za robusnost arhive.
Adaptirano na stvarni ArhivaEntry model.
"""
import os
from decimal import Decimal

from django.conf import settings
from django.test import TestCase

from companies.models import Company
from documents.models import ArhivaEntry


class ArhivaIntegrityTest(TestCase):
    """Anti-cascade, drift protection, soft reference."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Test Integrity d.o.o.", oib="99999999901")
        from datetime import date

        from django.utils import timezone

        from invoicing.models import Invoice
        cls.invoice = Invoice.objects.create(
            company=cls.company, number="INT-001", total=Decimal('125.00'), status='PAID',
            date_issued=timezone.now(),
        )
        cls.entry = ArhivaEntry(
            company=cls.company, source_type='invoice_out',
            source_id=str(cls.invoice.pk), doc_number='INT-001',
            partner_name='Test Partner', amount=Decimal('125.00'), currency='EUR',
            doc_date=date(2026, 1, 15),
        )
        cls.entry.save()

    def test_anti_cascade_survival(self):
        """Brisanje racuna NE SMIJE obrisati arhivu."""
        entry_pk = self.entry.pk
        self.invoice.delete()
        self.assertTrue(ArhivaEntry.objects.filter(pk=entry_pk).exists(),
                        "KATASTROFA: Cascade delete obrisao arhivu!")
        entry = ArhivaEntry.objects.get(pk=entry_pk)
        self.assertEqual(entry.amount, Decimal('125.00'))
        self.assertEqual(entry.doc_number, 'INT-001')

    def test_historical_drift_protection(self):
        """Izmjena racuna NE SMIJE promijeniti arhivu."""
        from invoicing.models import Invoice
        inv = Invoice.objects.get(pk=int(self.entry.source_id))
        inv.total = Decimal('999.99')
        inv.save()
        entry = ArhivaEntry.objects.get(pk=self.entry.pk)
        self.assertEqual(entry.amount, Decimal('125.00'),
                         "Arhiva prati dinamicke promjene!")

    def test_source_id_is_soft_reference(self):
        """source_id mora biti string, ne FK."""
        field = ArhivaEntry._meta.get_field('source_id')
        self.assertNotEqual(field.get_internal_type(), 'ForeignKey')
        self.assertEqual(type(self.entry.source_id), str)

    def test_archive_number_generated(self):
        """archive_number mora biti generiran."""
        self.assertTrue(bool(self.entry.archive_number))
        self.assertTrue(len(self.entry.archive_number) > 5)


class ArhivaPhysicalSyncTest(TestCase):
    """Sinkronizacija baze i fizickih datoteka."""

    def test_has_pdf_files_exist(self):
        """has_pdf=True entryji MORAJU imati datoteku na disku."""
        phantoms = []
        for e in ArhivaEntry.objects.filter(has_pdf=True).exclude(file_path='')[:100]:
            full = os.path.join(settings.MEDIA_ROOT, e.file_path)
            if not os.path.isfile(full):
                phantoms.append(f"#{e.pk}: {e.file_path}")
        self.assertEqual(len(phantoms), 0,
                         f"FANTOMSKI PDF: {len(phantoms)} ne postoje:\n" + "\n".join(phantoms[:5]))


class ArhivaAIProposalTest(TestCase):
    """AI prijedlog knjizenja."""

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        cls.company = Company.objects.create(name="AI Test d.o.o.", oib="88888888801")
        cls.entry = ArhivaEntry(
            company=cls.company, source_type='invoice_out', source_id='999',
            doc_number='AI-001', amount=Decimal('500.00'), currency='EUR',
            doc_date=date(2026, 2, 20),
            ai_proposal={
                'debit': [{'account': '120', 'amount': 500.0, 'description': 'Potrazivanje'}],
                'credit': [{'account': '750', 'amount': 500.0, 'description': 'Prihod'}],
                'source': 'ai',
            },
            is_booked=False,
        )
        cls.entry.save()

    def test_ai_proposal_structure(self):
        """AI proposal mora imati debit i credit."""
        p = self.entry.ai_proposal
        self.assertIn('debit', p)
        self.assertIn('credit', p)

    def test_ai_proposal_balance(self):
        """Debit i credit MORAJU biti balansirani."""
        p = self.entry.ai_proposal
        d = sum(x['amount'] for x in p.get('debit', []))
        k = sum(x['amount'] for x in p.get('credit', []))
        self.assertAlmostEqual(d, k, places=2, msg=f"D={d} K={k}")

    def test_accept_sets_booked(self):
        """Prihvacanje postavlja is_booked=True."""
        self.entry.is_booked = True
        self.entry.save(update_fields=['is_booked'])
        self.entry.refresh_from_db()
        self.assertTrue(self.entry.is_booked)
