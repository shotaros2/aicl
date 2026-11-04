"""Structural validation of messages and protocol validation of conversations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Set

from .model import (
    ACTS, BODY_REQUIRED, CORE_HEADS, FAIL_CODES, REASON_REQUIRED, REPLY_REQUIRED,
    Form, KList, KMap, Message, ModelError, Str, Symbol, Var, walk,
)
from .printer import to_text


@dataclass
class Issue:
    level: str          # "error" | "warning"
    code: str
    message: str
    msg_id: Optional[str] = None

    def __str__(self) -> str:
        where = f" [#{self.msg_id}]" if self.msg_id else ""
        return f"{self.level}{where} {self.code}: {self.message}"


def _err(code, msg, mid=None) -> Issue:
    return Issue("error", code, msg, mid)


def _warn(code, msg, mid=None) -> Issue:
    return Issue("warning", code, msg, mid)


def validate_message(form: Form) -> List[Issue]:
    """Check one message in isolation (SPEC §3, §4)."""
    issues: List[Issue] = []
    try:
        m = Message.from_form(form)
    except ModelError as e:
        return [_err("structure", str(e))]
    mid = m.id
    if m.act in REPLY_REQUIRED and m.reply is None:
        issues.append(_err("reply-required", f"'{m.act}' must carry ^reply", mid))
    if m.act in BODY_REQUIRED and not m.body:
        issues.append(_err("body-required", f"'{m.act}' needs a body", mid))
    if m.act in REASON_REQUIRED and "why" not in m.kw:
        issues.append(_err("why-required", f"'{m.act}' must give :why", mid))
    if m.act == "fail":
        code = m.kw.get("code")
        if not isinstance(code, Symbol):
            issues.append(_err("code-required", "'fail' must give :code", mid))
        elif code.name not in FAIL_CODES:
            issues.append(_warn("unknown-code", f"non-standard fail code '{code.name}'", mid))
    if m.act == "tell":
        binding_keys = {id(k) for b in m.body for t in walk(b) if isinstance(t, KMap) for k, _ in t.items}
        if any(isinstance(t, Var) and id(t) not in binding_keys for b in m.body for t in walk(b)):
            issues.append(_err("var-in-tell", "'tell' may contain $variables only as binding-map keys", mid))
    if m.act == "sub" and not any(isinstance(t, Var) for b in m.body for t in walk(b)):
        issues.append(_warn("sub-without-var", "'sub' pattern has no $variables", mid))
    if m.act == "def":
        if not m.body or not isinstance(m.body[0], Symbol):
            issues.append(_err("def-term", "'def' body must start with the symbol being defined", mid))
        if "gloss" not in m.kw and "uri" not in m.kw:
            issues.append(_err("def-gloss", "'def' needs :gloss (nl …) or :uri", mid))
    if m.act == "clar":
        heads = {b.head for b in m.body if isinstance(b, Form)}
        if not heads & {"amb", "unk", "parse"}:
            issues.append(_err("clar-body", "'clar' body must be (amb …), (unk …) or (parse …)", mid))
    if m.conf is not None and not 0.0 <= m.conf <= 1.0:
        issues.append(_err("conf-range", "confidence outside [0,1]", mid))
    for t in walk(form):
        if isinstance(t, Form):
            if t.conf is not None and not 0.0 <= t.conf <= 1.0:
                issues.append(_err("conf-range", "confidence outside [0,1]", mid))
            if t.head == "nl":
                if (len(t.args) != 2 or not isinstance(t.args[0], Symbol)
                        or not isinstance(t.args[1], Str)):
                    issues.append(_err("nl-shape", "(nl …) must be (nl <lang> \"text\")", mid))
            if t.head in ACTS and t is not form:
                issues.append(_err("nested-act", f"speech act '{t.head}' nested inside a message", mid))
    return issues


def unresolved_terms(form: Form, known: Set[str]) -> Set[str]:
    """Heads that are neither core, namespaced, nor in `known`."""
    out = set()
    for t in walk(form):
        if isinstance(t, Form) and t.head not in CORE_HEADS and ":" not in t.head and t.head not in known:
            out.add(t.head)
    return out


def validate_conversation(messages: Iterable[Message], known_terms: Iterable[str] = ()) -> List[Issue]:
    """Check protocol rules across a whole exchange (SPEC §4.4, §6)."""
    msgs = list(messages)
    issues: List[Issue] = []
    known: Set[str] = set(known_terms)
    seen = {}               # id -> Message
    open_asks = {}          # id -> Message
    pending_do = {}         # id -> state: "sent" | "accepted"
    pending_prop = {}
    closed_prop = {}        # id -> act that closed it ("acc" | "rej")
    pending_def = {}        # id -> term
    for m in msgs:
        issues.extend(validate_message(m.to_form()))
        if m.id in seen:
            issues.append(_err("dup-id", f"message id reused by {seen[m.id].sender}/{m.sender}", m.id))
        seen[m.id] = m
        if m.reply is not None:
            target = seen.get(m.reply)
            if target is None:
                issues.append(_err("bad-reply", f"^{m.reply} does not refer to an earlier message", m.id))
            elif m.act == "unsub":
                if target.sender != m.sender or target.act != "sub":
                    issues.append(_err("bad-reply", f"^{m.reply} is not a 'sub' sent by @{m.sender}", m.id))
            elif target.sender != m.receiver and target.receiver != "*":
                issues.append(_err("bad-reply", f"^{m.reply} was not sent by @{m.receiver}", m.id))
        for u in sorted(unresolved_terms(m.to_form(), known)):
            if m.act == "def" and m.body and isinstance(m.body[0], Symbol) and u == m.body[0].name:
                continue
            issues.append(_warn("unresolved-term", f"'{u}' is not core, namespaced, or defined", m.id))

        act, r = m.act, m.reply
        if act == "ask":
            open_asks[m.id] = m
        elif act == "do":
            pending_do[m.id] = "sent"
        elif act == "prop":
            pending_prop[m.id] = m
        elif act == "def" and m.body and isinstance(m.body[0], Symbol):
            pending_def[m.id] = m.body[0].name
        elif act == "tell" and r in open_asks:
            del open_asks[r]
        elif act == "ok":
            if r in pending_do:
                pending_do[r] = "accepted"
            elif r in pending_def:
                known.add(pending_def.pop(r))
        elif act == "no":
            open_asks.pop(r, None)
            pending_do.pop(r, None)
            pending_def.pop(r, None)
        elif act == "clar":
            open_asks.pop(r, None)
            pending_do.pop(r, None)
        elif act in ("done", "fail"):
            if r in pending_do:
                if act == "done" and pending_do[r] != "accepted":
                    issues.append(_err("done-without-ok", f"'done' for ^{r} without a prior 'ok'", m.id))
                del pending_do[r]
            elif r in open_asks:
                if act == "fail":
                    del open_asks[r]
                else:
                    issues.append(_err("done-for-ask", "'done' answers an 'ask'; use 'tell'", m.id))
        elif act in ("acc", "rej"):
            if r in closed_prop:
                issues.append(_err("prop-closed", f"proposal ^{r} was already closed by '{closed_prop[r]}'; "
                                   "a decision cannot be reversed by a second acc/rej (send a new prop)", m.id))
            elif r in pending_prop:
                del pending_prop[r]
                closed_prop[r] = act
    for mid in open_asks:
        issues.append(_warn("open-ask", "ask was never answered (tell/no/fail)", mid))
    for mid, state in pending_do.items():
        issues.append(_warn("open-do", f"do was never closed (state: {state})", mid))
    for mid in pending_prop:
        issues.append(_warn("open-prop", "proposal was never accepted or rejected", mid))
    return issues


def nl_ratio(messages: Iterable[Message]) -> float:
    """Fraction of body text (in canonical chars) that sits inside (nl …) forms."""
    total = nl = 0
    for m in messages:
        for b in m.body:
            total += len(to_text(b))
            for t in walk(b):
                if isinstance(t, Form) and t.head == "nl":
                    nl += len(to_text(t))
    return nl / total if total else 0.0
