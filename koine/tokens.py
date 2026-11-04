"""Token-count estimation used by `koine stats` and the benchmark.

Uses tiktoken (cl100k_base) when it is installed; otherwise a coarse
BPE-like heuristic. The result is labelled so nobody mistakes an estimate
for a measurement.
"""
from __future__ import annotations

import math
import re

_WORD = re.compile(r"[A-Za-z]+|\d{1,3}|[^\sA-Za-z\d]|\s+")

try:  # optional dependency
    import tiktoken  # type: ignore

    _ENC = tiktoken.get_encoding("cl100k_base")
    METHOD = "tiktoken/cl100k_base"
except Exception:  # pragma: no cover - depends on environment
    _ENC = None
    METHOD = "heuristic"


def _heuristic(text: str) -> int:
    n = 0
    for m in _WORD.finditer(text):
        t = m.group()
        if t.isspace():
            continue
        if t.isalpha():
            n += 1 if len(t) <= 6 else math.ceil(len(t) / 5)
        else:
            n += 1
    return n


def count(text: str) -> int:
    if _ENC is not None:
        return len(_ENC.encode(text))
    return _heuristic(text)
