import unittest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from src.services.cdr_processor import CDRProcessor

class TestCDRProcessorEdgeCases(unittest.TestCase):
    def setUp(self):
        with patch('src.services.cdr_processor.subprocess.run'):
            self.redis = MagicMock()
            self.processor = CDRProcessor(redis_client=self.redis)

    @patch('src.services.cdr_processor.psycopg.connect')
    def test_process_batch_with_unknown_customer(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock CDR query returning an unknown customer CDR (like CDR 113)
        mock_cursor.fetchall.side_effect = [
            # 1. Unrated CDRs fetch
            [{
                'cdr_id': 113,
                'call_uuid': '550e8400-e29b-41d4-a716-446655440000',
                'customer_id': 'unknown',
                'direction': 'inbound',
                'duration_sec': 100,
                'billsec': 90,
                'currency': 'USD',
                'ratecard_id': None,
                'start_time': datetime.now(timezone.utc),
                'dest_type': None,
                'dest_value': None,
                'status_code': '200 OK',
                'call_status': 'answered',
                'recording': False
            }]
        ]
        mock_cursor.rowcount = 1

        # Mock cache loader methods
        self.processor.load_rate_cards_cache = MagicMock(return_value={1: {'ratecard_id': 1}})
        self.processor.load_customer_ratecard_cache = MagicMock(return_value={'cust_1': {'ratecard_id': 1}})
        self.processor.load_rec_rate_cards_cache = MagicMock(return_value={})
        self.processor.load_customer_rec_rc_cache = MagicMock(return_value={})

        processed = self.processor.process_batch()
        self.assertEqual(processed, 1)
        mock_conn.commit.assert_called_once()

        # Verify UPDATE query was executed on cdr
        executed_queries = [str(call[0][0]) for call in mock_cursor.execute.call_args_list]
        has_update = any("UPDATE cdr AS c" in q for q in executed_queries)
        self.assertTrue(has_update, "Expected UPDATE cdr query to be executed")

    @patch('src.services.cdr_processor.psycopg.connect')
    def test_process_batch_mixed_valid_and_unknown(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        cdrs = [
            {
                'cdr_id': 113,
                'call_uuid': '550e8400-e29b-41d4-a716-446655440000',
                'customer_id': 'unknown',
                'direction': 'inbound',
                'duration_sec': 100,
                'billsec': 90,
                'currency': 'USD',
                'ratecard_id': None,
                'start_time': datetime.now(timezone.utc),
                'dest_type': None,
                'dest_value': None,
                'status_code': '200 OK',
                'call_status': 'answered',
                'recording': False
            },
            {
                'cdr_id': 114,
                'call_uuid': '550e8400-e29b-41d4-a716-446655440001',
                'customer_id': 'cust_valid',
                'direction': 'inbound',
                'duration_sec': 60,
                'billsec': 60,
                'currency': 'USD',
                'ratecard_id': None,
                'start_time': datetime.now(timezone.utc),
                'dest_type': None,
                'dest_value': None,
                'status_code': '200 OK',
                'call_status': 'answered',
                'recording': False
            }
        ]

        wallets_row = [{
            'customer_id': 'cust_valid',
            'currency': 'USD',
            'fiat_balance': Decimal('100.00'),
            'free_seconds': 0,
            'credit_limit': Decimal('0'),
            'credit_used': Decimal('0'),
            'version': 1
        }]

        mock_cursor.fetchall.side_effect = [
            cdrs, # fetch unrated cdrs
            wallets_row, # fetch locked wallets
            [{'transaction_id': 999, 'source_ref': '114'}], # returning from insert transactions
        ]
        mock_cursor.rowcount = 2

        self.processor.load_rate_cards_cache = MagicMock(return_value={
            1: {
                'ratecard_id': 1,
                'name': 'Standard',
                'in_rate_per_sec': '0.001',
                'in_rate_per_min': '0.06',
                'in_initial_increment_sec': 60,
                'in_increment_sec': 60,
                'ob_rate_per_sec': '0.002',
                'ob_rate_per_min': '0.12',
                'ob_initial_increment_sec': 60,
                'ob_increment_sec': 60
            }
        })
        self.processor.load_customer_ratecard_cache = MagicMock(return_value={
            'cust_valid': {'ratecard_id': 1, 'customer_id': 'cust_valid'}
        })
        self.processor.load_rec_rate_cards_cache = MagicMock(return_value={})
        self.processor.load_customer_rec_rc_cache = MagicMock(return_value={})

        processed = self.processor.process_batch()
        self.assertEqual(processed, 2)
        mock_conn.commit.assert_called_once()

    def test_recording_gate_tracks_available_purchasing_power(self):
        wallets = {
            'blocked': {
                'fiat_balance': Decimal('0'),
                'credit_limit': Decimal('10'),
                'credit_used': Decimal('10'),
            },
            'active': {
                'fiat_balance': Decimal('1'),
                'credit_limit': Decimal('0'),
                'credit_used': Decimal('0'),
            },
        }

        self.processor._sync_recording_gates(wallets, ['blocked', 'active'])

        self.redis.sadd.assert_called_once_with(
            'blacklist:customers:recording_overlimit', 'blocked'
        )
        self.redis.srem.assert_called_once_with(
            'blacklist:customers:recording_overlimit', 'active'
        )

if __name__ == '__main__':
    unittest.main()
