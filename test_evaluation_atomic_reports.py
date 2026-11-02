"""Regression tests for crash-safe, no-overwrite evaluation report publishing."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluate import write_report_exclusive


class AtomicReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "evaluation.json"

    def assert_no_staging_files(self):
        self.assertEqual(list(self.output.parent.glob(".evaluation.json.*.tmp")), [])

    def test_complete_json_is_published(self):
        payload = '{"schema_version":1,"score":0.75}\n'
        write_report_exclusive(self.output, payload)
        self.assertEqual(self.output.read_text(encoding="utf-8"), payload)
        self.assertEqual(json.loads(self.output.read_text())["score"], 0.75)
        self.assert_no_staging_files()

    def test_existing_report_is_never_replaced(self):
        self.output.write_text("previous verified report", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            write_report_exclusive(self.output, '{"score":1}\n')
        self.assertEqual(self.output.read_text(), "previous verified report")
        self.assert_no_staging_files()

    def test_failed_publish_does_not_leave_partial_destination(self):
        with patch("evaluate.os.link", side_effect=OSError("simulated publish failure")):
            with self.assertRaisesRegex(OSError, "publish failure"):
                write_report_exclusive(self.output, '{"score":1}\n')
        self.assertFalse(self.output.exists())
        self.assert_no_staging_files()

    def test_failed_file_sync_does_not_publish_report(self):
        with patch("evaluate.os.fsync", side_effect=OSError("simulated sync failure")):
            with self.assertRaisesRegex(OSError, "sync failure"):
                write_report_exclusive(self.output, '{"score":1}\n')
        self.assertFalse(self.output.exists())
        self.assert_no_staging_files()

    def test_existing_symlink_is_not_followed_or_replaced(self):
        target = self.output.parent / "other.txt"
        target.write_text("keep me", encoding="utf-8")
        try:
            self.output.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unsupported on this platform")
        with self.assertRaises(FileExistsError):
            write_report_exclusive(self.output, '{"score":1}\n')
        self.assertTrue(self.output.is_symlink())
        self.assertEqual(target.read_text(), "keep me")
        self.assert_no_staging_files()


if __name__ == "__main__":
    unittest.main()
