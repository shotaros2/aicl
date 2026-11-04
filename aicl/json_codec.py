"""JSON encoding of AICL terms (SPEC §8)."""
from __future__ import annotations

import json

from .lexer import classify_atom, ConfTok
from .model import (
    Agent, Date, Duration, Form, Instant, Keyword, KList, KMap, ModelError,
    Quantity, Ref, ReplyRef, Route, Str, Symbol, Term, Var,
)
from .printer import fmt_atom, _normalize


def to_json(term: Term):
    """Convert a term to a JSON-compatible Python object."""
    term = _normalize(term)
    if isinstance(term, Form):
        obj = {"f": term.head, "a": [to_json(a) for a in term.args]}
        if term.kw:
            obj["k"] = {k: to_json(v) for k, v in term.kw.items()}
        if term.conf is not None:
            obj["c"] = term.conf
        return obj
    if isinstance(term, KList):
        return [to_json(a) for a in term.items]
    if isinstance(term, KMap):
        return {"map": [[to_json(k), to_json(v)] for k, v in term.items]}
    if isinstance(term, Quantity):
        return {"q": term.value, "u": term.unit}
    if isinstance(term, Instant):
        return {"t": term.text}
    if isinstance(term, Date):
        return {"d": term.text}
    if isinstance(term, Duration):
        return {"dur": term.text}
    if isinstance(term, Str):
        return {"s": term.text}
    if term is None or isinstance(term, (bool, int, float)):
        return term
    if isinstance(term, (Symbol, Keyword, Agent, Route, Ref, ReplyRef, Var)):
        return fmt_atom(term)
    raise TypeError(f"cannot encode {term!r}")


def from_json(obj) -> Term:
    """Convert a JSON-compatible object back into a term."""
    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, str):
        atom = classify_atom(obj)
        if isinstance(atom, ConfTok):
            raise ModelError(f"confidence marker {obj!r} is not a value")
        return atom
    if isinstance(obj, list):
        return KList([from_json(a) for a in obj])
    if not isinstance(obj, dict):
        raise ModelError(f"cannot decode {obj!r}")
    keys = set(obj)
    if "f" in keys:
        if not isinstance(obj["f"], str):
            raise ModelError("form head must be a string")
        form = Form(obj["f"])
        form.args = [from_json(a) for a in obj.get("a", [])]
        form.kw = {k: from_json(v) for k, v in obj.get("k", {}).items()}
        if "c" in obj:
            c = obj["c"]
            if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0 <= c <= 1:
                raise ModelError(f"invalid confidence {c!r}")
            form.conf = float(c)
        return form
    if keys == {"map"}:
        return KMap([(from_json(k), from_json(v)) for k, v in obj["map"]])
    if keys == {"q", "u"}:
        return Quantity(obj["q"], obj["u"])
    if keys == {"t"}:
        atom = classify_atom(obj["t"])
        if not isinstance(atom, Instant):
            raise ModelError(f"invalid instant {obj['t']!r}")
        return atom
    if keys == {"d"}:
        atom = classify_atom(obj["d"])
        if not isinstance(atom, Date):
            raise ModelError(f"invalid date {obj['d']!r}")
        return atom
    if keys == {"dur"}:
        atom = classify_atom(obj["dur"])
        if not isinstance(atom, Duration):
            raise ModelError(f"invalid duration {obj['dur']!r}")
        return atom
    if keys == {"s"}:
        return Str(obj["s"])
    raise ModelError(f"unrecognised JSON object with keys {sorted(keys)}")


def dumps(term: Term) -> str:
    """Canonical JSON text: sorted keys, no whitespace, UTF-8."""
    return json.dumps(to_json(term), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def loads(text: str) -> Term:
    return from_json(json.loads(text))
