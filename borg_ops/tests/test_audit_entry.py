"""
Tests for BorgAuditEntry — immutability, creation, hooks.
Target: 13 tests
"""

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from borg_ops.audit_helpers import log_borg_audit
from borg_ops.models import BorgAuditEntry, BorgBriefingConfig, BorgTask


class BorgAuditEntryModelTest(TestCase):
    """Test BorgAuditEntry immutability and creation."""

    def setUp(self):
        from companies.models import Company

        self.company = Company.objects.create(name="Test Firma d.o.o.", oib="12345678901")

    def test_create_basic_entry(self):
        """BorgAuditEntry can be created with minimal fields."""
        entry = BorgAuditEntry(
            company=self.company,
            entry_type="FISCAL",
            summary="Test fiskalizacija",
        )
        entry.save()
        self.assertIsNotNone(entry.pk)
        self.assertEqual(entry.severity, "INFO")

    def test_immutable_no_update(self):
        """BorgAuditEntry cannot be updated after creation."""
        entry = BorgAuditEntry(
            company=self.company,
            entry_type="FISCAL",
            summary="Original summary",
        )
        entry.save()

        entry.summary = "Modified summary"
        with self.assertRaises(PermissionError):
            entry.save()

    def test_immutable_no_delete(self):
        """BorgAuditEntry cannot be deleted."""
        entry = BorgAuditEntry(
            company=self.company,
            entry_type="INVOICE",
            summary="Test invoice audit",
        )
        entry.save()

        with self.assertRaises(PermissionError):
            entry.delete()

    def test_all_entry_types_valid(self):
        """All ENTRY_TYPES choices are accepted."""
        for code, label in BorgAuditEntry.ENTRY_TYPES:
            entry = BorgAuditEntry(
                company=self.company,
                entry_type=code,
                summary=f"Test {label}",
            )
            entry.save()
            self.assertEqual(entry.entry_type, code)

    def test_severity_choices(self):
        """All severity levels work."""
        for code, label in BorgAuditEntry.SEVERITY_CHOICES:
            entry = BorgAuditEntry(
                company=self.company,
                entry_type="FISCAL",
                severity=code,
                summary=f"Test {label}",
            )
            entry.save()
            self.assertEqual(entry.severity, code)

    def test_generic_fk_with_borg_task(self):
        """Generic FK links to any model (BorgTask as example)."""
        task = BorgTask.objects.create(
            company=self.company,
            task_type="anomaly",
            title="Test task",
        )
        ct = ContentType.objects.get_for_model(BorgTask)
        entry = BorgAuditEntry(
            company=self.company,
            entry_type="FISCAL",
            summary="Audit linked to task",
            content_type=ct,
            object_id=task.pk,
        )
        entry.save()
        self.assertEqual(entry.content_type, ct)
        self.assertEqual(entry.object_id, task.pk)

    def test_metadata_and_verification(self):
        """JSON fields store structured data correctly."""
        entry = BorgAuditEntry(
            company=self.company,
            entry_type="VIES_CHECK",
            summary="VIES check test",
            verification_type="VIES",
            verification_result={"vies_valid": True, "vies_name": "Test GmbH"},
            metadata={"batch_id": 42, "source": "automated"},
        )
        entry.save()

        refreshed = BorgAuditEntry.objects.get(pk=entry.pk)
        self.assertTrue(refreshed.verification_result["vies_valid"])
        self.assertEqual(refreshed.metadata["batch_id"], 42)

    def test_str_representation(self):
        """__str__ returns readable format."""
        entry = BorgAuditEntry(
            company=self.company,
            entry_type="FISCAL",
            severity="WARNING",
            summary="Fiskalizacija timeout",
        )
        entry.save()
        self.assertIn("WARNING", str(entry))
        self.assertIn("Fiskalizacija", str(entry))

    def test_ordering_newest_first(self):
        """Entries are ordered newest first."""
        e1 = BorgAuditEntry.objects.create(company=self.company, entry_type="FISCAL", summary="First")
        e2 = BorgAuditEntry.objects.create(company=self.company, entry_type="FISCAL", summary="Second")
        entries = list(BorgAuditEntry.objects.filter(company=self.company))
        self.assertEqual(entries[0].pk, e2.pk)

    def test_filter_by_company(self):
        """Entries are filterable by company (tenant isolation)."""
        from companies.models import Company

        other = Company.objects.create(name="Other Firma", oib="99988877766")
        BorgAuditEntry.objects.create(company=self.company, entry_type="FISCAL", summary="Mine")
        BorgAuditEntry.objects.create(company=other, entry_type="FISCAL", summary="Theirs")
        mine = BorgAuditEntry.objects.filter(company=self.company)
        self.assertEqual(mine.count(), 1)
        self.assertEqual(mine.first().summary, "Mine")


class LogBorgAuditHelperTest(TestCase):
    """Test the log_borg_audit helper function."""

    def setUp(self):
        from companies.models import Company

        self.company = Company.objects.create(name="Helper Test d.o.o.", oib="98765432101")

    def test_basic_helper_call(self):
        """log_borg_audit creates entry with correct fields."""
        entry = log_borg_audit(
            company=self.company,
            entry_type="ERACUN",
            summary="e-Racun poslan uspjesno",
            severity="INFO",
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.entry_type, "ERACUN")
        self.assertEqual(entry.company, self.company)

    def test_helper_with_document(self):
        """log_borg_audit links generic FK to document."""
        task = BorgTask.objects.create(
            company=self.company,
            task_type="manual",
            title="Linked task",
        )
        entry = log_borg_audit(
            company=self.company,
            entry_type="FISCAL",
            summary="With document link",
            document=task,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.object_id, task.pk)
        self.assertIsNotNone(entry.content_type)

    def test_helper_returns_none_on_error(self):
        """log_borg_audit returns None on invalid input, does not crash."""
        result = log_borg_audit(
            company=None,
            entry_type="FISCAL",
            summary="Should fail gracefully",
        )
        self.assertIsNone(result)


class BorgBriefingConfigTest(TestCase):
    """Test BorgBriefingConfig model."""

    def setUp(self):
        from companies.models import Company

        self.company = Company.objects.create(name="Briefing Test", oib="11122233344")

    def test_create_config(self):
        """BorgBriefingConfig can be created."""
        config = BorgBriefingConfig.objects.create(
            company=self.company,
            enabled=True,
            phone_number="385991234567",
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.max_items, 5)

    def test_default_values(self):
        """Default values are correct."""
        config = BorgBriefingConfig.objects.create(
            company=self.company,
            phone_number="385991234567",
        )
        self.assertFalse(config.enabled)  # Opt-in: default OFF
        self.assertTrue(config.include_financial)
        self.assertTrue(config.include_compliance)
        self.assertTrue(config.include_operational)
