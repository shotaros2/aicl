"""Canonical and pretty text printers."""
from __future__ import annotations

import hashlib
import json
import math

from .model import (
    Agent, Date, Duration, Form, Instant, Keyword, KList, KMap, Message,
    ModelError, Quantity, Ref, ReplyRef, Route, Str, Symbol, Term, Var, is_message,
)


def fmt_number(x) -> str:
    if isinstance(x, bool):
        raise TypeError("bool is not a number")
    if isinstance(x, int):
        return str(x)
    if math.isnan(x) or math.isinf(x):
        raise ModelError("non-finite number")
    if x == 0:
        return "0"
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return repr(x).replace("e+", "e")


def fmt_conf(c: float) -> str:
    if not 0.0 <= c <= 1.0:
        raise ModelError(f"confidence {c} outside [0,1]")
    if c == 1.0:
        return "~1.0"
    return "~" + repr(float(c))


def fmt_string(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def fmt_atom(t: Term) -> str:
    if t is True:
        return "true"
    if t is False:
        return "false"
    if t is None:
        return "null"
    if isinstance(t, (int, float)):
        return fmt_number(t)
    if isinstance(t, Symbol):
        return t.name
    if isinstance(t, Keyword):
        return ":" + t.name
    if isinstance(t, Agent):
        return "@" + t.name
    if isinstance(t, Route):
        return f"@{t.src}>" + ("*" if t.dst == "*" else "@" + t.dst)
    if isinstance(t, Ref):
        return "#" + t.name
    if isinstance(t, ReplyRef):
        return "^" + t.name
    if isinstance(t, Var):
        return "$" + t.name
    if isinstance(t, Quantity):
        return fmt_number(t.value) + t.unit
    if isinstance(t, (Instant, Date, Duration)):
        return t.text
    if isinstance(t, Str):
        return fmt_string(t.text)
    raise TypeError(f"not an atom: {t!r}")


def _normalize(term: Term) -> Term:
    """Return a copy with message heads reordered (act #id route ^reply body…)."""
    if is_message(term):
        return Message.from_form(term).to_form()
    return term


def to_text(term: Term) -> str:
    """Canonical single-line text (SPEC §7)."""
    term = _normalize(term)
    if isinstance(term, Form):
        parts = [term.head]
        parts += [to_text(a) for a in term.args]
        for k in sorted(term.kw):
            parts.append(":" + k)
            parts.append(to_text(term.kw[k]))
        if term.conf is not None:
            parts.append(fmt_conf(term.conf))
        return "(" + " ".join(parts) + ")"
    if isinstance(term, KList):
        return "[" + " ".join(to_text(a) for a in term.items) + "]"
    if isinstance(term, KMap):
        pairs = sorted(((to_text(k), to_text(v)) for k, v in term.items), key=lambda p: p[0])
        return "{" + " ".join(f"{k} {v}" for k, v in pairs) + "}"
    return fmt_atom(term)


def canonical(term: Term) -> str:
    return to_text(term)


def canonical_document(terms) -> str:
    return "\n".join(to_text(t) for t in terms) + "\n"


def digest(term: Term) -> str:
    """SHA-256 hex digest of the canonical text."""
    return hashlib.sha256(to_text(term).encode("utf-8")).hexdigest()


def pretty(term: Term, indent: int = 0, width: int = 72) -> str:
    """Human-oriented multi-line layout; semantically identical to canonical."""
    flat = to_text(term)
    pad = "  " * indent
    if len(flat) + len(pad) <= width or not isinstance(term, (Form, KList, KMap)):
        return pad + flat
    term = _normalize(term)
    if isinstance(term, Form):
        head_atoms = [term.head]
        rest = list(term.args)
        while rest and not isinstance(rest[0], (Form, KList, KMap)):
            head_atoms.append(to_text(rest.pop(0)))
        lines = [pad + "(" + " ".join(head_atoms)]
        for a in rest:
            lines.append(pretty(a, indent + 1, width))
        for k in sorted(term.kw):
            v = term.kw[k]
            if isinstance(v, (Form, KList, KMap)) and len(to_text(v)) > width // 2:
                lines.append(pad + "  :" + k)
                lines.append(pretty(v, indent + 2, width))
            else:
                lines.append(pad + "  :" + k + " " + to_text(v))
        if term.conf is not None:
            lines.append(pad + "  " + fmt_conf(term.conf))
        lines[-1] += ")"
        return "\n".join(lines)
    if isinstance(term, KList):
        lines = [pad + "["] + [pretty(a, indent + 1, width) for a in term.items]
        lines[-1] += "]"
        return "\n".join(lines)
    pairs = sorted(((to_text(k), v) for k, v in term.items), key=lambda p: p[0])
    lines = [pad + "{"] + [pad + "  " + k + " " + to_text(v) for k, v in pairs]
    lines[-1] += "}"
    return "\n".join(lines)
