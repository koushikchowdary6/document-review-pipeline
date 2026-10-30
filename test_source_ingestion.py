"""Source ingestion must not follow links or block on special files."""
import os
from pathlib import Path
import tempfile
import unittest

from review import build


class SourceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.destination = self.root / "review-bundle"

    def test_regular_utf8_file_still_builds(self):
        source = self.root / "source.txt"
        source.write_text("Contact demo@example.com", encoding="utf-8")
        manifest = build(source, self.destination)
        self.assertEqual(manifest["status"], "pending_manual_review")
        self.assertTrue((self.destination / "manifest.json").is_file())
        self.assertTrue((self.destination / "sanitized.txt").is_file())

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "O_NOFOLLOW unavailable")
    def test_symlinked_source_is_rejected_without_output(self):
        target = self.root / "target.txt"
        target.write_text("Contact demo@example.com", encoding="utf-8")
        source = self.root / "source.txt"
        source.symlink_to(target)
        with self.assertRaises((OSError, ValueError)):
            build(source, self.destination)
        self.assertFalse(self.destination.exists())

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"),
                         "Nonblocking FIFO unavailable")
    def test_fifo_source_is_rejected_without_waiting_for_writer(self):
        source = self.root / "input.fifo"
        os.mkfifo(source)
        with self.assertRaises(ValueError):
            build(source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_invalid_utf8_source_is_rejected_without_output(self):
        source = self.root / "invalid.txt"
        source.write_bytes(b"\xff\xfe")
        with self.assertRaises(UnicodeDecodeError):
            build(source, self.destination)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
