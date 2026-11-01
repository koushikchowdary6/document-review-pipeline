"""Bounded reads for trusted-local review bundles; no symlink traversal."""
import json
import math
import os
from pathlib import Path
import stat

MAX_BUNDLE_BYTES = 8_000_000
MAX_JSON_DEPTH = 128


def _check_json_nesting(text):
    """Bound structural JSON depth without counting delimiters inside strings."""
    depth = 0
    quoted = False
    escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ValueError('Review JSON nesting exceeds depth budget')
        elif char in ']}':
            depth -= 1


def _finite_json_float(value):
    """Reject JSON numeric exponents that overflow to infinity in Python."""
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError('Nonfinite JSON numeric value')
    return parsed

def read_text(path):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(Path(path), flags)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Bundle entry must be a regular file')
        data = stream.read(MAX_BUNDLE_BYTES + 1)
    if len(data) > MAX_BUNDLE_BYTES:
        raise ValueError('Bundle entry exceeds byte budget')
    return data.decode('utf-8')


def loads(text):
    _check_json_nesting(text)
    def pairs(items):
        out = {}
        for key,value in items:
            if key in out:
                raise ValueError('Duplicate JSON key')
            out[key]=value
        return out
    def invalid(_):
        raise ValueError('Nonfinite JSON value')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid,
                      parse_float=_finite_json_float)
