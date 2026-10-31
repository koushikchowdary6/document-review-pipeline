"""Fail-closed scoring for malformed detector predictions (synthetic fixtures)."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluate import evaluate
from redactor import Finding


class PredictionIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'synthetic.json'
        self.path.write_text(json.dumps({
            'schema_version': 1,
            'cases': [{'id': 'sample', 'text': 'a b c', 'entities': []}],
        }), encoding='utf-8')

    def test_duplicate_predictions_are_not_silently_deduplicated(self):
        finding = Finding('EMAIL', 'a', 0, 1)
        with patch('evaluate.detect', return_value=[finding, finding]):
            with self.assertRaises(ValueError):
                evaluate(self.path)

    def test_invalid_out_of_bounds_and_boolean_spans_fail(self):
        for finding in (
            Finding('EMAIL', 'x', 0, 6),
            Finding('EMAIL', 'x', -1, 1),
            Finding('EMAIL', 'x', 2, 2),
            Finding('EMAIL', 'x', True, 2),
            Finding('EMAIL', 'x', 0, False),
            Finding('email', 'a', 0, 1),
        ):
            with self.subTest(finding=finding):
                with patch('evaluate.detect', return_value=[finding]):
                    with self.assertRaisesRegex(ValueError, 'Invalid detector prediction'):
                        evaluate(self.path)

    def test_overlapping_or_out_of_order_predictions_fail(self):
        for findings in (
            [Finding('EMAIL', 'a b', 0, 3), Finding('SSN', 'b c', 2, 5)],
            [Finding('EMAIL', 'c', 4, 5), Finding('SSN', 'a', 0, 1)],
        ):
            with self.subTest(findings=findings):
                with patch('evaluate.detect', return_value=findings):
                    with self.assertRaisesRegex(ValueError, 'Overlapping or out-of-order'):
                        evaluate(self.path)

    def test_valid_distinct_predictions_are_scored_as_false_positives(self):
        findings = [Finding('EMAIL', 'a', 0, 1), Finding('SSN', 'c', 4, 5)]
        with patch('evaluate.detect', return_value=findings):
            report = evaluate(self.path)
        self.assertEqual(report['overall']['false_positives'], 2)
        self.assertEqual(len(report['cases'][0]['false_positives']), 2)


if __name__ == '__main__':
    unittest.main()
