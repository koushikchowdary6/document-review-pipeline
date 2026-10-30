"""Prevent silent metric inflation from ambiguous synthetic ground truth."""
import json
from pathlib import Path
import tempfile
import unittest

from evaluate import load_cases


class DatasetIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'cases.json'

    def write(self, cases):
        self.path.write_text(json.dumps({
            'schema_version': 1,
            'provenance': 'Synthetic labels only',
            'cases': cases,
        }), encoding='utf-8')

    def test_duplicate_ground_truth_span_rejected_instead_of_silently_deduplicated(self):
        label = {'kind': 'EMAIL', 'start': 0, 'end': 1}
        self.write([{'id': 'duplicate', 'text': 'a', 'entities': [label, dict(label)]}])
        with self.assertRaisesRegex(ValueError, 'Duplicate ground-truth'):
            load_cases(self.path)

    def test_unknown_case_fields_are_rejected(self):
        self.write([{'id': 'extra', 'text': 'a', 'entities': [], 'ignored_labels': [1]}])
        with self.assertRaises(ValueError):
            load_cases(self.path)

    def test_distinct_ordered_labels_and_dataset_provenance_are_accepted(self):
        self.write([{'id': 'valid', 'text': 'a b', 'entities': [
            {'kind': 'PERSON', 'start': 0, 'end': 1},
            {'kind': 'PERSON', 'start': 2, 'end': 3},
        ]}])
        data = load_cases(self.path)
        self.assertEqual(data['provenance'], 'Synthetic labels only')
        self.assertEqual(len(data['cases'][0]['entities']), 2)


if __name__ == '__main__':
    unittest.main()
