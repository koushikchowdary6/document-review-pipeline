import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import decision
from decision import decide, export_approved, inspect_bundle, verify_bundle
from review import build

class IntegrityControlsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);source=self.root/'source';source.write_text('Contact demo@example.com')
        self.bundle=self.root/'bundle';build(source,self.bundle)
    def approve(self):decide(self.bundle,'approved','reviewer','Inspected synthetic text')
    def test_duplicate_manifest_key_rejected(self):
        p=self.bundle/'manifest.json';p.write_text(p.read_text().replace('"schema_version": 1','"schema_version": 1, "schema_version": 1'))
        with self.assertRaises(ValueError):verify_bundle(self.bundle)
    def test_invalid_metadata_rejected_before_approval(self):
        p=self.bundle/'manifest.json';original=json.loads(p.read_text())
        for field,value in [('schema_version',True),('characters',False),('finding_counts',{'EMAIL':7}),('source_sha256','invalid')]:
            altered=dict(original,**{field:value});p.write_text(json.dumps(altered))
            with self.subTest(field=field),self.assertRaises(ValueError):self.approve()
    def test_symlinked_sanitized_file_rejected(self):
        p=self.bundle/'sanitized.txt';target=self.root/'replacement';p.rename(target)
        p.symlink_to(target)
        with self.assertRaises(OSError):verify_bundle(self.bundle)
    def test_bounded_bundle_read(self):
        with patch('integrity.MAX_BUNDLE_BYTES',10),self.assertRaises(ValueError):verify_bundle(self.bundle)
    def test_nonfinite_manifest_rejected(self):
        p=self.bundle/'manifest.json';p.write_text(p.read_text().replace('"characters": 24','"characters": NaN'))
        # Insert an explicit extra nonfinite value independent of text length.
        p.write_text(p.read_text().replace('{','{"invalid":NaN,',1))
        with self.assertRaises(ValueError):verify_bundle(self.bundle)
    def test_export_uses_one_validated_bundle_snapshot(self):
        self.approve()
        with patch('decision.verify_bundle',wraps=decision.verify_bundle) as verify:
            export_approved(self.bundle,self.root/'export')
        self.assertEqual(verify.call_count,1)
    def test_failed_publication_leaves_no_partial_export(self):
        self.approve();out=self.root/'export'
        with patch('decision.os.link',side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):export_approved(self.bundle,out)
        self.assertFalse(out.exists());self.assertEqual(list(self.root.glob('.publish-*')),[])
    def test_malformed_review_timestamp_blocks_export(self):
        self.approve();p=self.bundle/'decision.json';data=json.loads(p.read_text());data['reviewed_at_utc']='not-a-time';p.write_text(json.dumps(data))
        with self.assertRaises(ValueError):export_approved(self.bundle,self.root/'export')
    def test_inspection_omits_content_by_default(self):
        view=inspect_bundle(self.bundle)
        self.assertNotIn('sanitized_text',view)
        self.assertNotIn('demo@example.com',json.dumps(view))
        self.assertIn('sanitized_text',inspect_bundle(self.bundle,True))
