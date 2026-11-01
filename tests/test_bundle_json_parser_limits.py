"""Fail closed on pathological or ambiguous JSON before review/export."""

import json

import pytest

from integrity import MAX_JSON_DEPTH, loads
from decision import verify_bundle
from review import build
from evaluate import load_cases


def test_exact_depth_boundary_and_overflow():
    assert loads("[" * MAX_JSON_DEPTH + "0" + "]" * MAX_JSON_DEPTH)
    with pytest.raises(ValueError, match="nesting"):
        loads("[" * (MAX_JSON_DEPTH + 1) + "0" + "]" * (MAX_JSON_DEPTH + 1))


def test_delimiters_inside_escaped_json_string_do_not_count():
    value = {"text": ('[{}]"\\' * 1000)}
    assert loads(json.dumps(value)) == value


def test_extreme_exponent_is_not_accepted_as_infinity():
    with pytest.raises(ValueError, match="Nonfinite"):
        loads('{"provenance": 1e9999}')
    assert loads('{"ratio": 1.25e2}') == {"ratio": 125.0}


def test_manifest_excessive_depth_blocks_bundle_verification(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Contact demo@example.com", encoding="utf-8")
    bundle = tmp_path / "bundle"
    build(source, bundle)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["extra"] = "[" * (MAX_JSON_DEPTH + 1)
    # Actual nested arrays, not a string that merely contains brackets.
    raw = json.dumps(manifest)
    raw = raw[:-1] + ', "nested": ' + "[" * (MAX_JSON_DEPTH + 1) + "0" + "]" * (MAX_JSON_DEPTH + 1) + "}"
    manifest_path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError, match="nesting"):
        verify_bundle(bundle)


def test_evaluation_rejects_overflowed_provenance(tmp_path):
    dataset = tmp_path / "cases.json"
    dataset.write_text(
        '{"schema_version":1,"provenance":1e9999,'
        '"cases":[{"id":"benign","text":"hello","entities":[]}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Nonfinite"):
        load_cases(dataset)
