"""OutboundPipeline — end-to-end orchestrator for sending e-invoices.

Flow: Generate UBL → Validate → Route → Submit
Each step creates an audit event on the AS4Message.
"""
import logging

from einvoice.models import AS4Message, MessageDirection, MessageStatus
from einvoice.services.transport_router import TransportRouter
from einvoice.services.ubl_generator import generate_ubl_for_eracun, generate_ubl_for_invoice
from einvoice.services.ubl_validator import validate_ubl

logger = logging.getLogger("propter.einvoice.pipeline")


class OutboundPipeline:
    """Orchestrates the full outbound e-invoice flow."""

    def __init__(self):
        self.router = TransportRouter()

    def process_invoice(self, invoice, user=None, profile="HR", strict=False):
        """
        Full pipeline: Invoice → UBL → Validate → Route → Submit.

        Args:
            invoice: invoicing.Invoice instance
            user: requesting user (for audit)
            profile: CIUS profile (HR, DE, EU)
            strict: strict validation mode

        Returns:
            AS4Message instance (with final status)
        """
        company = invoice.company
        receiver_oib = invoice.client_oib or ""
        sender_oib = company.oib if company else ""

        # Step 1: Check for existing message
        existing = AS4Message.objects.filter(
            invoice=invoice, direction=MessageDirection.OUTBOUND,
        ).exclude(
            status__in=[MessageStatus.CANCELLED, MessageStatus.REJECTED]
        ).first()
        if existing and not existing.is_terminal:
            logger.info(f"Invoice {invoice.number} already has active AS4Message {existing.id}")
            return existing

        # Step 2: Generate UBL XML
        try:
            ubl_xml = generate_ubl_for_invoice(invoice, profile=profile)
        except Exception as e:
            logger.error(f"UBL generation failed for {invoice.number}: {e}")
            if existing:
                existing.transition_to(MessageStatus.VALIDATION_FAILED, detail=f"UBL generiranje: {e}", user=user)
                return existing
            raise

        # Step 3: Route
        decision = self.router.resolve(
            company_id=str(company.id) if company else "",
            sender_oib=sender_oib,
            receiver_oib=receiver_oib,
        )

        # Step 4: Create or update AS4Message
        if existing:
            message = existing
            message.set_ubl_xml(ubl_xml)
            message.save()
        else:
            doc_type = "INVOICE"
            if hasattr(invoice, "doc_type") and invoice.doc_type in ("STORNO", "CREDIT_NOTE"):
                doc_type = "CREDIT_NOTE"

            message = AS4Message(
                company=company,
                invoice=invoice,
                direction=MessageDirection.OUTBOUND,
                transport=decision.transport,
                sender_participant_id=f"9934:{sender_oib}",
                receiver_participant_id=f"9934:{receiver_oib}",
                sender_name=company.name if company else "",
                receiver_name=invoice.client_name or "",
                document_type=doc_type,
                invoice_number=invoice.number,
                invoice_amount=invoice.total,
                invoice_currency=getattr(invoice, "currency", "EUR"),
                status=MessageStatus.DRAFT,
                created_by=user,
                metadata={"routing": {"transport": decision.transport, "reason": decision.reason}},
            )
            message.set_ubl_xml(ubl_xml)
            message.save()
            message.transition_to(MessageStatus.DRAFT, detail="AS4 poruka kreirana", user=user)

        # Step 5: Validate
        validation = validate_ubl(ubl_xml, strict=strict)
        message.validation_passed = validation.is_valid
        message.validation_errors = validation.errors
        message.validation_warnings = validation.warnings
        message.save(update_fields=["validation_passed", "validation_errors", "validation_warnings"])

        if not validation.is_valid:
            message.transition_to(
                MessageStatus.VALIDATION_FAILED,
                detail=f"Validacija neuspjesna: {'; '.join(validation.errors[:3])}",
                user=user,
            )
            logger.warning(f"Validation failed for {invoice.number}: {validation.errors[:3]}")
            return message

        message.transition_to(MessageStatus.VALIDATED, detail=validation.summary, user=user)

        # Step 6: Submit via transport backend
        message.transport = decision.transport
        message.save(update_fields=["transport"])

        backend = self.router.get_backend(decision.transport)
        try:
            external_id = backend.submit(message)
            logger.info(f"Invoice {invoice.number} submitted: {external_id} via {decision.backend_name}")
            return message
        except Exception as e:
            logger.error(f"Submit failed for {invoice.number}: {e}")
            # transition_to is already called inside backend.submit()
            return message

    def process_eracun(self, eracun, user=None, profile="HR", strict=False):
        """Pipeline for existing eracun.ERacun instances."""
        try:
            ubl_xml = generate_ubl_for_eracun(eracun, profile=profile)
        except Exception as e:
            logger.error(f"UBL generation failed for ERacun {eracun.invoice_number}: {e}")
            raise

        company = eracun.company
        sender_oib = eracun.issuer_oib or ""
        receiver_oib = eracun.recipient_oib or ""

        decision = self.router.resolve(
            company_id=str(company.id),
            sender_oib=sender_oib,
            receiver_oib=receiver_oib,
        )

        message = AS4Message(
            company=company,
            direction=MessageDirection.OUTBOUND,
            transport=decision.transport,
            sender_participant_id=f"9934:{sender_oib}",
            receiver_participant_id=f"9934:{receiver_oib}",
            sender_name=eracun.issuer_name or "",
            receiver_name=eracun.recipient_name or "",
            document_type="CREDIT_NOTE" if eracun.doc_type == "381" else "INVOICE",
            invoice_number=eracun.invoice_number,
            invoice_amount=eracun.total,
            invoice_currency=eracun.currency or "EUR",
            status=MessageStatus.DRAFT,
            created_by=user,
        )
        message.set_ubl_xml(ubl_xml)
        message.save()

        validation = validate_ubl(ubl_xml, strict=strict)
        message.validation_passed = validation.is_valid
        message.validation_errors = validation.errors
        message.validation_warnings = validation.warnings
        message.save(update_fields=["validation_passed", "validation_errors", "validation_warnings"])

        if not validation.is_valid:
            message.transition_to(MessageStatus.VALIDATION_FAILED, detail=validation.summary, user=user)
            return message

        message.transition_to(MessageStatus.VALIDATED, detail=validation.summary, user=user)

        backend = self.router.get_backend(decision.transport)
        try:
            backend.submit(message)
        except Exception as e:
            logger.error(f"Submit failed for ERacun {eracun.invoice_number}: {e}")
        return message

    def bulk_send(self, invoices, user=None, profile="HR"):
        """Process multiple invoices. Returns list of (invoice, message, error)."""
        results = []
        for invoice in invoices:
            try:
                message = self.process_invoice(invoice, user=user, profile=profile)
                results.append((invoice, message, None))
            except Exception as e:
                results.append((invoice, None, str(e)))
                logger.error(f"Bulk send error for {invoice.number}: {e}")
        return results
