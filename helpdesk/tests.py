"""Tests for Helpdesk module."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from companies.models import Company
from helpdesk.models import Ticket, TicketMessage

User = get_user_model()


class TicketTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Help Co", oib="77777777777")
        self.user = User.objects.create_user(username="helper", password="test123")

    def test_ticket_creation(self):
        ticket = Ticket.objects.create(
            company=self.company,
            created_by=self.user,
            subject="Test problem",
            description="Something is broken",
        )
        self.assertEqual(ticket.subject, "Test problem")
        self.assertIn("Test problem", str(ticket))

    def test_ticket_default_status(self):
        ticket = Ticket.objects.create(
            company=self.company,
            created_by=self.user,
            subject="New ticket",
        )
        self.assertEqual(ticket.status, "open")

    def test_ticket_message(self):
        ticket = Ticket.objects.create(
            company=self.company,
            created_by=self.user,
            subject="Msg test",
        )
        msg = TicketMessage.objects.create(
            ticket=ticket,
            sender=self.user,
            body="This is a reply",
        )
        self.assertEqual(msg.ticket, ticket)
        self.assertEqual(ticket.messages.count(), 1)
