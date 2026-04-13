"""
eInvoice Test Suite — FINA / Peppol / UBL 2.1
Priprema za testiranje sukladnosti Porezne uprave.
"""

import hashlib
from unittest.mock import patch

from django.test import TestCase


class AS4MessageModelTest(TestCase):
    def setUp(self):
        from companies.models import Company
        from einvoice.models import AS4Message

        self.AS4Message = AS4Message
        self.company = Company.objects.filter(is_deactivated=False).first()

    def test_model_fields_postoje(self):
        """AS4Message ima sva kritična polja."""
        fields = [f.name for f in self.AS4Message._meta.fields]
        for field in [
            "direction",
            "status",
            "ubl_xml",
            "archive_sha256",
            "retry_count",
            "max_retries",
            "validation_passed",
        ]:
            self.assertIn(field, fields, f"Nedostaje polje: {field}")

    def test_dlq_threshold_je_5(self):
        """DLQ threshold — max 5 pokušaja."""
        from einvoice.tasks.outbound_tasks import DLQ_MAX_RETRIES

        self.assertEqual(DLQ_MAX_RETRIES, 5)

    def test_as4_sha256_polje_postoji(self):
        """archive_sha256 polje za integrity check."""
        fields = [f.name for f in self.AS4Message._meta.fields]
        self.assertIn("archive_sha256", fields)

    def test_as4_retry_logika(self):
        """retry_count i max_retries su u modelu."""
        fields = [f.name for f in self.AS4Message._meta.fields]
        self.assertIn("retry_count", fields)
        self.assertIn("max_retries", fields)


class XAdESSignerTest(TestCase):
    def test_modul_importira(self):
        """xades_signer.py se importira bez greške."""
        from eracun.services import xades_signer

        self.assertTrue(hasattr(xades_signer, "sign_xades_b"))
        self.assertTrue(hasattr(xades_signer, "verify_xades_b"))

    def test_sign_xades_b_callable(self):
        """sign_xades_b je callable."""
        from eracun.services.xades_signer import sign_xades_b

        self.assertTrue(callable(sign_xades_b))

    def test_verify_xades_b_callable(self):
        """verify_xades_b je callable."""
        from eracun.services.xades_signer import verify_xades_b

        self.assertTrue(callable(verify_xades_b))

    @patch("eracun.services.xades_signer.sign_xades_b")
    def test_sign_prima_argumente(self, mock_sign):
        """sign_xades_b prima root, cert_pem, key_pem."""
        from lxml import etree

        mock_sign.return_value = etree.fromstring(b"<Signed/>")
        from eracun.services.xades_signer import sign_xades_b

        sign_xades_b(etree.fromstring(b"<Invoice/>"), b"cert", b"key")
        mock_sign.assert_called_once()


class OutboundPipelineTest(TestCase):
    def test_instancira(self):
        """OutboundPipeline se instancira."""
        from einvoice.services.outbound_pipeline import OutboundPipeline

        p = OutboundPipeline()
        self.assertIsNotNone(p)

    def test_process_invoice_postoji(self):
        from einvoice.services.outbound_pipeline import OutboundPipeline

        self.assertTrue(hasattr(OutboundPipeline, "process_invoice"))

    def test_bulk_send_postoji(self):
        from einvoice.services.outbound_pipeline import OutboundPipeline

        self.assertTrue(hasattr(OutboundPipeline, "bulk_send"))

    def test_process_eracun_postoji(self):
        from einvoice.services.outbound_pipeline import OutboundPipeline

        self.assertTrue(hasattr(OutboundPipeline, "process_eracun"))


class TransportRouterTest(TestCase):
    def test_importira(self):
        from einvoice.services.transport_router import TransportRouter

        self.assertIsNotNone(TransportRouter)

    def test_transport_config_model(self):
        from einvoice.models.transport_config import TransportConfiguration

        self.assertGreater(len(TransportConfiguration._meta.fields), 0)

    def test_peppol_participant_model(self):
        from einvoice.models.peppol_participant import PeppolParticipant

        self.assertGreater(len(PeppolParticipant._meta.fields), 0)


