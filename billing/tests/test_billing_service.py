import unittest
from decimal import Decimal
from datetime import datetime, timezone
from src.services.billing_service import BillingService

class TestBillingServiceAndEdgeCases(unittest.TestCase):
    def setUp(self):
        self.billing_service = BillingService()
        self.batch_timestamp = datetime.now(timezone.utc)
        self.rate_cards = {
            1: {
                'ratecard_id': 1,
                'name': 'Standard 60/60',
                'in_rate_per_sec': '0.000167',
                'in_rate_per_min': '0.010000',
                'in_initial_increment_sec': 60,
                'in_increment_sec': 60,
                'ob_rate_per_sec': '0.000333',
                'ob_rate_per_min': '0.020000',
                'ob_initial_increment_sec': 60,
                'ob_increment_sec': 60
            }
        }
        self.customer_ratecards = {
            'cust_123': {'ratecard_id': 1, 'customer_id': 'cust_123'}
        }
        self.rec_rate_cards = {}
        self.customer_rec_rc = {}

    def _make_wallet(self, balance='50.00', free_secs=0):
        return {
            'fiat_balance': Decimal(balance),
            'free_seconds': free_secs,
            'credit_limit': Decimal('0'),
            'credit_used': Decimal('0'),
            'currency': 'USD'
        }

    def _make_cdr(self, cdr_id, billsec, duration_sec, direction='inbound'):
        return {
            'cdr_id': cdr_id,
            'call_uuid': f'550e8400-e29b-41d4-a716-{cdr_id:012d}',
            'customer_id': 'cust_123',
            'direction': direction,
            'billsec': billsec,
            'duration_sec': duration_sec,
            'currency': 'USD'
        }

    # ─── Pulse Rounding (60/60) ───────────────────────────────────────────────

    def test_2s_call_bills_for_60s(self):
        """2 second call with 60/60 rate card → must bill 60s"""
        cdr = self._make_cdr(201, billsec=2, duration_sec=2)
        wallet = self._make_wallet()
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 60)
        self.assertEqual(update['billed_amount'], Decimal('60') * Decimal('0.000167'))

    def test_31s_call_bills_for_60s(self):
        """31 second call with 60/60 rate card → must bill 60s"""
        cdr = self._make_cdr(202, billsec=31, duration_sec=31)
        wallet = self._make_wallet()
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 60)
        self.assertEqual(update['billed_amount'], Decimal('60') * Decimal('0.000167'))

    def test_55s_call_bills_for_60s(self):
        """55 second call with 60/60 rate card → must bill 60s"""
        cdr = self._make_cdr(203, billsec=55, duration_sec=55)
        wallet = self._make_wallet()
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 60)

    def test_exactly_60s_call_bills_for_60s(self):
        """Exactly 60 second call → must bill 60s"""
        cdr = self._make_cdr(204, billsec=60, duration_sec=60)
        wallet = self._make_wallet()
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 60)

    def test_61s_call_bills_for_120s(self):
        """61 second call with 60/60 rate card → must bill 120s"""
        cdr = self._make_cdr(205, billsec=61, duration_sec=61)
        wallet = self._make_wallet()
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 120)
        self.assertEqual(update['billed_amount'], Decimal('120') * Decimal('0.000167'))

    def test_88s_call_bills_for_120s(self):
        """1m 28s call with 60/60 rate card → must bill 120s (2m 0s)"""
        cdr = self._make_cdr(206, billsec=88, duration_sec=88)
        wallet = self._make_wallet()
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 120)

    def test_110s_call_bills_for_120s(self):
        """1m 50s call with 60/60 rate card → must bill 120s"""
        cdr = self._make_cdr(207, billsec=110, duration_sec=110)
        wallet = self._make_wallet()
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 120)

    def test_63s_call_bills_for_120s(self):
        """1m 3s call with 60/60 rate card → must bill 120s"""
        cdr = self._make_cdr(208, billsec=63, duration_sec=63)
        wallet = self._make_wallet()
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 120)

    # ─── Free Seconds ─────────────────────────────────────────────────────────

    def test_full_free_seconds_call(self):
        """60s call fully covered by 100 free seconds → billsec=60, billed_amount=0"""
        cdr = self._make_cdr(116, billsec=60, duration_sec=60)
        wallet = self._make_wallet(free_secs=100)
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 60)
        self.assertEqual(update['billed_amount'], Decimal('0'))
        self.assertEqual(update['total_amount'], Decimal('0'))
        self.assertEqual(txn['free_used_sec'], 60)
        self.assertEqual(txn['wallet_debit_amount'], Decimal('0'))
        self.assertEqual(wallet['free_seconds'], 40)
        self.assertEqual(wallet['fiat_balance'], Decimal('50.00'))

    def test_partial_free_seconds_call(self):
        """120s call, 60 free seconds → billed_amount = only remaining 60s"""
        cdr = self._make_cdr(117, billsec=120, duration_sec=120)
        wallet = self._make_wallet(free_secs=60)
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 120)
        expected_charge = Decimal('60') * Decimal('0.000167')
        self.assertEqual(update['billed_amount'], expected_charge)
        self.assertEqual(update['total_amount'], expected_charge)
        self.assertEqual(txn['free_used_sec'], 60)
        self.assertEqual(txn['wallet_debit_amount'], expected_charge)
        self.assertEqual(wallet['free_seconds'], 0)
        self.assertEqual(wallet['fiat_balance'], Decimal('50.00') - expected_charge)

    # ─── Unanswered / Zero / Negative Duration ────────────────────────────────

    def test_zero_duration_call(self):
        """Unanswered (billsec=0, duration_sec=0) → no billing, no free second deduction"""
        cdr = self._make_cdr(118, billsec=0, duration_sec=0)
        wallet = self._make_wallet(free_secs=100)
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 0)
        self.assertEqual(update['billed_amount'], Decimal('0'))
        self.assertEqual(update['total_amount'], Decimal('0'))
        self.assertEqual(txn['free_used_sec'], 0)
        self.assertEqual(txn['wallet_debit_amount'], Decimal('0'))
        self.assertEqual(wallet['free_seconds'], 100)  # free seconds NOT consumed
        self.assertEqual(wallet['fiat_balance'], Decimal('50.00'))

    def test_negative_duration_call(self):
        """Anomalous negative duration → treated as unanswered, no billing"""
        cdr = self._make_cdr(119, billsec=-10, duration_sec=-10)
        wallet = self._make_wallet(free_secs=100)
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 0)
        self.assertEqual(update['billed_amount'], Decimal('0'))
        self.assertEqual(update['total_amount'], Decimal('0'))
        self.assertEqual(txn['free_used_sec'], 0)
        self.assertEqual(wallet['free_seconds'], 100)
        self.assertEqual(wallet['fiat_balance'], Decimal('50.00'))

    def test_billsec_zero_falls_back_to_duration_sec(self):
        """SIP race condition: billsec=0 but duration_sec=31 → should bill 60s"""
        cdr = self._make_cdr(120, billsec=0, duration_sec=31)
        wallet = self._make_wallet()
        txn, update = self.billing_service.calculate_billing(
            cdr, self.rate_cards, self.customer_ratecards,
            self.rec_rate_cards, self.customer_rec_rc, wallet, self.batch_timestamp
        )
        self.assertIsNotNone(txn)
        self.assertEqual(update['billsec'], 60)
        self.assertEqual(update['billed_amount'], Decimal('60') * Decimal('0.000167'))


if __name__ == '__main__':
    unittest.main()
