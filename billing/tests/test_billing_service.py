import unittest
from datetime import datetime, timezone
from decimal import Decimal

from src.services.billing_service import BillingService


class RecordingOnlyBillingTest(unittest.TestCase):
    def setUp(self):
        self.service = BillingService()
        self.now = datetime.now(timezone.utc)
        self.wallet = {
            'fiat_balance': Decimal('50.00'),
            'free_seconds': 3600,
            'credit_limit': Decimal('0'),
            'credit_used': Decimal('0'),
            'currency': 'USD',
        }

    def cdr(self, recording=False, billsec=60):
        return {
            'cdr_id': 1,
            'call_uuid': '550e8400-e29b-41d4-a716-446655440000',
            'customer_id': 'cust_123',
            'direction': 'outbound',
            'billsec': billsec,
            'duration_sec': billsec,
            'currency': 'USD',
            'recording': recording,
        }

    def calculate(self, cdr, rec_cards=None, customer_rec=None):
        return self.service.calculate_billing(
            cdr,
            {},
            {},
            rec_cards or {},
            customer_rec or {},
            self.wallet,
            self.now,
        )

    def test_unrecorded_call_has_zero_charge_and_does_not_consume_free_seconds(self):
        transaction, update = self.calculate(self.cdr(recording=False, billsec=125))

        self.assertEqual(update['billsec'], 125)
        self.assertEqual(update['billed_amount'], Decimal('0'))
        self.assertEqual(update['recording_amount'], Decimal('0'))
        self.assertEqual(update['total_amount'], Decimal('0'))
        self.assertEqual(transaction['wallet_debit_amount'], Decimal('0'))
        self.assertEqual(transaction['free_used_sec'], 0)
        self.assertEqual(self.wallet['free_seconds'], 3600)
        self.assertEqual(self.wallet['fiat_balance'], Decimal('50.00'))

    def test_recording_is_the_only_wallet_debit(self):
        rec_cards = {
            '7': {
                'id': 7,
                'rate_per_sec': '0.001',
                'billing_increments': 60,
                'retention_period': 30,
            }
        }
        customer_rec = {'cust_123': {'rec_rc_id': 7}}

        transaction, update = self.calculate(
            self.cdr(recording=True, billsec=61), rec_cards, customer_rec
        )

        self.assertEqual(update['billed_amount'], Decimal('0'))
        self.assertEqual(update['recording_amount'], Decimal('0.120'))
        self.assertEqual(update['total_amount'], Decimal('0.120'))
        self.assertEqual(transaction['wallet_debit_amount'], Decimal('0.120'))
        self.assertEqual(self.wallet['fiat_balance'], Decimal('49.880'))

    def test_recording_charge_uses_credit_and_triggers_hard_stop(self):
        self.wallet['fiat_balance'] = Decimal('0.01')
        self.wallet['credit_limit'] = Decimal('0.02')
        rec_cards = {
            '7': {
                'id': 7,
                'rate_per_sec': '0.001',
                'billing_increments': 60,
                'retention_period': 30,
            }
        }

        self.calculate(
            self.cdr(recording=True, billsec=60),
            rec_cards,
            {'cust_123': {'rec_rc_id': 7}},
        )

        self.assertEqual(self.wallet['fiat_balance'], Decimal('0'))
        self.assertEqual(self.wallet['credit_used'], Decimal('0.050'))
        self.assertEqual(self.wallet['available_purchasing_power'], Decimal('0'))
        self.assertTrue(self.wallet['hard_stop_triggered'])


if __name__ == '__main__':
    unittest.main()
