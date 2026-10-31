"""Standalone redactor CLI must reject unsafe file sources without leaking text."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "redactor.py"


def invoke(path):
    return subprocess.run(
        [sys.executable, str(CLI), str(path)],
        capture_output=True, text=True, check=False, timeout=10,
    )


def test_regular_file_redacts_without_exposing_email(tmp_path):
    source = tmp_path / "input.txt"
    source.write_text("Contact demo@example.com", encoding="utf-8")
    result = invoke(source)
    assert result.returncode == 0, result.stderr
    assert "demo@example.com" not in result.stdout
    assert "[REDACTED:EMAIL]" in result.stdout


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="O_NOFOLLOW unavailable")
def test_symlink_is_rejected_without_output(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("Contact demo@example.com", encoding="utf-8")
    link = tmp_path / "input.txt"
    link.symlink_to(target)
    result = invoke(link)
    assert result.returncode != 0
    assert not result.stdout
    assert "demo@example.com" not in result.stderr


@pytest.mark.skipif(
    not (hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK")),
    reason="nonblocking FIFO unavailable",
)
def test_fifo_is_rejected_without_waiting_for_writer(tmp_path):
    source = tmp_path / "input.fifo"
    os.mkfifo(source)
    result = invoke(source)
    assert result.returncode != 0
    assert not result.stdout


def test_invalid_utf8_is_rejected_without_output(tmp_path):
    source = tmp_path / "input.txt"
    source.write_bytes(b"\xff\xfe")
    result = invoke(source)
    assert result.returncode != 0
    assert not result.stdout


def test_oversized_regular_file_is_rejected_before_redaction(tmp_path):
    source = tmp_path / "input.txt"
    source.write_bytes(b"A" * 4_000_001)
    result = invoke(source)
    assert result.returncode != 0
    assert not result.stdout
