import json
from pathlib import Path
import tempfile
import unittest
from review import build
from decision import decide, export_approved, review_status

class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / 'source.txt'
        source.write_text('Contact demo@example.com')
        self.bundle = self.root / 'bundle'
        build(source, self.bundle)

    def test_pending_status_has_no_export_side_effect(self):
        self.assertEqual(review_status(self.bundle), {'status':'pending_manual_review','export_allowed':False})
        self.assertEqual(sorted(p.name for p in self.bundle.iterdir()), ['manifest.json','sanitized.txt'])

    def test_rejected_status(self):
        decide(self.bundle, 'rejected', 'reviewer', 'Needs correction')
        self.assertEqual(review_status(self.bundle), {'status':'rejected','export_allowed':False})

    def test_approved_status_and_export(self):
        decide(self.bundle, 'approved', 'reviewer', 'Inspected content')
        self.assertTrue(review_status(self.bundle)['export_allowed'])
        export_approved(self.bundle, self.root / 'export.txt')

    def test_manifest_metadata_change_invalidates_approval(self):
        decide(self.bundle, 'approved', 'reviewer', 'Inspected content')
        manifest_path = self.bundle / 'manifest.json'
        data = json.loads(manifest_path.read_text())
        data['source_sha256'] = '0' * 64
        manifest_path.write_text(json.dumps(data))
        with self.assertRaises(ValueError): review_status(self.bundle)
        with self.assertRaises(ValueError): export_approved(self.bundle, self.root / 'export.txt')
        self.assertFalse((self.root / 'export.txt').exists())

    def test_json_reformat_does_not_invalidate_review(self):
        decide(self.bundle, 'approved', 'reviewer', 'Inspected content')
        p = self.bundle / 'manifest.json'
        p.write_text(json.dumps(json.loads(p.read_text()), separators=(',', ':')))
        self.assertTrue(review_status(self.bundle)['export_allowed'])

    def test_legacy_unbound_decision_fails_closed(self):
        decide(self.bundle, 'approved', 'reviewer', 'Inspected content')
        p = self.bundle / 'decision.json'
        data = json.loads(p.read_text()); del data['manifest_sha256']
        p.write_text(json.dumps(data))
        with self.assertRaises(ValueError): review_status(self.bundle)
