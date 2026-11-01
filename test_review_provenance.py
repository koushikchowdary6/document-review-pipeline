"""Review provenance is untrusted local metadata, never authenticated identity."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from decision import decide, export_approved, review_status
from review import build


class ReviewProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / 'source.txt'
        source.write_text('Email demo@example.com', encoding='utf-8')
        self.bundle = self.root / 'bundle'
        build(source, self.bundle)
        self.export = self.root / 'export.txt'

    def _approve(self, reviewer='José García'):
        return decide(self.bundle, 'approved', reviewer, 'Inspected synthetic redaction')

    def _change_record(self, **changes):
        path = self.bundle / 'decision.json'
        record = json.loads(path.read_text(encoding='utf-8'))
        record.update(changes)
        path.write_text(json.dumps(record), encoding='utf-8')

    def test_normal_unicode_name_and_utc_review_remain_exportable(self):
        record = self._approve()
        self.assertEqual(record['reviewer'], 'José García')
        self.assertTrue(review_status(self.bundle)['export_allowed'])
        export_approved(self.bundle, self.export)
        self.assertTrue(self.export.is_file())

    def test_invisible_or_spoofed_reviewer_cannot_approve(self):
        for label in ('Alice\u202e', 'Al\u200bice', 'Alice\nAdmin', '\u034f',
                      'Alice\ufe0f', '\ud800'):
            with self.subTest(label=repr(label)):
                with self.assertRaises(ValueError):
                    self._approve(label)
                self.assertFalse((self.bundle / 'decision.json').exists())

    def test_tampered_reviewer_is_rejected_on_export(self):
        self._approve()
        self._change_record(reviewer='Alice\u202e')
        with self.assertRaises(ValueError):
            export_approved(self.bundle, self.export)
        self.assertFalse(self.export.exists())

    def test_future_dated_approval_cannot_authorize_export(self):
        self._approve()
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        self._change_record(reviewed_at_utc=future)
        with self.assertRaisesRegex(ValueError, 'future'):
            export_approved(self.bundle, self.export)
        self.assertFalse(self.export.exists())

    def test_non_utc_offset_is_not_accepted_as_utc_provenance(self):
        self._approve()
        self._change_record(reviewed_at_utc='2026-01-01T12:00:00+02:00')
        with self.assertRaisesRegex(ValueError, 'UTC'):
            review_status(self.bundle)

    def test_unrecognized_decision_fields_are_not_trusted(self):
        self._approve()
        self._change_record(reviewer_authenticated=True)
        with self.assertRaises(ValueError):
            export_approved(self.bundle, self.export)
        self.assertFalse(self.export.exists())


if __name__ == '__main__':
    unittest.main()
