"""FINA Posrednik Integration — Phase 1 transport backend."""

import logging

import httpx
from django.conf import settings

from einvoice.models import MessageStatus

logger = logging.getLogger("propter.einvoice.posrednik")


class PosrednikClient:
    """FINA Intermediary REST API Client."""

    def __init__(self):
        self.base_url = getattr(settings, "FINA_POSREDNIK_BASE_URL", "https://api.einvoice.hr/v1")
        self.api_key = getattr(settings, "FINA_POSREDNIK_API_KEY", "")
        self.sandbox = getattr(settings, "FINA_POSREDNIK_SANDBOX", True)
        self._client = None

    def _get_client(self):
        if self._client is None or self._client.is_closed:
            cert_path = getattr(settings, "FINA_POSREDNIK_CLIENT_CERT", "")
            key_path = getattr(settings, "FINA_POSREDNIK_CLIENT_KEY", "")
            cert = (cert_path, key_path) if cert_path else None

            self._client = httpx.Client(
                base_url=self.base_url,
                headers={
                    "Content-Type": "application/xml",
                    "Accept": "application/json",
                    "X-API-Key": self.api_key,
                },
                cert=cert,
                timeout=httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=10.0),
                follow_redirects=True,
            )
        return self._client

    def submit(self, message):
        """Submit outbound invoice to FINA posrednik. Returns external message ID."""
        client = self._get_client()
        payload = {
            "senderParticipantId": message.sender_participant_id,
            "receiverParticipantId": message.receiver_participant_id,
            "documentType": self._map_document_type(message.document_type),
            "processId": "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0",
        }

        try:
            content = message.ubl_xml.encode("utf-8") if isinstance(message.ubl_xml, str) else message.ubl_xml
            response = client.post("/invoices", content=content, params=payload)
            response.raise_for_status()
            result = response.json()
            external_id = result.get("messageId", result.get("id", ""))

            logger.info(f"Invoice submitted: {message.invoice_number} -> {external_id}")
            message.external_message_id = external_id
            message.transition_to(MessageStatus.SUBMITTED, detail=f"Predano FINA posredniku: {external_id}")
            return external_id

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"Posrednik submission failed: {e.response.status_code} - {error_body}")
            message.transition_to(
                MessageStatus.SEND_FAILED, detail=f"HTTP {e.response.status_code}: {error_body[:500]}"
            )
            raise PosrednikError("SUBMISSION_FAILED", f"HTTP {e.response.status_code}: {error_body[:200]}")

        except httpx.RequestError as e:
            logger.error(f"Posrednik connection error: {e}")
            message.transition_to(MessageStatus.SEND_FAILED, detail=f"Greska povezivanja: {str(e)[:500]}")
            raise PosrednikError("CONNECTION_ERROR", f"Ne mogu se spojiti na posrednika: {e}")

    def check_status(self, external_id):
        client = self._get_client()
        try:
            response = client.get(f"/invoices/{external_id}")
            response.raise_for_status()
            result = response.json()
            posrednik_status = result.get("status", "UNKNOWN")
            return {
                "status": self._map_status(posrednik_status),
                "raw_status": posrednik_status,
                "delivered_at": result.get("deliveredAt"),
                "error": result.get("errorMessage"),
                "details": result,
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"status": "NOT_FOUND", "error": f"Poruka {external_id} nije pronadena"}
            raise PosrednikError("STATUS_CHECK_FAILED", f"HTTP {e.response.status_code}")

    def poll_inbox(self, participant_id):
        client = self._get_client()
        try:
            response = client.get("/inbox", params={"participantId": participant_id, "status": "PENDING"})
            response.raise_for_status()
            result = response.json()
            messages = result.get("messages", result.get("items", []))
            logger.info(f"Inbox poll: {len(messages)} pending for {participant_id}")
            return messages
        except httpx.HTTPStatusError as e:
            raise PosrednikError("INBOX_POLL_FAILED", f"HTTP {e.response.status_code}")

    def download(self, external_id):
        client = self._get_client()
        try:
            response = client.get(f"/inbox/{external_id}/content", headers={"Accept": "application/xml"})
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            raise PosrednikError("DOWNLOAD_FAILED", f"Cannot download {external_id}: HTTP {e.response.status_code}")

    def acknowledge(self, external_id):
        client = self._get_client()
        try:
            response = client.post(f"/inbox/{external_id}/ack")
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError:
            return False

    def _map_document_type(self, doc_type):
        mapping = {
            "INVOICE": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice##urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1",
            "CREDIT_NOTE": "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2::CreditNote##urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1",
        }
        return mapping.get(doc_type, mapping["INVOICE"])

    def _map_status(self, posrednik_status):
        mapping = {
            "PENDING": MessageStatus.SUBMITTED,
            "PROCESSING": MessageStatus.SUBMITTED,
            "QUEUED": MessageStatus.SUBMITTED,
            "SENDING": MessageStatus.SENT,
            "SENT": MessageStatus.SENT,
            "DELIVERED": MessageStatus.DELIVERED,
            "ACKNOWLEDGED": MessageStatus.ACKNOWLEDGED,
            "ACCEPTED": MessageStatus.DELIVERED,
            "REJECTED": MessageStatus.REJECTED,
            "FAILED": MessageStatus.SEND_FAILED,
            "ERROR": MessageStatus.SEND_FAILED,
        }
        return mapping.get(posrednik_status.upper(), MessageStatus.SUBMITTED)

    def close(self):
        if self._client and not self._client.is_closed:
            self._client.close()


class PosrednikError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")
