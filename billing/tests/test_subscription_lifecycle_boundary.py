import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('legacy_teardown', Path(__file__).parents[1] / 'src/services/teardown_service.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SubscriptionBoundaryTest(unittest.TestCase):
    def test_zero_wallet_never_suspends_paid_subscriptions(self):
        db, redis = Mock(), Mock()
        service = module.TeardownService(db, redis)
        service.enforce_hard_stop('U1001', 0)
        redis.sadd.assert_called_once_with(service.recording_key, 'U1001')
        db.cursor.assert_not_called()
        redis.set.assert_not_called()
        redis.publish.assert_not_called()
        service.restore_service('U1001', 10)
        redis.srem.assert_called_once_with(service.recording_key, 'U1001')
        db.cursor.assert_not_called()


if __name__ == '__main__':
    unittest.main()
