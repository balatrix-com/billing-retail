import unittest
from unittest.mock import MagicMock, patch
from processor import process_cdr_analytics
from datetime import datetime

class TestAnalyticsProcessor(unittest.TestCase):
    """Unit tests for the aggregation logic in processor.py (PostgreSQL Version)."""
    
    def setUp(self):
        """Prepare mock data and cursors."""
        self.mock_cursor = MagicMock()
        self.mock_cdrs = [
            {
                'cdr_id': 1,
                'customer_id': 'C001',
                'billsec': 30,
                'duration_sec': 35,
                'direction': 'inbound',
                'callee': '1234567890',
                'start_time': datetime(2026, 4, 18, 10, 0, 0)
            },
            {
                'cdr_id': 2,
                'customer_id': 'C001',
                'billsec': 0,
                'duration_sec': 10,
                'direction': 'outbound',
                'callee': '0987654321',
                'start_time': datetime(2026, 4, 18, 10, 30, 0)
            }
        ]

    @patch('processor.upsert_cdr_metrics_day')
    @patch('processor.upsert_cdr_metrics_hourly')
    @patch('processor.upsert_cdr_metrics_did_day')
    @patch('processor.upsert_cdr_metrics_hour_of_day')
    def test_processing_aggregation(self, mock_hod, mock_did, mock_hourly, mock_day):
        """Tests that the processor correctly groups and aggregates rows before calling upserts."""
        
        process_cdr_analytics(self.mock_cdrs, self.mock_cursor)
        
        # 1. Check daily upsert call
        self.assertTrue(mock_day.called)
        # Should have 2 records: (C001, today, inbound) and (C001, today, outbound)
        args, _ = mock_day.call_args
        records = args[1]
        self.assertEqual(len(records), 2)
        
        # 2. Check hourly upsert call
        self.assertTrue(mock_hourly.called)
        # Should have 2 records (10:00 inbound and 10:00 outbound)
        args, _ = mock_hourly.call_args
        records = args[1]
        self.assertEqual(len(records), 2)
        
        # 3. Check DID upsert
        self.assertTrue(mock_did.called)
        # Only the inbound call (cdr_id 1) should be in DID day
        args, _ = mock_did.call_args
        records = args[1]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0][2], '1234567890')

    @patch('processor.upsert_cdr_metrics_day')
    def test_empty_batch(self, mock_day):
        """Processor should return early and not call upserts if batch is empty."""
        process_cdr_analytics([], self.mock_cursor)
        self.assertFalse(mock_day.called)

if __name__ == "__main__":
    unittest.main()
