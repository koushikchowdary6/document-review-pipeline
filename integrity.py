"""Bounded reads for trusted-local review bundles; no symlink traversal."""
import json
import os
from pathlib import Path
import stat

MAX_BUNDLE_BYTES = 8_000_000

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
    def pairs(items):
        out = {}
        for key,value in items:
            if key in out:
                raise ValueError('Duplicate JSON key')
            out[key]=value
        return out
    def invalid(_):
        raise ValueError('Nonfinite JSON value')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)
