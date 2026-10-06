import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import scripts.purge_old_recordings as purge_module


class TestPurgeOldRecordings(unittest.TestCase):
    def test_purge_once_deletes_expired_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cust_dir = tmp_path / "1001"
            cust_dir.mkdir()
            rec_file = cust_dir / "call-abc-123.mp3"
            rec_file.write_text("dummy audio")

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                ("call-abc-123", "1001"),
                ("non-existent-uuid", "1001"),
            ]

            with patch.object(purge_module, "RECORDINGS_DIR", tmp_path), \
                 patch.object(purge_module, "db_connect", return_value=mock_conn):
                purge_module.purge_once(dry_run=False)

            self.assertFalse(rec_file.exists(), "Expired recording file should have been deleted")

    def test_purge_once_resolves_u_prefix_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Folder on disk uses 'U1044' prefix as in wlabel FreeSWITCH dialplans
            cust_dir = tmp_path / "U1044"
            cust_dir.mkdir()
            rec_file = cust_dir / "call-xyz-789.mp3"
            rec_file.write_text("dummy audio")

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            # Database stores customer_id as numeric '1044'
            mock_cursor.fetchall.return_value = [
                ("call-xyz-789", "1044"),
            ]

            with patch.object(purge_module, "RECORDINGS_DIR", tmp_path), \
                 patch.object(purge_module, "db_connect", return_value=mock_conn):
                purge_module.purge_once(dry_run=False)

            self.assertFalse(rec_file.exists(), "Should delete file in U1044 folder when DB customer_id is 1044")

    def test_purge_once_dry_run_preserves_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cust_dir = tmp_path / "1001"
            cust_dir.mkdir()
            rec_file = cust_dir / "call-abc-123.mp3"
            rec_file.write_text("dummy audio")

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                ("call-abc-123", "1001"),
            ]

            with patch.object(purge_module, "RECORDINGS_DIR", tmp_path), \
                 patch.object(purge_module, "db_connect", return_value=mock_conn):
                purge_module.purge_once(dry_run=True)

            self.assertTrue(rec_file.exists(), "Dry run should NOT delete file")

    def test_purge_once_blocks_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            outside_file = tmp_path.parent / "important_outside.mp3"
            outside_file.write_text("do not delete")

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            # Attempt traversal outside RECORDINGS_DIR
            mock_cursor.fetchall.return_value = [
                ("../important_outside", ".."),
            ]

            try:
                with patch.object(purge_module, "RECORDINGS_DIR", tmp_path), \
                     patch.object(purge_module, "db_connect", return_value=mock_conn):
                    purge_module.purge_once(dry_run=False)

                self.assertTrue(outside_file.exists(), "Path traversal target must NOT be deleted")
            finally:
                if outside_file.exists():
                    outside_file.unlink()


if __name__ == "__main__":
    unittest.main()
