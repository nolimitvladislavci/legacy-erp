from django.test import TestCase

from .base import FiscalResult
from .models import FiscalProvider


class FiscalResultTest(TestCase):
    def test_default_values(self):
        r = FiscalResult(success=True)
        self.assertTrue(r.success)
        self.assertEqual(r.zki, '')
        self.assertEqual(r.jir, '')

    def test_hr_result(self):
        r = FiscalResult(success=True, zki='abc123', jir='xyz789')
        self.assertEqual(r.zki, 'abc123')
        self.assertEqual(r.jir, 'xyz789')

    def test_de_result(self):
        r = FiscalResult(success=True, tse_signature='sig', tse_transaction_number='TX1')
        self.assertEqual(r.tse_signature, 'sig')

    def test_error_result(self):
        r = FiscalResult(success=False, error_message='timeout')
        self.assertFalse(r.success)
        self.assertEqual(r.error_message, 'timeout')


class FiscalProviderChoicesTest(TestCase):
    def test_choices(self):
        self.assertEqual(FiscalProvider.HR_FINA, 'hr_fina')
        self.assertEqual(FiscalProvider.DE_TSE, 'de_tse')
        self.assertEqual(FiscalProvider.NONE, 'none')
