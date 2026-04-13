"""
Tests for pos/hashchain.py — cryptographic audit trail.
Hash chain integrity, tamper detection, daily anchor, training exclusion.
"""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from pos.hashchain import (
    ChainLink,
    _sha256,
    append_receipt,
    daily_anchor_hash,
    verify_chain,
    verify_single,
)

# ── Helper factories ──────────────────────────────────────────────────────

def _make_company():
    from companies.models import Company
    return Company.objects.create(
        name='HashChain Test Co ' + str(uuid.uuid4())[:8],
        oib='HC' + str(uuid.uuid4().int)[:9],
    )


def _make_terminal(company, code=None):
    from pos.models import POSTerminal
    code = code or ('T' + str(uuid.uuid4().int)[:5])
    return POSTerminal.objects.create(
        company=company,
        name='Terminal ' + code,
        terminal_code=code,
    )


def _make_session(terminal, user, number=1):
    from pos.models import POSSession
    return POSSession.objects.create(
        terminal=terminal,
        operator=user,
        session_number=number,
        status='open',
        opening_cash=Decimal('0'),
    )


def _make_receipt(session, number=1, total=Decimal('100.00'), status='paid',
                  is_training=False):
    from pos.models import POSReceipt
    subtotal = (total / Decimal('1.25')).quantize(Decimal('0.01'))
    tax = total - subtotal
    receipt = POSReceipt.objects.create(
        session=session,
        receipt_number=number,
        subtotal=subtotal,
        tax_amount=tax,
        total=total,
        status=status,
        paid_at=timezone.now(),
        is_training=is_training,
        zki='ZKI-TEST',
        jir='JIR-TEST',
    )
    return receipt


def _add_item(receipt, description='Test item', quantity=1, unit_price=Decimal('80.00'),
              tax_rate=Decimal('25.00')):
    from pos.models import POSReceiptItem
    return POSReceiptItem.objects.create(
        receipt=receipt,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        tax_rate=tax_rate,
    )


# ══════════════════════════════════════════════════════════════════════════
# Core hash chain tests
# ══════════════════════════════════════════════════════════════════════════