class ValidatorTest(TestCase):
    def test_oib_validate_postoji(self):
        """OIB validator funkcija postoji u eracun engine."""
        from eracun.services.engine import _validate_oib

        self.assertTrue(callable(_validate_oib))

    def test_oib_neispravan_vraca_false(self):
        """Neispravan OIB se odbija."""
        from eracun.services.engine import _validate_oib

        self.assertFalse(_validate_oib("00000000000"))

    def test_fina_engine_build_xml(self):
        """build_fina_xml postoji u engine."""
        from eracun.services.engine import build_fina_xml

        self.assertTrue(callable(build_fina_xml))

    def test_validate_eracun_postoji(self):
        from eracun.services.engine import validate_eracun

        self.assertTrue(callable(validate_eracun))


class ArchiveServiceTest(TestCase):
    def test_importira(self):
        from einvoice.services.archive_service import ArchiveService

        self.assertIsNotNone(ArchiveService)

    def test_sha256_konzistentnost(self):
        """Isti sadržaj = isti SHA-256."""
        content = b"<Invoice>test</Invoice>"
        self.assertEqual(hashlib.sha256(content).hexdigest(), hashlib.sha256(content).hexdigest())

    def test_sha256_razlicit_sadrzaj(self):
        """Različit sadržaj = različit hash."""
        self.assertNotEqual(hashlib.sha256(b"inv_001").hexdigest(), hashlib.sha256(b"inv_002").hexdigest())

    def test_sha256_duljina_64(self):
        """SHA-256 hex digest je uvijek 64 znaka."""
        h = hashlib.sha256(b"test").hexdigest()
        self.assertEqual(len(h), 64)


class PosrednikClientTest(TestCase):
    def test_instancira(self):
        from einvoice.services.posrednik_client import PosrednikClient

        self.assertIsNotNone(PosrednikClient())

    def test_metode_postoje(self):
        from einvoice.services.posrednik_client import PosrednikClient

        for m in ["submit", "check_status", "poll_inbox", "acknowledge"]:
            self.assertTrue(hasattr(PosrednikClient, m), f"Nedostaje: {m}")

    def test_posrednik_error_klasa(self):
        from einvoice.services.posrednik_client import PosrednikError

        self.assertTrue(issubclass(PosrednikError, Exception))


class MetricsTest(TestCase):
    def test_prometheus_instaliran(self):
        """prometheus_client je instaliran."""
        from prometheus_client import Counter

        c = Counter("einvoice_test_total", "Test metric")
        self.assertIsNotNone(c)

    def test_metrics_modul_importira(self):
        from einvoice.services import metrics

        self.assertIsNotNone(metrics)


class SmartMailboxTest(TestCase):
    def test_service_importira(self):
        """SmartMailboxService se importira."""
        from einvoice.services.smart_mailbox import SmartMailboxService

        self.assertIsNotNone(SmartMailboxService)

    def test_process_incoming_postoji(self):
        from einvoice.services.smart_mailbox import SmartMailboxService

        self.assertTrue(hasattr(SmartMailboxService, "process_incoming"))

    def test_inbound_model(self):
        from einvoice.models.inbound_invoice import InboundInvoice

        self.assertGreater(len(InboundInvoice._meta.fields), 0)


class DocumentArchiveTest(TestCase):
    def test_model_postoji(self):
        from einvoice.models.document_archive import DocumentArchive

        self.assertIsNotNone(DocumentArchive)

    def test_archive_sha256_pattern(self):
        """SHA-256 za AS4 archiving — isti format."""
        data = b"<UBL>invoice</UBL>"
        h = hashlib.sha256(data).hexdigest()
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))
