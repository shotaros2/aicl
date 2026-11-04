"""Dense text encoding (SPEC §8): the same messages, tuned for BPE tokenizers.

Readable:  (tell #b.1 @b>@a ^a.1 {$t 18.5C} ~0.9 :src jma :at 2026-11-05T09:00+09:00)
Dense:     (T b.1>a ^a.1 {$t 18.5C} :a 20261105T0900+9 :s jma ~0.9)

The mapping is bijective and purely lexical, so `from_dense(to_dense(t))` has the
same canonical form as `t`. Humans should run `aicl fmt` on it rather than read it.
"""
from __future__ import annotations

import re
from datetime import datetime

from .lexer import _TOKEN, IDENT, normalize_instant
from .model import (
    ACTS, Form, Instant, Keyword, KList, KMap, LexError, Message, ModelError,
    Ref, ReplyRef, Route, Term,
)
from .parser import parse
from .printer import fmt_atom, fmt_conf, _normalize

ACT_CODE = {
    "ask": "A", "tell": "T", "do": "D", "ok": "K", "no": "N", "done": "Z", "fail": "F",
    "prop": "P", "acc": "C", "rej": "R", "def": "E", "clar": "Q", "why": "W",
    "sub": "S", "unsub": "U", "end": "X", "retract": "B",   # B: take Back
}
CODE_ACT = {v: k for k, v in ACT_CODE.items()}
assert set(ACT_CODE) == ACTS

KEY_CODE = {
    "at": "a", "by": "b", "conv": "c", "code": "e", "gloss": "g", "if": "i", "args": "r",
    "src": "s", "eta": "t", "unit": "u", "ret": "v", "why": "w",
}
CODE_KEY = {v: k for k, v in KEY_CODE.items()}

RE_DENSE_HEADER = re.compile(rf"^({IDENT})>@?(\*|{IDENT})$")   # a.1>b canonical; a.1>@b accepted on input
RE_DENSE_INSTANT = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})?(Z|[+-]\d{1,4})$")


# ----------------------------------------------------------------- instants
#
# ISO 8601 *basic* format, which an LLM can read and write as easily as the
# extended form but which tokenizes to about half as many tokens:
#   2026-11-06T10:00+09:00  ->  20261106T1000+9
#   2026-11-04T09:04:12Z    ->  20261104T090412Z
# Offsets: 1-2 digits = hours, 3-4 digits = HHMM. Fractional seconds keep the extended form.

def encode_instant(text: str) -> str:
    dt = datetime.fromisoformat(text)
    if dt.microsecond:
        return text
    out = dt.strftime("%Y%m%dT%H%M")
    if dt.second:
        out += f"{dt.second:02d}"
    off = int(dt.utcoffset().total_seconds())
    if off == 0:
        return out + "Z"
    h, m = divmod(abs(off) // 60, 60)
    return out + ("+" if off > 0 else "-") + str(h) + (f"{m:02d}" if m else "")


def decode_instant(tok: str) -> str:
    m = RE_DENSE_INSTANT.match(tok)
    if not m:
        raise LexError(f"invalid dense instant {tok!r}")
    y, mo, d, hh, mi, ss, off = m.groups()
    if off == "Z":
        iso_off = "+00:00"
    else:
        digits = off[1:]
        h, mm = (int(digits), 0) if len(digits) <= 2 else (int(digits[:-2]), int(digits[-2:]))
        iso_off = f"{off[0]}{h:02d}:{mm:02d}"
    return normalize_instant(f"{y}-{mo}-{d}T{hh}:{mi}:{ss or '00'}{iso_off}")


# ------------------------------------------------------------------ encoder

def to_dense(term: Term) -> str:
    term = _normalize(term)
    if isinstance(term, Form):
        if term.head in ACT_CODE:
            try:
                return _dense_message(term)
            except ModelError:
                return _dense_form(term.head, term)   # act-headed ordinary term, e.g. nested (done …)
        return _dense_form(term.head, term)
    if isinstance(term, KList):
        return "[" + " ".join(to_dense(a) for a in term.items) + "]"
    if isinstance(term, KMap):
        pairs = sorted(((to_dense(k), to_dense(v)) for k, v in term.items), key=lambda p: p[0])
        return "{" + " ".join(f"{k} {v}" for k, v in pairs) + "}"
    if isinstance(term, Instant):
        return encode_instant(term.text)
    return fmt_atom(term)


def _dense_tail(form: Form) -> list:
    parts = []
    for k in sorted(form.kw):
        parts.append(":" + KEY_CODE.get(k, k))
        parts.append(to_dense(form.kw[k]))
    if form.conf is not None:
        parts.append(fmt_conf(form.conf))
    return parts


def _dense_form(head: str, form: Form) -> str:
    if head in CODE_ACT or (len(head) == 1 and head.isupper()):
        raise ModelError(f"head '{head}' is reserved for dense act codes")
    return "(" + " ".join([head] + [to_dense(a) for a in form.args] + _dense_tail(form)) + ")"


def _dense_message(form: Form) -> str:
    m = Message.from_form(form)
    parts = [ACT_CODE[m.act]]
    prefix = m.id.split(".", 1)[0]
    if "." in m.id and prefix == m.route.src:
        parts.append(f"{m.id}>{m.route.dst}")
    else:
        parts += [fmt_atom(Ref(m.id)), fmt_atom(m.route)]
    if m.reply is not None:
        parts.append(fmt_atom(ReplyRef(m.reply)))
    parts += [to_dense(a) for a in m.body]
    parts += _dense_tail(form)
    return "(" + " ".join(parts) + ")"


def dense_document(terms) -> str:
    return "\n".join(to_dense(t) for t in terms) + "\n"


# ------------------------------------------------------------------ decoder

def expand(text: str) -> str:
    """Rewrite dense tokens to readable ones; the result parses with the normal parser."""
    out = []
    after_open = False
    for m in _TOKEN.finditer(text):
        kind, raw = m.lastgroup, m.group()
        if kind in ("ws", "comment"):
            continue
        if kind == "punct":
            out.append(raw)
            after_open = raw == "("
            continue
        if kind == "str":
            out.append(raw)
        elif after_open and raw in CODE_ACT:
            out.append(CODE_ACT[raw])
        elif RE_DENSE_INSTANT.match(raw):
            out.append(decode_instant(raw))
        elif raw.startswith(":") and raw[1:] in CODE_KEY:
            out.append(":" + CODE_KEY[raw[1:]])
        elif ">" in raw and raw[0] not in "@<>=!#^$:~" and RE_DENSE_HEADER.match(raw):
            mm = RE_DENSE_HEADER.match(raw)
            mid, dst = mm.group(1), mm.group(2)
            src = mid.split(".", 1)[0]
            out.append("#" + mid)
            out.append(f"@{src}>" + ("*" if dst == "*" else "@" + dst))
        else:
            out.append(raw)
        after_open = False
    return " ".join(out)


def from_dense(text: str):
    """Parse a dense document into terms."""
    return parse(expand(text))


def looks_dense(text: str) -> bool:
    """Cheap sniff used by the CLI: any dense header or instant token present."""
    for m in _TOKEN.finditer(text):
        if m.lastgroup == "atom":
            raw = m.group()
            if RE_DENSE_INSTANT.match(raw) or (">" in raw and RE_DENSE_HEADER.match(raw)):
                return True
    return False