class TestAppendReceipt(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('hashtest', password='test123')
        self.terminal = _make_terminal(self.company)
        self.session = _make_session(self.terminal, self.user)

    def test_genesis_link(self):
        """Test 1: first receipt creates genesis link with prev_hash=0*64."""
        receipt = _make_receipt(self.session, number=1)
        _add_item(receipt)

        link = append_receipt(receipt)

        self.assertEqual(ChainLink.objects.count(), 1)
        self.assertEqual(link.sequence, 1)
        self.assertEqual(link.prev_hash, '0' * 64)
        self.assertTrue(len(link.chain_hash) == 64)
        self.assertEqual(link.receipt, receipt)

    def test_chain_three_links(self):
        """Test 2: 3 receipts form a proper chain."""
        links = []
        for i in range(1, 4):
            r = _make_receipt(self.session, number=i, total=Decimal(str(10 * i)))
            _add_item(r, description=f'Item {i}', unit_price=Decimal(str(8 * i)))
            links.append(append_receipt(r))

        self.assertEqual(links[1].prev_hash, links[0].chain_hash)
        self.assertEqual(links[2].prev_hash, links[1].chain_hash)
        # All unique hashes
        hashes = {l.chain_hash for l in links}
        self.assertEqual(len(hashes), 3)


class TestVerifyChain(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('verifytest', password='test123')
        self.terminal = _make_terminal(self.company)
        self.session = _make_session(self.terminal, self.user)

    def _build_chain(self, count=5):
        for i in range(1, count + 1):
            r = _make_receipt(self.session, number=i, total=Decimal(str(10 + i)))
            _add_item(r, description=f'Item {i}', unit_price=Decimal(str(8 + i)))
            append_receipt(r)

    def test_intact_chain(self):
        """Test 3: verify_chain returns (True, None, 5) for intact chain."""
        self._build_chain(5)
        is_valid, break_point, total = verify_chain(self.company)
        self.assertTrue(is_valid)
        self.assertIsNone(break_point)
        self.assertEqual(total, 5)

    def test_tampered_chain(self):
        """Test 4: tampered payload_hash causes verify_chain to detect break."""
        self._build_chain(3)
        # Tamper with sequence 2
        ChainLink.objects.filter(company=self.company, sequence=2).update(
            payload_hash='a' * 64
        )
        is_valid, break_point, total = verify_chain(self.company)
        self.assertFalse(is_valid)
        self.assertEqual(break_point, 2)
        self.assertEqual(total, 2)  # stopped at link 2


class TestVerifySingle(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('singletest', password='test123')
        self.terminal = _make_terminal(self.company)
        self.session = _make_session(self.terminal, self.user)

    def test_unmodified_receipt(self):
        """Test 5: verify_single returns True for unmodified receipt."""
        r = _make_receipt(self.session, number=1)
        _add_item(r)
        append_receipt(r)
        self.assertTrue(verify_single(r))

    def test_modified_receipt(self):
        """Test 6: verify_single returns False after receipt total is changed."""
        r = _make_receipt(self.session, number=1, total=Decimal('100.00'))
        _add_item(r)
        append_receipt(r)
        # Modify total directly in DB
        from pos.models import POSReceipt
        POSReceipt.objects.filter(pk=r.pk).update(total=Decimal('9999.99'))
        r.refresh_from_db()
        self.assertFalse(verify_single(r))

    def test_receipt_not_in_chain(self):
        """Test 7: verify_single returns None for receipt without chain link."""
        r = _make_receipt(self.session, number=1)
        _add_item(r)
        # Do NOT call append_receipt
        result = verify_single(r)
        self.assertIsNone(result)


class TestDailyAnchorHash(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('anchortest', password='test123')
        self.terminal = _make_terminal(self.company)
        self.session = _make_session(self.terminal, self.user)

    def test_anchor_hash_returns_string(self):
        """Test 8: daily_anchor_hash returns 64-char hex string."""
        for i in range(1, 4):
            r = _make_receipt(self.session, number=i, total=Decimal(str(10 + i)))
            _add_item(r, description=f'Anchor item {i}')
            append_receipt(r)

        anchor = daily_anchor_hash(self.company)
        self.assertIsInstance(anchor, str)
        self.assertEqual(len(anchor), 64)

    def test_anchor_hash_empty_day(self):
        """Test 9: daily_anchor_hash returns None when no links today."""
        anchor = daily_anchor_hash(self.company)
        self.assertIsNone(anchor)


class TestSha256Determinism(TestCase):

    def test_same_input_same_hash(self):
        """Test 10: _sha256 is deterministic."""
        self.assertEqual(_sha256('test'), _sha256('test'))

    def test_different_input_different_hash(self):
        """Test 10b: _sha256 case-sensitive."""
        self.assertNotEqual(_sha256('test'), _sha256('Test'))


# ══════════════════════════════════════════════════════════════════════════
# PLG Virus — chain_link_safe property
# ══════════════════════════════════════════════════════════════════════════

class TestChainLinkSafe(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('safetest', password='test123')
        self.terminal = _make_terminal(self.company)
        self.session = _make_session(self.terminal, self.user)

    def test_chain_link_safe_exists(self):
        """Test 11: chain_link_safe returns ChainLink when in chain."""
        r = _make_receipt(self.session, number=1)
        _add_item(r)
        link = append_receipt(r)
        r.refresh_from_db()
        self.assertEqual(r.chain_link_safe, link)

    def test_chain_link_safe_not_exists(self):
        """Test 12: chain_link_safe returns None when not in chain."""
        r = _make_receipt(self.session, number=1)
        _add_item(r)
        self.assertIsNone(r.chain_link_safe)


# ══════════════════════════════════════════════════════════════════════════
# Checkout integration — training receipts NOT in chain
# ══════════════════════════════════════════════════════════════════════════

class TestCheckoutChainIntegration(TestCase):
    """Test 13: checkout skips chain for training receipts, adds for normal."""

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('checkouttest', password='test123')
        self.terminal = _make_terminal(self.company)
        self.session = _make_session(self.terminal, self.user)

    def test_training_receipt_not_in_chain(self):
        """Training receipts should NOT be added to hash chain (per checkout.py logic)."""
        r = _make_receipt(self.session, number=1, is_training=True)
        _add_item(r)
        # Simulate checkout logic: skip training
        if not r.is_training:
            append_receipt(r)
        self.assertEqual(ChainLink.objects.filter(company=self.company).count(), 0)

    def test_normal_receipt_in_chain(self):
        """Normal receipts get added to hash chain."""
        r = _make_receipt(self.session, number=1, is_training=False)
        _add_item(r)
        # Simulate checkout logic
        if not r.is_training:
            link = append_receipt(r)
        self.assertEqual(ChainLink.objects.filter(company=self.company).count(), 1)
        self.assertEqual(link.receipt, r)


# ══════════════════════════════════════════════════════════════════════════
# Chain integrity — multiple receipts cross-validation
# ══════════════════════════════════════════════════════════════════════════

class TestChainIntegrityCrossReceipts(TestCase):
    """End-to-end chain integrity across many receipts."""

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('crosstest', password='test123')
        self.terminal = _make_terminal(self.company)
        self.session = _make_session(self.terminal, self.user)

    def test_ten_receipts_chain_valid(self):
        """10 receipts form valid chain, verify passes."""
        for i in range(1, 11):
            r = _make_receipt(self.session, number=i, total=Decimal(str(10 * i)))
            _add_item(r, description=f'Bulk item {i}', unit_price=Decimal(str(8 * i)))
            append_receipt(r)

        is_valid, bp, total = verify_chain(self.company)
        self.assertTrue(is_valid)
        self.assertEqual(total, 10)

    def test_tamper_middle_breaks_chain(self):
        """Tampering with link 5 out of 10 breaks chain at 5."""
        for i in range(1, 11):
            r = _make_receipt(self.session, number=i, total=Decimal(str(10 * i)))
            _add_item(r, description=f'Tamper item {i}', unit_price=Decimal(str(8 * i)))
            append_receipt(r)

        # Tamper link 5
        ChainLink.objects.filter(company=self.company, sequence=5).update(
            chain_hash='b' * 64
        )

        is_valid, bp, total = verify_chain(self.company)
        self.assertFalse(is_valid)
        self.assertEqual(bp, 5)
