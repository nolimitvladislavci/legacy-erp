"""
LIMIT Connect custom exception hierarchy.

Usage:
    from core.exceptions import InvoiceError, PaymentError
    raise InvoiceError("Račun nema stavki.")

These are caught by BusinessErrorMiddleware and shown to users
as friendly messages, while logging the error for debugging.
"""


class BusinessError(Exception):
    """Base for all business logic errors. User-friendly message."""
    status_code: int = 400

    def __init__(self, message: str = "", code: str = ""):
        self.message = message
        self.code = code or getattr(self.__class__, 'code', '')
        super().__init__(message)


class ValidationError(BusinessError):
    """Data validation failed."""
    pass


class PermissionDeniedError(BusinessError):
    """User lacks permission for this action."""
    status_code = 403


class NotFoundError(BusinessError):
    """Requested resource not found."""
    status_code = 404


# ── Module-specific errors ──────────────────────────────────

class InvoiceError(BusinessError):
    """Invoicing module errors."""
    pass


class PaymentError(BusinessError):
    """Payment processing errors."""
    pass


class FiscalizationError(BusinessError):
    """Fiscal registration errors (non-blocking)."""
    pass


class BookingConflictError(BusinessError):
    """Appointment slot already taken."""
    pass


class SessionError(BusinessError):
    """POS session lifecycle errors."""
    pass


class WorkOrderError(BusinessError):
    """Work order processing errors."""
    pass


class CompanyIsolationError(PermissionDeniedError):
    """Cross-company data access attempt."""
    code = "ISOLATION_VIOLATION"
