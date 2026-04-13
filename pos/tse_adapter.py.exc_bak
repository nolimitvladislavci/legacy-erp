"""
Fiskaly Cloud TSE Adapter — KassenSichV §146a AO compliance
=========================================================
Koristi Fiskaly KASSENSICHV API v2 za potpisivanje transakcija.

Dokumentacija: https://developer.fiskaly.com/api/kassensichv/v2

Arhitektura:
  CheckoutService._fiscalize(receipt)
    └─ company.country == 'DE'  → FiskalyTSEAdapter.sign_transaction(receipt)
    └─ company.country == 'HR'  → fiscalize_pos_receipt(receipt)   (FINA CIS)
    └─ company.fiscal_exempt    → bypass (udruge)
"""

import logging
import uuid as uuid_module
from decimal import Decimal

import requests
from django.utils import timezone as tz

logger = logging.getLogger('pos_tse')

# ── Fiskaly API konstante ─────────────────────────────────────────────────────
FISKALY_BASE    = 'https://kassensichv-middleware.fiskaly.com/api/v2'
FISKALY_AUTH    = 'https://identitytoolkit.fiskaly.com/api/v0/auth'
FISKALY_TIMEOUT = 10  # sekunde

# ── DSFinV-K mapiranje metoda plaćanja ────────────────────────────────────────
# Ref: DSFinV-K v2.3 §3.4 — ZAHLUNGSART
PAYMENT_TYPE_MAP = {
    'CASH':    'Bar',
    'CARD':    'Unbar',
    'MOBILE':  'Unbar',
    'VOUCHER': 'Keine',    # Gutschein
    'ACCOUNT': 'Unbar',
    'CRYPTO':  'Unbar',
    'REVOLUT': 'Unbar',
    'AIRCASH': 'Unbar',
}


class TSEError(Exception):
    """TSE API greška — ne blokira naplatu, logira se za retry."""
    pass


