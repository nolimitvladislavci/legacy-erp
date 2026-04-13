"""phase4 AS4 Gateway Client — Phase 3 stub.
Will be implemented when we deploy our own Peppol AP."""
import logging

logger = logging.getLogger("propter.einvoice.phase4")


class Phase4Client:
    """Stub for future phase4 integration."""
    def submit(self, message):
        raise NotImplementedError("phase4 AP not yet deployed (Phase 3)")

    def check_status(self, external_id):
        raise NotImplementedError("phase4 AP not yet deployed (Phase 3)")

    def poll_inbox(self, participant_id):
        raise NotImplementedError("phase4 AP not yet deployed (Phase 3)")

    def download(self, external_id):
        raise NotImplementedError("phase4 AP not yet deployed (Phase 3)")
