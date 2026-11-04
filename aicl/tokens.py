"""Token-count estimation used by `aicl stats` and the benchmark.

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


def get_counter(name=None):
    """Token counter by name: None/'auto', 'chars', 'heuristic', or a tiktoken encoding
    name such as 'cl100k_base' / 'o200k_base' (optionally prefixed 'tiktoken:')."""
    if name in (None, "", "auto"):
        return count
    if name == "chars":
        return len
    if name == "heuristic":
        return _heuristic
    enc_name = name.split(":", 1)[1] if name.startswith("tiktoken:") else name
    try:
        import tiktoken  # type: ignore
        enc = tiktoken.get_encoding(enc_name)
    except Exception as e:  # pragma: no cover
        raise ValueError(f"tokenizer {name!r} unavailable: {e}") from None
    return lambda s: len(enc.encode(s))
