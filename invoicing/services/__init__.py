from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError

from .confirm import confirm_invoice, lock_invoice
from .entry_point import (
    BaseFiscalHandler,
    DocumentEntry,
    DocumentResult,
    FiscalHandlerRegistry,
    FiscalResult,
    HRCashFiscalHandler,
    NullFiscalHandler,
)
from .events import log_invoice_event
from .fiscalize import fiscalize_invoice, generate_qr, generate_zki
from .invoice_service import (
    VALID_TRANSITIONS,
    bulk_create_invoices,
    calculate_tax,
    can_transition,
    copy_invoice,
    create_invoice,
    generate_invoice_number,
)
from .storno import create_storno
