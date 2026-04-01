"""
ai_assistant/tests.py — Tests for AI assistant module.

3 klase, 11 test metoda:
  1. ClaudeClientTest      (3 methods) — model config, cost estimate
  2. ConversationModelTest  (3 methods) — model, message persistence
  3. ChatAPITest            (5 methods) — API endpoint, auth, tool dispatch

Run:
    python manage.py test ai_assistant --verbosity=2
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse

User = get_user_model()

NO_HTTPS = override_settings(
    SECURE_SSL_REDIRECT=False,
    MIDDLEWARE=[
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.locale.LocaleMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
    ],
)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def make_company(oib="77766655543"):
    from companies.models import Company
    return Company.objects.get_or_create(
        oib=oib,
        defaults=dict(name="AI Test GmbH", country="DE", has_signed_tc_consent=True,
                      city="Berlin", zip_code="10115"),
    )[0]


def make_user(company, username="ai_user"):
    from accounts.models import UserProfile
    user = User.objects.create_user(
        username=username,
        email=f"{username}@ai-test.de",
        password="TestPass2026!",
    )
    UserProfile.objects.create(user=user, company=company, role="company_admin", totp_enabled=True)
    return user


def make_subscription(company):
    from registration.models import CompanySubscription
    from django.utils import timezone
    return CompanySubscription.objects.create(
        company=company,
        plan="enterprise",
        valid_from=timezone.now().date(),
        monthly_fee=0,
        is_active=True,
        modules_override=["ai_assistant"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1 — Claude client config and cost estimation
# ══════════════════════════════════════════════════════════════════════════════

class ClaudeClientTest(TestCase):
    """Tests for claude_client.py configuration."""

    def test_model_is_current(self):
        """MODEL should be the current claude-haiku-4-5-20251001."""
        from ai_assistant.claude_client import MODEL
        self.assertEqual(MODEL, "claude-haiku-4-5-20251001")

    def test_estimate_cost_zero_tokens(self):
        """Zero tokens → zero cost."""
        from ai_assistant.claude_client import estimate_cost
        self.assertEqual(estimate_cost(0, 0), 0.0)

    def test_estimate_cost_formula(self):
        """1M input + 1M output tokens → $0.80 + $4.00 = $4.80."""
        from ai_assistant.claude_client import estimate_cost
        cost = estimate_cost(1_000_000, 1_000_000)
        self.assertAlmostEqual(cost, 4.80, places=2)

    def test_estimate_cost_small_conversation(self):
        """Typical 500 input + 200 output tokens → small positive cost."""
        from ai_assistant.claude_client import estimate_cost
        cost = estimate_cost(500, 200)
        self.assertGreater(cost, 0)
        self.assertLess(cost, 0.01)  # under 1 cent


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Conversation and Message models
# ══════════════════════════════════════════════════════════════════════════════

class ConversationModelTest(TestCase):
    """Tests for Conversation and Message models."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)

    def test_create_conversation(self):
        """Can create a Conversation for a user."""
        from ai_assistant.models import Conversation
        conv = Conversation.objects.create(
            user=self.user,
            title="Test razgovor",
        )
        self.assertEqual(conv.user, self.user)
        self.assertTrue(conv.is_active)

    def test_create_messages(self):
        """User + assistant messages saved and ordered by created_at."""
        from ai_assistant.models import Conversation, Message
        conv = Conversation.objects.create(user=self.user, title="Test")
        Message.objects.create(conversation=conv, role="user", content="Zdravo!")
        Message.objects.create(conversation=conv, role="assistant", content="Bok!")
        msgs = list(conv.messages.all())
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0].role, "user")
        self.assertEqual(msgs[1].role, "assistant")

    def test_usage_log_cost_estimate(self):
        """AIUsageLog stores non-zero cost_estimate after a real call."""
        from ai_assistant.models import Conversation, AIUsageLog
        from ai_assistant.claude_client import estimate_cost
        conv = Conversation.objects.create(user=self.user, title="Cost test")
        cost = estimate_cost(1000, 300)
        log = AIUsageLog.objects.create(
            user=self.user,
            conversation=conv,
            input_tokens=1000,
            output_tokens=300,
            cost_estimate=cost,
        )
        log.refresh_from_db()
        self.assertGreater(float(log.cost_estimate), 0)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3 — Chat API endpoint
# ══════════════════════════════════════════════════════════════════════════════

@NO_HTTPS
class ChatAPITest(TestCase):
    """Tests for the /ai/api/chat/ endpoint."""

    def setUp(self):
        self.company = make_company(oib="77766655544")
        make_subscription(self.company)
        self.user = make_user(self.company, username="chat_user")
        self.c = Client()
        self.c.login(username="chat_user", password="TestPass2026!")
        self.url = reverse('ai_assistant:chat_api')

    def _mock_claude_response(self, content="Testni odgovor"):
        """Return a mock that makes chat_with_claude return a simple text response."""
        return patch(
            "ai_assistant.views.chat_with_claude",
            return_value={
                "content": content,
                "tool_calls": [],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 50, "output_tokens": 20},
            },
        )

    def _mock_all(self, content="Testni odgovor"):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(self._mock_claude_response(content))
        stack.enter_context(patch("ai_assistant.views._build_contextual_system_prompt", return_value="Test"))
        stack.enter_context(patch("ai_assistant.views._get_rag_context", return_value=""))
        return stack

    def test_chat_requires_login(self):
        """Unauthenticated POST → redirect to login."""
        anon = Client()
        r = anon.post(self.url, data='{"message":"test"}',
                      content_type="application/json")
        self.assertIn(r.status_code, (302, 401))

    def test_empty_message_rejected(self):
        """Empty message → 400."""
        r = self.c.post(self.url, data='{"message":"  "}',
                        content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_chat_returns_response(self):
        """Valid message → 200 with content and conversation_id."""
        with self._mock_all("Ja sam vaš AI asistent."):
            r = self.c.post(self.url,
                            data='{"message":"Tko si ti?"}',
                            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("content", d)
        self.assertIn("conversation_id", d)
        self.assertEqual(d["content"], "Ja sam vaš AI asistent.")

    def test_conversation_persisted(self):
        """After a chat call, Conversation + 2 Messages are saved in DB."""
        from ai_assistant.models import Conversation, Message
        with self._mock_all("Bok!"):
            self.c.post(self.url,
                        data='{"message":"Zdravo!"}',
                        content_type="application/json")
        self.assertEqual(Conversation.objects.filter(user=self.user).count(), 1)
        conv = Conversation.objects.filter(user=self.user).first()
        self.assertEqual(conv.messages.count(), 2)  # user + assistant

    def test_usage_log_created(self):
        """Each chat call creates an AIUsageLog record with cost_estimate."""
        from ai_assistant.models import AIUsageLog
        with self._mock_all("Test"):
            self.c.post(self.url,
                        data='{"message":"Koliko je racuna danas?"}',
                        content_type="application/json")
        log = AIUsageLog.objects.filter(user=self.user).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.input_tokens, 50)
        self.assertEqual(log.output_tokens, 20)
        self.assertGreater(float(log.cost_estimate), 0)
