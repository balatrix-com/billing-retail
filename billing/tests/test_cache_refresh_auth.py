import unittest
from unittest.mock import patch

from fastapi import HTTPException

from src import api_server


class CacheRefreshAuthTest(unittest.TestCase):
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
