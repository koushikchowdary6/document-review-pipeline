"""Synthetic exact-span evaluation must use valid Unicode scalar text."""
import json
from pathlib import Path
import tempfile
import unittest

from evaluate import evaluate, load_cases


class EvaluationUnicodeScalarTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "dataset.json"

    def write(self, text, entities=None):
        self.path.write_text(
            json.dumps({
                "schema_version": 1,
                "cases": [{
                    "id": "unicode",
                    "text": text,
                    "entities": entities if entities is not None else [],
                }],
            }),
            encoding="utf-8",
        )

    def test_escaped_lone_high_and_low_surrogates_are_rejected(self):
        # json.dumps emits \\ud800/\\udfff as ASCII escapes; UTF-8 file
        # decoding alone does not protect against these malformed values.
        for text in ("prefix\ud800suffix", "\udfff", "\ud800"):
            with self.subTest(text=repr(text)):
                self.write(text)
                with self.assertRaisesRegex(ValueError, "Unicode surrogate"):
                    load_cases(self.path)
                with self.assertRaisesRegex(ValueError, "Unicode surrogate"):
                    evaluate(self.path)

    def test_valid_astral_unicode_is_one_character_for_span_scoring(self):
        # A valid JSON surrogate pair decodes to one Unicode scalar, so
        # character offsets follow Python's actual decoded text indexing.
        self.write("A🚀B", [{"kind": "PERSON", "start": 1, "end": 2}])
        loaded = load_cases(self.path)
        self.assertEqual(loaded["cases"][0]["text"], "A🚀B")
        self.assertEqual(len(loaded["cases"][0]["text"]), 3)


if __name__ == "__main__":
    unittest.main()
