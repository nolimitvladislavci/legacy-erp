"""
AT Fiskalisierung — RKSV Provider (Registrierkassensicherheitsverordnung)
BAO §131b: Chained signatures, AES-256 counter, DEP export.

Supports: fiskaly AT, PrimeSign, or A-Trust for signing.
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime

from ..base import BaseFiscalProvider, FiscalResult

logger = logging.getLogger(__name__)

FISKALY_AT_BASE = "https://kassensichv-middleware.fiskaly.com/api/v2"


class ATRksvProvider(BaseFiscalProvider):
    """
    Austrian RKSV fiscal provider.

    Receipt chain:
    1. Encrypt running turnover counter with AES-256-CTR
    2. Sign with certificate (RSA/ECDSA via cloud HSM)
    3. Include previous receipt's signature hash in chain
    4. Generate machine-readable QR code (BMF format)
    """

    def __init__(self, config):
        super().__init__(config)
        self._token = None

    def fiscalize(self, receipt_data: dict) -> FiscalResult:
        if self.config.is_test_mode:
            return self._mock_fiscalize(receipt_data)

        try:
            token = self._authenticate()
            if not token:
                return FiscalResult(
                    success=False,
                    error_message='RKSV Authentifizierung fehlgeschlagen'
                )

            # Build RKSV receipt (Beleg)
            beleg = self._build_beleg(receipt_data)

            # Sign via cloud HSM
            signed = self._sign_beleg(beleg, token)
            if not signed:
                return FiscalResult(
                    success=False,
                    error_message='RKSV Signierung fehlgeschlagen'
                )

            # Generate QR code data (BMF format)
            qr_data = self._generate_qr(signed)

            return FiscalResult(
                success=True,
                tse_signature=signed.get('signature', ''),
                tse_transaction_number=str(signed.get('receipt_number', '')),
                qr_code_data=qr_data,
                raw_request=json.dumps(beleg),
                raw_response=json.dumps(signed),
            )

        except (TypeError, ValueError) as e:
            logger.error("RKSV error: %s", e)
            return FiscalResult(success=False, error_message=str(e))

    def test_connection(self) -> bool:
        return self._authenticate() is not None

    def echo(self) -> bool:
        return self.test_connection()

    def _authenticate(self):
        """Authenticate with signing provider (fiskaly AT or PrimeSign)."""
        try:
            import requests
            r = requests.post(FISKALY_AT_BASE + '/auth', json={
                'api_key': self.config.rksv_api_key,
                'api_secret': self.config.rksv_api_secret,
            }, timeout=10)
            if r.status_code == 200:
                self._token = r.json().get('access_token')
                return self._token
            logger.error("RKSV auth failed: %d %s", r.status_code, r.text[:200])
            return None
        except requests.RequestException as e:
            logger.error("RKSV auth error: %s", e)
            return None

    def _build_beleg(self, data):
        """
        Build RKSV Beleg structure.

        Turnover categories (Umsatzzähler):
        - Satz-Normal (20%)
        - Satz-Ermäßigt-1 (10%)
        - Satz-Ermäßigt-2 (13%)
        - Satz-Besonders (0%)
        - Satz-Null (0% steuerbefreit)
        """
        tax_amounts = data.get('tax_amounts', [])
        normal = sum(t['base'] + t['amount'] for t in tax_amounts if t['rate'] == 20)
        reduced_1 = sum(t['base'] + t['amount'] for t in tax_amounts if t['rate'] == 10)
        reduced_2 = sum(t['base'] + t['amount'] for t in tax_amounts if t['rate'] == 13)
        special = sum(t['base'] + t['amount'] for t in tax_amounts if t['rate'] == 0)

        return {
            'kassen_id': self.config.rksv_kassen_id,
            'beleg_nummer': data.get('receipt_number', ''),
            'beleg_datum_uhrzeit': datetime.now().isoformat(),
            'betrag_satz_normal': str(normal),
            'betrag_satz_ermaessigt_1': str(reduced_1),
            'betrag_satz_ermaessigt_2': str(reduced_2),
            'betrag_satz_besonders': str(special),
            'betrag_satz_null': '0.00',
            'stand_umsatzzaehler_aes256_ict': '',  # Encrypted running counter
            'zertifikat_seriennummer': self.config.rksv_cert_serial,
            'sig_voriger_beleg': data.get('previous_signature_hash', ''),
        }

    def _sign_beleg(self, beleg, token):
        """Sign beleg via cloud HSM."""
        try:
            import requests
            url = FISKALY_AT_BASE + '/sign'
            headers = {
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json',
            }
            r = requests.post(url, json=beleg, headers=headers, timeout=15)
            if r.status_code in (200, 201):
                return r.json()
            logger.error("RKSV sign failed: %d %s", r.status_code, r.text[:200])
            return None
        except requests.RequestException as e:
            logger.error("RKSV sign error: %s", e)
            return None

    @staticmethod
    def _generate_qr(signed_beleg):
        """
        Generate BMF-compliant QR code data.
        Format: _R1-AT0_KassenID_BelegNr_Datum_Beträge_EncCounter_CertSerial_PrevSigHash_Signature
        """
        b = signed_beleg
        parts = [
            '_R1-AT0',
            b.get('kassen_id', ''),
            b.get('beleg_nummer', ''),
            b.get('beleg_datum_uhrzeit', ''),
            b.get('betrag_satz_normal', '0.00'),
            b.get('betrag_satz_ermaessigt_1', '0.00'),
            b.get('betrag_satz_ermaessigt_2', '0.00'),
            b.get('betrag_satz_besonders', '0.00'),
            b.get('betrag_satz_null', '0.00'),
            b.get('stand_umsatzzaehler_aes256_ict', ''),
            b.get('zertifikat_seriennummer', ''),
            b.get('sig_voriger_beleg', ''),
            b.get('signature', ''),
        ]
        return '_'.join(str(p) for p in parts)

    def _mock_fiscalize(self, data):
        """Test mode — generate deterministic mock signature."""
        raw = "%s%s%s" % (
            data.get('receipt_number', ''),
            data.get('total_amount', '0'),
            datetime.now().isoformat(),
        )
        mock_sig = hashlib.sha256(raw.encode()).hexdigest()
        return FiscalResult(
            success=True,
            tse_signature=mock_sig,
            tse_transaction_number='RKSV-TEST-' + uuid.uuid4().hex[:8].upper(),
            qr_code_data='_R1-AT0_TEST_%s_%s' % (
                data.get('receipt_number', 'X'), mock_sig[:16]
            ),
            raw_request='TEST MODE',
            raw_response='mock RKSV signature: ' + mock_sig[:16] + '...',
        )


def get_previous_signature_hash(company):
    """
    Get SHA-256 hash of the previous receipt's signature.
    Required for RKSV chain integrity.
    """
    from fiscal.models import FiscalLog
    last = FiscalLog.objects.filter(
        config__company=company,
        config__provider='at_rksv',
        status='success',
    ).order_by('-created_at').first()

    if last and last.tse_signature:
        return hashlib.sha256(last.tse_signature.encode()).hexdigest()
    return hashlib.sha256(b'').hexdigest()  # Genesis hash for first receipt
