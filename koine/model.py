"""Abstract data model for Koine terms and messages."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union


class KoineError(Exception):
    """Base class for all Koine errors."""


class LexError(KoineError):
    """Invalid token."""


class ParseError(KoineError):
    """Invalid structure."""


class ModelError(KoineError):
    """A term is not a valid message or violates the data model."""


# --------------------------------------------------------------------------- atoms

@dataclass(frozen=True)
class Symbol:
    name: str


@dataclass(frozen=True)
class Keyword:
    name: str


@dataclass(frozen=True)
class Agent:
    name: str


@dataclass(frozen=True)
class Route:
    src: str
    dst: str  # "*" means broadcast


@dataclass(frozen=True)
class Ref:
    name: str


@dataclass(frozen=True)
class ReplyRef:
    name: str


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Quantity:
    value: Union[int, float]
    unit: str


@dataclass(frozen=True)
class Instant:
    text: str  # canonical ISO 8601 with offset


@dataclass(frozen=True)
class Date:
    text: str


@dataclass(frozen=True)
class Duration:
    text: str


@dataclass(frozen=True)
class Str:
    text: str


# ----------------------------------------------------------------------- compounds

@dataclass
class KList:
    items: list = field(default_factory=list)


@dataclass
class KMap:
    items: list = field(default_factory=list)  # list of (key, value) pairs


@dataclass
class Form:
    head: str
    args: list = field(default_factory=list)
    kw: dict = field(default_factory=dict)
    conf: Optional[float] = None


Term = Any  # Union of the classes above plus int, float, bool, None


# ------------------------------------------------------------------- vocabulary

ACTS = frozenset({
    "ask", "tell", "do", "ok", "no", "done", "fail",
    "prop", "acc", "rej", "def", "clar", "why", "sub", "unsub", "end",
})

REPLY_REQUIRED = frozenset({"ok", "no", "done", "fail", "acc", "rej", "why", "clar", "unsub"})
REASON_REQUIRED = frozenset({"no", "rej", "fail"})
BODY_REQUIRED = frozenset({"ask", "tell", "do", "prop", "def", "clar", "sub"})

FAIL_CODES = frozenset({
    "parse", "unknown-term", "unsupported", "timeout", "denied",
    "not-found", "conflict", "limit", "internal",
})

CORE_HEADS = frozenset({
    "and", "or", "not", "if", "all", "some",
    "=", "!=", "<", "<=", ">", ">=", "in", "count",
    "none", "nl", "amb", "unk", "ref", "tokenizer", "codebook",
}) | ACTS

HEAD_KEYS = ("conv", "at", "src", "why", "code", "eta", "if")


# --------------------------------------------------------------------- message

@dataclass
class Message:
    act: str
    id: str
    route: Route
    reply: Optional[str] = None
    body: list = field(default_factory=list)
    kw: dict = field(default_factory=dict)
    conf: Optional[float] = None

    @classmethod
    def from_form(cls, form: Form) -> "Message":
        if not isinstance(form, Form):
            raise ModelError("a message must be a form")
        if form.head not in ACTS:
            raise ModelError(f"unknown speech act '{form.head}'")
        mid = route = reply = None
        body: list = []
        for a in form.args:
            if isinstance(a, Ref) and mid is None:
                mid = a.name
            elif isinstance(a, Route) and route is None:
                route = a
            elif isinstance(a, ReplyRef) and reply is None:
                reply = a.name
            else:
                body.append(a)
        if mid is None:
            raise ModelError(f"({form.head} …) has no message id (#id)")
        if route is None:
            raise ModelError(f"({form.head} #{mid} …) has no route (@from>@to)")
        return cls(form.head, mid, route, reply, body, dict(form.kw), form.conf)

    def to_form(self) -> Form:
        args: list = [Ref(self.id), self.route]
        if self.reply is not None:
            args.append(ReplyRef(self.reply))
        args.extend(self.body)
        return Form(self.act, args, dict(self.kw), self.conf)

    @property
    def sender(self) -> str:
        return self.route.src

    @property
    def receiver(self) -> str:
        return self.route.dst


def is_message(term: Term) -> bool:
    return isinstance(term, Form) and term.head in ACTS


def walk(term: Term):
    """Yield every sub-term, depth first, including the term itself."""
    yield term
    if isinstance(term, Form):
        for a in term.args:
            yield from walk(a)
        for v in term.kw.values():
            yield from walk(v)
    elif isinstance(term, KList):
        for a in term.items:
            yield from walk(a)
    elif isinstance(term, KMap):
        for k, v in term.items:
            yield from walk(k)
            yield from walk(v)
