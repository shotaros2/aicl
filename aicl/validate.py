"""Structural validation of messages and protocol validation of conversations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Set

from .model import (
    ACTS, BODY_REQUIRED, CORE_HEADS, FAIL_CODES, REASON_REQUIRED, REPLY_REQUIRED, SELF_REPLY,
    STATUS_VALUES, Form, KList, KMap, Message, ModelError, Ref, Str, Symbol, Var, walk,
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


def _is_ref_form(t) -> bool:
    return isinstance(t, Form) and t.head == "ref" and len(t.args) == 1 and isinstance(t.args[0], Ref)


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
            if t.head == "status":
                if len(t.args) < 1 or not _is_ref_form(t.args[0]):
                    issues.append(_err("status-shape", "(status …) must be (status (ref #id) $s)", mid))
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


def _pair(a: str, b: str) -> FrozenSet[str]:
    return frozenset((a, b))


def validate_conversation(messages: Iterable[Message], known_terms: Iterable[str] = ()) -> List[Issue]:
    """Check protocol rules across a whole exchange (SPEC §4.4, §6)."""
    msgs = list(messages)
    issues: List[Issue] = []
    shared: Set[str] = set(known_terms)                 # pre-agreed terms and broadcast defs
    pair_known: Dict[FrozenSet[str], Set[str]] = {}     # defs agreed between two agents
    seen: Dict[str, Message] = {}
    open_asks: Dict[str, Message] = {}
    pending_do: Dict[str, str] = {}                     # id -> "sent" | "accepted"
    do_eta: Dict[str, str] = {}                         # do id -> eta promised in ok
    pending_prop: Dict[str, Message] = {}
    closed_prop: Dict[str, str] = {}                    # id -> "acc" | "rej"
    pending_def: Dict[str, tuple] = {}                  # def id -> (term, pair)
    why_targets: Dict[str, str] = {}                    # why id -> id it questions
    status_asks: Set[str] = set()

    for m in msgs:
        issues.extend(validate_message(m.to_form()))
        if m.id in seen:
            issues.append(_err("dup-id", f"message id reused by {seen[m.id].sender}/{m.sender}", m.id))
        seen[m.id] = m

        target = seen.get(m.reply) if m.reply is not None else None
        if m.reply is not None:
            if target is None:
                issues.append(_err("bad-reply", f"^{m.reply} does not refer to an earlier message", m.id))
            elif m.act in SELF_REPLY:
                if target.sender != m.sender:
                    issues.append(_err("bad-reply", f"'{m.act}' must reference the sender's own message, "
                                       f"^{m.reply} was sent by @{target.sender}", m.id))
                elif m.act == "unsub" and target.act != "sub":
                    issues.append(_err("bad-reply", f"^{m.reply} is not a 'sub'", m.id))
            elif target.sender != m.receiver and target.receiver != "*":
                issues.append(_err("bad-reply", f"^{m.reply} was not sent by @{m.receiver}", m.id))

        known = set(shared)
        if m.receiver != "*":
            known |= pair_known.get(_pair(m.sender, m.receiver), set())
        # Evidence under :src names data sources, not vocabulary: it is not subject to resolution.
        checked = Form(m.act, list(m.body), {k: v for k, v in m.kw.items() if k != "src"})
        for u in sorted(unresolved_terms(checked, known)):
            if m.act == "def" and m.body and isinstance(m.body[0], Symbol) and u == m.body[0].name:
                continue
            issues.append(_warn("unresolved-term", f"'{u}' is not core, namespaced, or defined for this pair", m.id))

        act, r = m.act, m.reply
        if act == "ask":
            open_asks[m.id] = m
            if m.body and isinstance(m.body[0], Form) and m.body[0].head == "status":
                status_asks.add(m.id)
        elif act == "do":
            pending_do[m.id] = "sent"
        elif act == "prop":
            pending_prop[m.id] = m
        elif act == "def" and m.body and isinstance(m.body[0], Symbol):
            if m.receiver == "*":
                shared.add(m.body[0].name)                 # a broadcast def is shared at once
            else:
                pending_def[m.id] = (m.body[0].name, _pair(m.sender, m.receiver))
        elif act == "why":
            if target is not None:
                why_targets[m.id] = target.id
        elif act == "tell":
            if r in open_asks:
                if r in status_asks:
                    vals = [v for b in m.body if isinstance(b, KMap) for _, v in b.items]
                    if not vals or not all(isinstance(v, Symbol) and v.name in STATUS_VALUES for v in vals):
                        issues.append(_warn("status-value", "answer to (status …) should be one of "
                                            + " ".join(sorted(STATUS_VALUES)), m.id))
                del open_asks[r]
            if r in why_targets and "src" not in m.kw:
                issues.append(_err("why-needs-src", "an answer to 'why' must carry :src (structured evidence or (none))", m.id))
        elif act == "ok":
            if r in pending_do:
                pending_do[r] = "accepted"
                if "eta" in m.kw:
                    do_eta[r] = to_text(m.kw["eta"])
            elif r in pending_def:
                term, pair = pending_def.pop(r)
                pair_known.setdefault(pair, set()).add(term)
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
                                   "retract that decision first or send a new prop", m.id))
            elif r in pending_prop:
                del pending_prop[r]
                closed_prop[r] = act
        elif act == "retract" and target is not None and target.sender == m.sender:
            # Reopen whatever the retracted message had closed.
            t, tr = target.act, target.reply
            if t in ("acc", "rej") and tr in closed_prop:
                del closed_prop[tr]
                if tr in seen:
                    pending_prop[tr] = seen[tr]
            elif t in ("done", "fail") and tr in seen and seen[tr].act == "do":
                pending_do[tr] = "accepted"
            elif t == "ok" and tr in seen and seen[tr].act == "do":
                pending_do[tr] = "sent"
            elif t == "tell" and tr in seen and seen[tr].act == "ask":
                open_asks[tr] = seen[tr]
            elif t in ("prop",):
                pending_prop.pop(target.id, None)
                closed_prop.pop(target.id, None)
            elif t in ("ask", "do"):
                open_asks.pop(target.id, None)
                pending_do.pop(target.id, None)

    for mid in open_asks:
        issues.append(_warn("open-ask", "ask was never answered (tell/no/fail)", mid))
    for mid, state in pending_do.items():
        eta = f", eta {do_eta[mid]} promised" if mid in do_eta else ""
        issues.append(_warn("open-do", f"do was never closed (state: {state}{eta})", mid))
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
