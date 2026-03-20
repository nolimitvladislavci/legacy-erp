"""Tests for core.exceptions — custom exception hierarchy."""
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from core.exceptions import (
    BookingConflictError,
    BusinessError,
    CompanyIsolationError,
    FiscalizationError,
    InvoiceError,
    NotFoundError,
    PaymentError,
    PermissionDeniedError,
    SessionError,
    ValidationError,
    WorkOrderError,
)


class TestExceptionHierarchy(TestCase):
    """Verify exception inheritance chain."""

    def test_all_inherit_from_business_error(self):
        for exc_class in [InvoiceError, PaymentError, FiscalizationError,
                          BookingConflictError, SessionError, WorkOrderError,
                          ValidationError]:
            self.assertTrue(issubclass(exc_class, BusinessError))

    def test_permission_denied_inherits(self):
        self.assertTrue(issubclass(PermissionDeniedError, BusinessError))
        self.assertTrue(issubclass(CompanyIsolationError, PermissionDeniedError))

    def test_status_codes(self):
        self.assertEqual(BusinessError.status_code, 400)
        self.assertEqual(PermissionDeniedError.status_code, 403)
        self.assertEqual(NotFoundError.status_code, 404)

    def test_exception_message(self):
        e = InvoiceError("Račun nema stavki.")
        self.assertEqual(str(e), "Račun nema stavki.")
        self.assertEqual(e.message, "Račun nema stavki.")

    def test_exception_code(self):
        e = CompanyIsolationError("Cross-company access")
        self.assertEqual(e.code, "ISOLATION_VIOLATION")

    def test_raise_and_catch(self):
        with self.assertRaises(BusinessError):
            raise PaymentError("Test payment error")

    def test_raise_and_catch_specific(self):
        with self.assertRaises(PaymentError):
            raise PaymentError("Specific")

        # Should NOT catch unrelated exception type
        with self.assertRaises(SessionError):
            raise SessionError("Wrong type")


class TestBusinessErrorMiddleware(TestCase):
    """Test the middleware catches BusinessError and redirects."""

    def setUp(self):
        self.factory = RequestFactory()

    def _get_request(self, path="/"):
        request = self.factory.get(path)
        request.user = User(pk=1, username="test")
        # Add session
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        # Add messages
        setattr(request, '_messages', FallbackStorage(request))
        return request

    def test_non_business_error_passthrough(self):
        from core.middleware import BusinessErrorMiddleware
        mw = BusinessErrorMiddleware(lambda r: None)
        request = self._get_request()
        result = mw.process_exception(request, ValueError("not business"))
        self.assertIsNone(result)  # Should pass through

    def test_business_error_caught(self):
        from core.middleware import BusinessErrorMiddleware
        mw = BusinessErrorMiddleware(lambda r: None)
        request = self._get_request("/invoicing/")
        request.META["HTTP_REFERER"] = "/invoicing/"
        result = mw.process_exception(request, InvoiceError("Nema stavki"))
        self.assertIsNotNone(result)  # Should redirect
        self.assertEqual(result.status_code, 302)