class FiskalyTSEAdapter:
    """
    Fiskaly Cloud TSE — potpisivanje POS transakcija za KassenSichV.

    Inicijalizacija:
        adapter = FiskalyTSEAdapter.from_company(company)
        tse_data = adapter.sign_transaction(receipt)

    Vraća dict s TSE podacima koji se spremaju na POSReceipt.
    """

    def __init__(self, api_key: str, api_secret: str, tss_id: str, client_id: str):
        self.api_key    = api_key
        self.api_secret = api_secret
        self.tss_id     = tss_id
        self.client_id  = client_id
        self._token: str | None = None

    @classmethod
    def from_company(cls, company) -> 'FiskalyTSEAdapter':
        """
        Kreira adapter iz Company modela.
        Traži credentials u company.settings['tse'] JSONu.
        """
        tse_cfg = company.settings.get('tse', {}) if hasattr(company, 'settings') else {}

        api_key    = tse_cfg.get('api_key', '')
        api_secret = tse_cfg.get('api_secret', '')
        tss_id     = tse_cfg.get('tss_id', '')
        client_id  = tse_cfg.get('client_id', '')

        if not all([api_key, api_secret, tss_id, client_id]):
            raise TSEError(
                f'Tvrtka {company.name} nema konfigurirane TSE kredencijale. '
                f'Dodajte tse.api_key, tse.api_secret, tse.tss_id, tse.client_id '
                f'u company.settings JSON.'
            )
        return cls(api_key, api_secret, tss_id, client_id)

    # ── Auth ─────────────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        """JWT token — cache po instanci (važeći 1h)."""
        if self._token:
            return self._token
        try:
            resp = requests.post(
                FISKALY_AUTH,
                json={'api_key': self.api_key, 'api_secret': self.api_secret},
                timeout=FISKALY_TIMEOUT,
            )
            resp.raise_for_status()
            self._token = resp.json()['access_token']
            return self._token
        except Exception as e:
            raise TSEError(f'Fiskaly auth failed: {e}') from e

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self._get_token()}',
            'Content-Type': 'application/json',
        }

    # ── TSE API pozivi ────────────────────────────────────────────────────────

    def _start_transaction(self) -> str:
        """Otvara TSE transakciju — vraća tx_id (UUID)."""
        tx_id = str(uuid_module.uuid4())
        url = f'{FISKALY_BASE}/tss/{self.tss_id}/tx/{tx_id}?tx_revision=1'
        try:
            resp = requests.put(
                url,
                json={
                    'state': 'ACTIVE',
                    'client_id': self.client_id,
                },
                headers=self._headers(),
                timeout=FISKALY_TIMEOUT,
            )
            resp.raise_for_status()
            return tx_id
        except Exception as e:
            raise TSEError(f'TSE START_TRANSACTION failed: {e}') from e

    def _finish_transaction(self, tx_id: str, receipt, vat_breakdown: list, payments: list) -> dict:
        """Zatvara TSE transakciju — vraća potpisan rezultat."""
        url = f'{FISKALY_BASE}/tss/{self.tss_id}/tx/{tx_id}?tx_revision=2'
        payload = {
            'state': 'FINISHED',
            'client_id': self.client_id,
            'schema': {
                'standard_v1': {
                    'receipt': {
                        'receipt_type': 'RECEIPT',
                        'amounts_per_vat_rate': vat_breakdown,
                        'amounts_per_payment_type': payments,
                    }
                }
            }
        }
        try:
            resp = requests.put(
                url,
                json=payload,
                headers=self._headers(),
                timeout=FISKALY_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise TSEError(f'TSE FINISH_TRANSACTION failed: {e}') from e

    # ── Pomoćne metode za izgradnju payloada ─────────────────────────────────

    @staticmethod
    def _build_vat_breakdown(receipt) -> list:
        """
        DSFinV-K VAT kategorije:
          NORMAL       = 19%
          REDUCED_1    = 7%
          NULL         = 0%
          SPECIAL_S1   = 13%
          SPECIAL_S2   = 5% (COVID smanjenje, nije više aktualno ali se može pojaviti)

        Mapiraj po tax_rate vrijednosti.
        """
        VAT_MAP = {
            19: 'NORMAL',
            7:  'REDUCED_1',
            0:  'NULL',
            13: 'SPECIAL_S1',
            5:  'SPECIAL_S2',
        }
        breakdown = {}
        for item in receipt.items.all():
            rate = int(item.tax_rate)
            vat_cat = VAT_MAP.get(rate, 'NORMAL')  # fallback na NORMAL
            if vat_cat not in breakdown:
                breakdown[vat_cat] = Decimal('0')
            breakdown[vat_cat] += item.total_price

        return [
            {'vat_rate_percentage': cat, 'amount': str(round(amt, 2))}
            for cat, amt in breakdown.items()
        ]

    @staticmethod
    def _build_payment_breakdown(receipt) -> list:
        """Mapira POSPaymentLine.Method na DSFinV-K ZAHLUNGSART."""
        payments = []
        for line in receipt.payment_lines.all():
            dsfinvk_type = PAYMENT_TYPE_MAP.get(line.method, 'Unbar')
            payments.append({
                'payment_type': dsfinvk_type,
                'amount': str(line.amount),
            })
        return payments if payments else [{'payment_type': 'Bar', 'amount': str(receipt.total)}]

    # ── Glavna metoda ─────────────────────────────────────────────────────────

    def sign_transaction(self, receipt) -> dict:
        """
        Potpiše POS transakciju.

        Vraća dict koji se direktno sprema na POSReceipt:
            tse_transaction_number, tse_signature_counter,
            tse_hash, tse_serial_number, tse_start_time, tse_end_time

        Iznimka TSEError se hvata u CheckoutService i logira
        — naplata se NE blokira (FINA analog).
        """
        vat_breakdown = self._build_vat_breakdown(receipt)
        payments      = self._build_payment_breakdown(receipt)

        tx_id  = self._start_transaction()
        result = self._finish_transaction(tx_id, receipt, vat_breakdown, payments)

        sig = result.get('signature', {})
        tss = result.get('tss', {})

        return {
            'tse_transaction_number': str(result.get('number', '')),
            'tse_signature_counter':  sig.get('counter'),
            'tse_hash':               sig.get('value', ''),
            'tse_serial_number':      tss.get('serial_number', ''),
            'tse_start_time':         result.get('time_start'),
            'tse_end_time':           result.get('time_end'),
        }
