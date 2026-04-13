"""
DE Fiskalisierung - fiskaly Cloud TSE Provider
KassenSichV: REST API via fiskaly Middleware
Base URL: https://kassensichv-middleware.fiskaly.com/api/v2
"""
import uuid
import json
import hashlib
import logging
from datetime import datetime
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from ..base import BaseFiscalProvider, FiscalResult

logger = logging.getLogger(__name__)

FISKALY_BASE = "https://kassensichv-middleware.fiskaly.com/api/v2"
FISKALY_AUTH = "https://kassensichv-middleware.fiskaly.com/api/v2/auth"


class DETseProvider(BaseFiscalProvider):

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
                    error_message='TSE Authentifizierung fehlgeschlagen'
                )

            tx_id = str(uuid.uuid4())
            tss_id = self.config.tse_tss_id
            client_id = self.config.tse_client_id

            start_res = self._api_call(
                'PUT', '/tss/%s/tx/%s' % (tss_id, tx_id),
                {'state': 'ACTIVE', 'client_id': client_id}, token
            )
            if not start_res or start_res.get('state') != 'ACTIVE':
                return FiscalResult(
                    success=False,
                    error_message='TX start failed: %s' % start_res,
                    raw_response=json.dumps(start_res or {})
                )

            receipt_schema = self._build_receipt_schema(receipt_data)
            finish_res = self._api_call(
                'PUT', '/tss/%s/tx/%s' % (tss_id, tx_id),
                {'state': 'FINISHED', 'client_id': client_id, 'schema': receipt_schema},
                token
            )

            if finish_res and finish_res.get('state') == 'FINISHED':
                sig = finish_res.get('signature', {})
                return FiscalResult(
                    success=True,
                    tse_signature=sig.get('value', ''),
                    tse_transaction_number=str(finish_res.get('number', '')),
                    qr_code_data=finish_res.get('qr_code_data', ''),
                    raw_request=json.dumps(receipt_schema),
                    raw_response=json.dumps(finish_res)
                )

            return FiscalResult(
                success=False,
                error_message='TX finish failed: %s' % finish_res,
                raw_response=json.dumps(finish_res or {})
            )

        except (TypeError, ValueError) as e:
            logger.error("TSE error: %s", e)
            return FiscalResult(success=False, error_message=str(e))

    def test_connection(self) -> bool:
        return self._authenticate() is not None

    def echo(self) -> bool:
        return self.test_connection()

    def _authenticate(self):
        try:
            import requests
            r = requests.post(FISKALY_AUTH, json={
                'api_key': self.config.tse_api_key,
                'api_secret': self.config.tse_api_secret,
            }, timeout=10)
            if r.status_code == 200:
                self._token = r.json().get('access_token')
                return self._token
            logger.error("fiskaly auth failed: %d %s", r.status_code, r.text[:200])
            return None
        except requests.RequestException as e:
            logger.error("fiskaly auth error: %s", e)
            return None

    def _api_call(self, method, path, data, token):
        try:
            import requests
            url = FISKALY_BASE + path
            headers = {
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json',
            }
            r = requests.request(method, url, json=data, headers=headers, timeout=15)
            if r.status_code in (200, 201):
                return r.json()
            logger.error("fiskaly %s %s: %d %s", method, path, r.status_code, r.text[:200])
            return None
        except Exception as e:
            logger.error("fiskaly API error: %s", e)
            return None

    @staticmethod
    def _build_receipt_schema(data):
        amounts_per_vat = []
        for tax in data.get('tax_amounts', []):
            if tax['rate'] == 19:
                vat_id = 'NORMAL'
            elif tax['rate'] == 7:
                vat_id = 'REDUCED_1'
            else:
                vat_id = 'NULL'
            amounts_per_vat.append({
                'vat_definition_export_id': vat_id,
                'amount': str(tax.get('base', 0) + tax.get('amount', 0)),
            })

        pm = data.get('payment_method', '').lower()
        payment_type = 'CASH' if pm in ('cash', 'bar', 'gotovina') else 'NON_CASH'

        return {
            'standard_v1': {
                'receipt': {
                    'receipt_type': 'RECEIPT',
                    'amounts_per_vat_rate': amounts_per_vat,
                    'amounts_per_payment_type': [{
                        'payment_type': payment_type,
                        'amount': str(data['total_amount']),
                    }],
                },
            },
        }

    def _mock_fiscalize(self, data):
        mock_sig = hashlib.sha256(
            ("%s%s%s" % (data['receipt_number'], data['total_amount'], datetime.now().isoformat())).encode()
        ).hexdigest()
        return FiscalResult(
            success=True,
            tse_signature=mock_sig,
            tse_transaction_number='TEST-' + uuid.uuid4().hex[:8].upper(),
            raw_request='TEST MODE',
            raw_response='mock signature: ' + mock_sig[:16] + '...',
        )
