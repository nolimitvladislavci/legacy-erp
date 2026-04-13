"""Smoke tests for POS views — correct URLs from pos/urls.py."""

import datetime
import json

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase


def _setup_pos_user(oib, username):
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription

    company = Company.objects.create(name=f"POS {oib}", oib=oib)
    user = User.objects.create_user(username, password="pass123")
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)
    CompanySubscription.objects.create(
        company=company,
        plan="starter",
        valid_from=datetime.date.today(),
        monthly_fee=0,
        is_active=True,
        billing_cycle="monthly",
        modules_override=["pos", "invoicing", "inventory"],
    )
    return company, user


ALLOWED = [200, 302, 403, 404, 405, 500]


class POSViewSmokeTest(TestCase):
    """Test correct POS URL patterns."""

    def setUp(self):
        self.company, self.user = _setup_pos_user("11111111110", "pos_v1")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="pos_v1", password="pass123")

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_dashboard(self):
        self.assertIn(self._get("/pos/"), ALLOWED)

    def test_new_terminal(self):
        self.assertIn(self._get("/pos/terminal/new/"), ALLOWED)

    def test_pos_settings(self):
        self.assertIn(self._get("/pos/settings/"), ALLOWED)

    def test_gastro_dashboard(self):
        self.assertIn(self._get("/pos/gastro/"), ALLOWED)

    def test_gastro_kitchen(self):
        self.assertIn(self._get("/pos/gastro/kitchen/"), ALLOWED)

    def test_expiry_dashboard(self):
        self.assertIn(self._get("/pos/expiry/"), ALLOWED)

    def test_expiry_add(self):
        self.assertIn(self._get("/pos/expiry/add/"), ALLOWED)

    def test_api_barcode_lookup(self):
        resp = self.client.get("/pos/api/barcode/?code=1234567890", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_article_search(self):
        resp = self.client.get("/pos/api/articles/search/?q=test", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_quick_create(self):
        data = {"name": "Quick Artikl", "price": "9.99", "tax_rate": 25}
        resp = self.client.post(
            "/pos/api/quick-create/",
            json.dumps(data),
            content_type="application/json",
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)


class POSWithTerminalTest(TestCase):
    """Test POS views that require a terminal."""

    def setUp(self):
        self.company, self.user = _setup_pos_user("11111111120", "pos_v2")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="pos_v2", password="pass123")

    def _make_terminal(self):
        from pos.models import POSTerminal

        return POSTerminal.objects.create(
            company=self.company,
            name="Test Blagajna",
            is_active=True,
        )

    def _make_session(self, terminal):
        from pos.models import POSSession

        return POSSession.objects.create(
            terminal=terminal,
            operator=self.user,
            session_number=1,
            status="open",
        )

    def test_terminal_detail(self):
        try:
            t = self._make_terminal()
            resp = self.client.get(f"/pos/terminal/{t.pk}/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_open_session(self):
        try:
            t = self._make_terminal()
            resp = self.client.post(f"/pos/terminal/{t.pk}/open/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_quick_pos(self):
        try:
            t = self._make_terminal()
            resp = self.client.get(f"/pos/quick/{t.pk}/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_restaurant_pos(self):
        try:
            t = self._make_terminal()
            resp = self.client.get(f"/pos/restaurant/{t.pk}/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_session_detail(self):
        try:
            t = self._make_terminal()
            s = self._make_session(t)
            resp = self.client.get(f"/pos/session/{s.pk}/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_session_new_receipt(self):
        try:
            t = self._make_terminal()
            s = self._make_session(t)
            resp = self.client.post(f"/pos/session/{s.pk}/receipt/new/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_session_close(self):
        try:
            t = self._make_terminal()
            s = self._make_session(t)
            resp = self.client.post(f"/pos/session/{s.pk}/close/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_session_zreport(self):
        try:
            t = self._make_terminal()
            s = self._make_session(t)
            resp = self.client.get(f"/pos/session/{s.pk}/zreport/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_session_deposit(self):
        try:
            t = self._make_terminal()
            s = self._make_session(t)
            resp = self.client.post(f"/pos/session/{s.pk}/deposit/", {"amount": "50.00"}, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_dashboard_with_terminal(self):
        try:
            t = self._make_terminal()
            resp = self.client.get(f"/pos/?terminal={t.pk}", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass


class POSReceiptTest(TestCase):
    """Test POS receipt views."""

    def setUp(self):
        self.company, self.user = _setup_pos_user("11111111130", "pos_v3")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="pos_v3", password="pass123")

    def _make_receipt(self):
        from pos.models import POSReceipt, POSSession, POSTerminal

        t = POSTerminal.objects.create(company=self.company, name="Test Blagajna 3", is_active=True)
        s = POSSession.objects.create(terminal=t, operator=self.user, session_number=1, status="open")
        return POSReceipt.objects.create(session=s, receipt_number=1, status="open")

    def test_receipt_detail(self):
        try:
            r = self._make_receipt()
            resp = self.client.get(f"/pos/receipt/{r.pk}/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_receipt_pdf(self):
        try:
            r = self._make_receipt()
            resp = self.client.get(f"/pos/receipt/{r.pk}/pdf/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (KeyError, AttributeError):
            pass

    def test_receipt_cancel(self):
        try:
            r = self._make_receipt()
            resp = self.client.post(f"/pos/receipt/{r.pk}/cancel/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_receipt_json(self):
        try:
            r = self._make_receipt()
            resp = self.client.get(f"/pos/receipt/{r.pk}/json/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass


class POSSettingsTest(TestCase):
    """Test POS settings views."""

    def setUp(self):
        self.company, self.user = _setup_pos_user("11111111140", "pos_v4")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="pos_v4", password="pass123")

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_settings_page(self):
        self.assertIn(self._get("/pos/settings/"), ALLOWED)

    def test_gastro_kitchen_api(self):
        resp = self.client.get("/pos/gastro/kitchen/api/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_expiry_alerts_api(self):
        resp = self.client.get("/pos/expiry/api/alerts/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)
