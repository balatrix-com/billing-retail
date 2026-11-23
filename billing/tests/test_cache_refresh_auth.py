import unittest
from unittest.mock import patch

from fastapi import HTTPException

from src import api_server


class CacheRefreshAuthTest(unittest.TestCase):
    def test_both_refresh_urls_use_recording_rates_and_retain_authentication(self):
        for path in ("/api/v1/cache/refresh", "/api/v1/cache/refresh-record"):
            with self.subTest(path=path):
                route = next(r for r in api_server.app.routes if r.path == path)
                self.assertTrue(any(d.call is api_server.require_refresh_token for d in route.dependant.dependencies))
                with patch.object(api_server, "run_refresh_record", return_value={"status": "success"}) as refresh:
                    # This handler does not await I/O. Advance it directly so the
                    # unit test needs neither a network socket nor an event loop.
                    with self.assertRaises(StopIteration) as completed:
                        route.endpoint(_authorized=None).send(None)
                    result = completed.exception.value
                refresh.assert_called_once_with()
                self.assertEqual(result["details"]["status"], "success")

    def test_missing_configuration_fails_closed(self):
        with patch.object(api_server.config, "REFRESH_CACHE_TOKEN", ""):
            with self.assertRaises(HTTPException) as raised:
                api_server.require_refresh_token("any-token")
        self.assertEqual(raised.exception.status_code, 503)

    def test_missing_or_wrong_header_is_rejected(self):
        with patch.object(api_server.config, "REFRESH_CACHE_TOKEN", "a" * 32):
            for supplied in (None, "b" * 32):
                with self.subTest(supplied=supplied):
                    with self.assertRaises(HTTPException) as raised:
                        api_server.require_refresh_token(supplied)
                    self.assertEqual(raised.exception.status_code, 403)

    def test_matching_header_is_accepted(self):
        with patch.object(api_server.config, "REFRESH_CACHE_TOKEN", "a" * 32):
            self.assertIsNone(api_server.require_refresh_token("a" * 32))


if __name__ == "__main__":
    unittest.main()
