import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from redactor import Finding
from evaluate import evaluate,load_cases,rates
from demo import run

class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'dataset.json'
    def write(self,cases):self.path.write_text(json.dumps({'schema_version':1,'cases':cases}))
    def test_exact_span_precision_and_recall_are_hand_calculable(self):
        self.write([{'id':'one','text':'a b c','entities':[{'kind':'PERSON','start':0,'end':1},{'kind':'PERSON','start':2,'end':3}]}])
        with patch('evaluate.detect',return_value=[Finding('PERSON','a',0,1),Finding('PERSON','c',4,5)]):result=evaluate(self.path)
        self.assertEqual(result['overall'],{'true_positives':1,'false_positives':1,'false_negatives':1,'precision':.5,'recall':.5})
    def test_negative_document_false_positive_rate(self):
        self.write([{'id':'negative','text':'a','entities':[]}])
        with patch('evaluate.detect',return_value=[Finding('PERSON','a',0,1)]):result=evaluate(self.path)
        self.assertEqual(result['negative_document_false_positive_rate'],1)
    def test_no_denominator_is_unavailable_not_perfect(self):
        self.assertEqual(rates(0,0,0)['precision'],None)
        self.assertEqual(rates(0,0,0)['recall'],None)
    def test_duplicate_ids_and_invalid_labels_rejected(self):
        case={'id':'same','text':'a','entities':[]}
        self.write([case,case])
        with self.assertRaises(ValueError):load_cases(self.path)
        case['entities']=[{'kind':'PERSON','start':False,'end':1}];self.write([case])
        with self.assertRaises(ValueError):load_cases(self.path)
    def test_checked_in_report_is_reproducible_and_omits_raw_text(self):
        root=Path(__file__).parent
        report=evaluate(root/'fixtures/pii_eval.json')
        self.assertEqual(report,json.loads((root/'evaluation/baseline.json').read_text()))
        self.assertNotIn('demo@example.com',json.dumps(report))
    def test_synthetic_end_to_end_control_demo(self):
        result=run(Path(self.temp.name)/'demo',True)
        for key in ['pending_export_blocked','approved_export_succeeded','tampered_export_blocked','rejected_export_blocked']:
            self.assertTrue(result[key])
