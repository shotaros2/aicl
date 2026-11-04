"""Tokenizer for the Koine text encoding."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Union

from .model import (
    Agent, Date, Duration, Instant, Keyword, LexError, Quantity, Ref,
    ReplyRef, Route, Str, Symbol, Var,
)

IDENT = r"[A-Za-z0-9_][A-Za-z0-9_.:/-]*"
NUMBER = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"

_TOKEN = re.compile(
    r"""(?P<ws>\s+)
      | (?P<comment>;[^\n]*)
      | (?P<punct>[()\[\]{}])
      | (?P<str>"(?:[^"\\\n]|\\.)*")
      | (?P<atom>[^\s()\[\]{}";]+)
    """,
    re.X,
)

RE_ROUTE = re.compile(rf"^@({IDENT})>(?:@({IDENT})|(\*))$")
RE_AGENT = re.compile(rf"^@({IDENT})$")
RE_REF = re.compile(rf"^#({IDENT})$")
RE_REPLY = re.compile(rf"^\^({IDENT})$")
RE_VAR = re.compile(rf"^\$({IDENT})$")
RE_KEYWORD = re.compile(rf"^:({IDENT})$")
RE_CONF = re.compile(r"^~(0(?:\.\d+)?|1(?:\.0+)?)$")
RE_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_DURATION = re.compile(
    r"^P(?!$)(?:\d+Y)?(?:\d+M)?(?:\d+W)?(?:\d+D)?(?:T(?=\d)(?:\d+H)?(?:\d+M)?(?:\d+(?:\.\d+)?S)?)?$"
)
RE_NUMBER = re.compile(rf"^{NUMBER}$")
RE_QUANTITY = re.compile(rf"^(?P<num>{NUMBER})(?P<unit>[A-Za-z%][A-Za-z0-9/^%]*)$")
RE_SYMBOL = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_.:/-]*|=|!=|<|<=|>|>=)$")


@dataclass(frozen=True)
class ConfTok:
    value: float


@dataclass(frozen=True)
class Punct:
    char: str


@dataclass(frozen=True)
class Token:
    value: object
    line: int
    col: int


def parse_number(text: str) -> Union[int, float]:
    if re.fullmatch(r"[+-]?\d+", text):
        return int(text)
    v = float(text)
    if v != v or v in (float("inf"), float("-inf")):
        raise LexError(f"non-finite number {text!r}")
    return v


def normalize_instant(text: str) -> str:
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as e:
        raise LexError(f"invalid instant {text!r}: {e}") from None
    if dt.tzinfo is None:
        raise LexError(f"instant {text!r} has no timezone offset")
    off = dt.utcoffset()
    total = int(off.total_seconds())
    base = dt.strftime("%Y-%m-%dT%H:%M")
    if dt.second or dt.microsecond:
        base += f":{dt.second:02d}"
    if dt.microsecond:
        base += "." + f"{dt.microsecond:06d}".rstrip("0")
    if total == 0:
        return base + "Z"
    sign = "+" if total > 0 else "-"
    total = abs(total)
    return f"{base}{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def classify_atom(text: str):
    """Turn a bare token into a model atom (or ConfTok)."""
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "null":
        return None
    m = RE_ROUTE.match(text)
    if m:
        return Route(m.group(1), m.group(2) or "*")
    m = RE_AGENT.match(text)
    if m:
        return Agent(m.group(1))
    m = RE_REF.match(text)
    if m:
        return Ref(m.group(1))
    m = RE_REPLY.match(text)
    if m:
        return ReplyRef(m.group(1))
    m = RE_VAR.match(text)
    if m:
        return Var(m.group(1))
    m = RE_KEYWORD.match(text)
    if m:
        return Keyword(m.group(1))
    m = RE_CONF.match(text)
    if m:
        return ConfTok(float(m.group(1)))
    if RE_INSTANT.match(text):
        return Instant(normalize_instant(text))
    if RE_DATE.match(text):
        try:
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            raise LexError(f"invalid date {text!r}") from None
        return Date(text)
    if RE_DURATION.match(text):
        return Duration(text)
    if RE_NUMBER.match(text):
        return parse_number(text)
    m = RE_QUANTITY.match(text)
    if m:
        return Quantity(parse_number(m.group("num")), m.group("unit"))
    if RE_SYMBOL.match(text):
        return Symbol(text)
    raise LexError(f"invalid token {text!r}")


def unescape_string(raw: str) -> str:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise LexError(f"invalid string literal {raw!r}: {e.msg}") from None


def tokenize(text: str) -> Iterator[Token]:
    pos = 0
    line = 1
    line_start = 0
    n = len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            raise LexError(f"unexpected character {text[pos]!r} at {line}:{pos - line_start + 1}")
        kind = m.lastgroup
        raw = m.group()
        col = pos - line_start + 1
        if kind == "ws":
            nl = raw.count("\n")
            if nl:
                line += nl
                line_start = pos + raw.rfind("\n") + 1
        elif kind == "comment":
            pass
        elif kind == "punct":
            yield Token(Punct(raw), line, col)
        elif kind == "str":
            yield Token(Str(unescape_string(raw)), line, col)
        else:
            try:
                yield Token(classify_atom(raw), line, col)
            except LexError as e:
                raise LexError(f"{e} at {line}:{col}") from None
        pos = m.end()
