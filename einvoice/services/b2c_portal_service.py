"""B2C Portal Service — email + web viewer for non-Peppol recipients."""
import logging
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger("propter.einvoice.b2c")


class B2CPortalService:
    """Stub for B2C portal (Phase 2)."""
    def submit(self, message):
        raise NotImplementedError("B2C portal not yet deployed (Phase 2)")
