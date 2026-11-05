"""Structural validation of messages and protocol validation of conversations."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, FrozenSet, Iterable, List, Optional, Set

from .model import (
    ACTS, Agent, BODY_REQUIRED, CORE_HEADS, Date, FAIL_CODES, REASON_REQUIRED, REPLY_REQUIRED,
    SELF_REPLY, STATUS_VALUES, Duration, Form, Instant, KList, KMap, Message, ModelError,
    Quantity, Ref, Str, Symbol, Term, Var, walk,
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


_DURATION = re.compile(r"^P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?$")


def _as_datetime(t) -> Optional[datetime]:
    """An Instant term as an aware datetime, or None."""
    if isinstance(t, Instant):
        try:
            d = datetime.fromisoformat(t.text.replace("Z", "+00:00"))
            return d if d.tzinfo is not None else None
        except ValueError:
            return None
    return None


def _as_timedelta(t) -> Optional[timedelta]:
    """A Duration term as a timedelta, or None."""
    if isinstance(t, Duration):
        m = _DURATION.match(t.text)
        if m and any(m.groups()):
            w, d, h, mi, s = (float(g) if g else 0.0 for g in m.groups())
            return timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)
    return None


def parse_now(text: str) -> datetime:
    """Parse a --now instant; raises ValueError if it is not an aware ISO instant."""
    d = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError(f"'{text}' has no UTC offset")
    return d


# ------------------------------------------------------- typed signatures (SPEC §6.1)

TYPE_NAMES = {"any", "bool", "number", "string", "symbol", "agent", "instant",
              "date", "duration", "qty", "ref", "term"}


def _valid_type(t) -> bool:
    if isinstance(t, Symbol):
        return True                                   # core type name, or a sort name (unchecked)
    if isinstance(t, Form) and not t.kw and t.conf is None and len(t.args) == 1:
        if t.head == "qty":
            return isinstance(t.args[0], Symbol)
        if t.head == "list":
            return _valid_type(t.args[0])
    return False


def parse_signature(m: Message):
    """The typed signature of a def: ([(name, type|None), …] | None, ret | None, error | None)."""
    args = None
    a = m.kw.get("args")
    if a is not None:
        if not isinstance(a, KList):
            return None, None, "':args' must be a list"
        args = []
        for item in a.items:
            if isinstance(item, Symbol):
                args.append((item.name, None))        # untyped parameter name (pre-0.3 form)
            elif (isinstance(item, Form) and not item.kw and item.conf is None
                  and len(item.args) == 1 and _valid_type(item.args[0])):
                args.append((item.head, item.args[0]))
            else:
                return None, None, f"':args' entry {to_text(item)} is not a name or (name type)"
    ret = m.kw.get("ret")
    if ret is not None and not _valid_type(ret):
        return None, None, f"':ret' {to_text(ret)} is not a type"
    return args, ret, None


def _type_ok(v, t) -> Optional[bool]:
    """True/False when the type is checkable; None for a sort name (documentation only)."""
    if isinstance(t, Symbol):
        n = t.name
        if n not in TYPE_NAMES:
            return None
        return {
            "any": True,
            "bool": isinstance(v, bool),
            "number": isinstance(v, (int, float)) and not isinstance(v, bool),
            "string": isinstance(v, Str),
            "symbol": isinstance(v, Symbol),
            "agent": isinstance(v, Agent),
            "instant": isinstance(v, Instant),
            "date": isinstance(v, Date),
            "duration": isinstance(v, Duration),
            "qty": isinstance(v, Quantity),
            "ref": isinstance(v, Ref) or _is_ref_form(v),
            "term": isinstance(v, (Form, KList, KMap)),
        }[n]
    if isinstance(t, Form) and t.head == "qty":
        return isinstance(v, Quantity) and v.unit == t.args[0].name
    if isinstance(t, Form) and t.head == "list":
        if not isinstance(v, KList):
            return False
        return all(_type_ok(i, t.args[0]) is not False for i in v.items)
    return None


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
    if m.act == "ok" and "eta" in m.kw and "at" not in m.kw:
        issues.append(_warn("eta-unanchored", "an ':eta' promise without ':at' cannot be checked "
                            "for overrun or expiry (SPEC §4.2)", mid))
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
        sig_err = parse_signature(m)[2]
        if sig_err is not None:
            issues.append(_err("def-sig", sig_err + " (SPEC §6.1)", mid))
    if m.act == "clar":
        heads = {b.head for b in m.body if isinstance(b, Form)}
        if not heads & {"amb", "unk", "parse"}:
            issues.append(_err("clar-body", "'clar' body must be (amb …), (unk …) or (parse …)", mid))
    if "part" in m.kw:
        p = m.kw["part"]
        if not (m.act in ("tell", "done") and isinstance(p, KList) and len(p.items) == 2
                and all(isinstance(x, int) and not isinstance(x, bool) for x in p.items)
                and 1 <= p.items[0] <= p.items[1]):
            issues.append(_err("part-shape", "':part [i n]' needs two integers 1 <= i <= n, "
                               "on a tell or done (SPEC §4.5)", mid))
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
            if t.head == "blob":
                from .blob import blob_hash
                if blob_hash(t) is None:
                    issues.append(_err("blob-shape", "(blob …) must carry exactly one sha256:<64 hex> "
                                       "argument (SPEC §5.2)", mid))
                else:
                    nb = t.kw.get("bytes")
                    if nb is not None and (isinstance(nb, bool) or not isinstance(nb, int) or nb < 0):
                        issues.append(_err("blob-shape", "(blob …) :bytes must be a non-negative integer", mid))
            if t.head in ACTS and t is not form:
                try:
                    Message.from_form(t)
                except ModelError:
                    pass    # act-named ordinary term, e.g. (done (ref #a.1)) — fine (SPEC §3)
                else:
                    issues.append(_err("nested-act", f"message '{t.head}' nested inside a message", mid))
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


def _part_of(m: Message):
    """(i, n) of a well-shaped ':part [i n]', else None (shape errors are per-message)."""
    p = m.kw.get("part")
    if (isinstance(p, KList) and len(p.items) == 2
            and all(isinstance(x, int) and not isinstance(x, bool) for x in p.items)
            and 1 <= p.items[0] <= p.items[1]):
        return p.items[0], p.items[1]
    return None


def validate_conversation(messages: Iterable[Message], known_terms: Iterable[str] = (),
                          now: Optional[datetime] = None,
                          keys: Optional[Dict[str, str]] = None) -> List[Issue]:
    """Check protocol rules across a whole exchange (SPEC §4.4, §6).

    With `now` (an aware datetime, see `parse_now`), deadlines become checkable:
    an open `do` whose `:by` has passed, or whose promised `:at` + `:eta` has
    elapsed, is flagged.

    With `keys` ({agent name: base64url Ed25519 public key}, SPEC §3.1), identity
    becomes checkable: a message from an agent with a known key must carry a valid
    `:sig` (`sig-missing`, `sig-invalid`); one from an agent without a key is
    flagged `sig-no-key`. Needs the optional crypto dependency to verify.
    """
    msgs = list(messages)
    issues: List[Issue] = []
    shared: Set[str] = set(known_terms)                 # pre-agreed terms and broadcast defs
    pair_known: Dict[FrozenSet[str], Set[str]] = {}     # defs agreed between two agents
    seen: Dict[str, Message] = {}
    open_asks: Dict[str, Message] = {}
    pending_do: Dict[str, str] = {}                     # id -> "sent" | "accepted"
    do_eta: Dict[str, str] = {}                         # do id -> eta promised in ok
    do_by: Dict[str, datetime] = {}                     # do id -> :by deadline
    do_finish: Dict[str, datetime] = {}                 # do id -> promised :at + :eta
    retracted: Dict[str, str] = {}                      # retracted id -> id of the retract
    pending_prop: Dict[str, Message] = {}
    closed_prop: Dict[str, str] = {}                    # id -> "acc" | "rej"
    pending_def: Dict[str, tuple] = {}                  # def id -> (term, pair, signature)
    sigs: Dict[tuple, tuple] = {}                       # (scope, term) -> (args, ret); scope = pair | "*"
    var_types: Dict[str, Dict[str, Term]] = {}          # ask id -> {var name: expected type}
    why_targets: Dict[str, str] = {}                    # why id -> id it questions
    status_asks: Dict[str, Optional[str]] = {}          # status-ask id -> id of the request it queries
    status_claim: Dict[str, str] = {}                   # request id -> tell that claimed it done/failed
    parts: Dict[str, tuple] = {}                        # request id -> (n, {i received}) of :part slices
    acked: Dict[str, str] = {}                          # do/def/sub id -> the ok that acknowledged it
    closed_do: Set[str] = set()                         # do ids closed by done/fail/no/clar or retracted

    for m in msgs:
        issues.extend(validate_message(m.to_form()))
        if m.id in seen:
            issues.append(_err("dup-id", f"message id reused by {seen[m.id].sender}/{m.sender}", m.id))
        seen[m.id] = m

        if keys is not None:
            from .signing import sig_of, verify_form
            if m.sender not in keys:
                issues.append(_warn("sig-no-key", f"no public key known for @{m.sender}; "
                                    "signature not checked", m.id))
            elif sig_of(m.to_form()) is None:
                issues.append(_err("sig-missing", f"@{m.sender} has a known key but the message "
                                   "carries no well-formed :sig (SPEC §3.1)", m.id))
            elif not verify_form(m.to_form(), keys[m.sender]):
                issues.append(_err("sig-invalid", f"the :sig does not verify against @{m.sender}'s "
                                   "key: forged, altered, or signed with another key", m.id))

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
            if m.reply in retracted and m.act != "retract":
                issues.append(_warn("stale-reply", f"^{m.reply} was retracted by #{retracted[m.reply]}; "
                                    "a retract is unilateral and final (SPEC §4.4)", m.id))

        known = set(shared)
        if m.receiver != "*":
            known |= pair_known.get(_pair(m.sender, m.receiver), set())
        # Evidence under :src names data sources, :args/:ret name parameters and types
        # (SPEC §6.1), and :sig is transport metadata (SPEC §3.1), not vocabulary:
        # none of them is subject to resolution.
        checked = Form(m.act, list(m.body), {k: v for k, v in m.kw.items() if k not in ("src", "args", "ret", "sig")})
        for u in sorted(unresolved_terms(checked, known)):
            if m.act == "def" and m.body and isinstance(m.body[0], Symbol) and u == m.body[0].name:
                continue
            issues.append(_warn("unresolved-term", f"'{u}' is not core, namespaced, or defined for this pair", m.id))

        # Typed signatures (SPEC §6.1): check uses of defined terms, remember what each $var must bind to.
        pair = _pair(m.sender, m.receiver)
        expect: Dict[str, Term] = {}
        for b in m.body:
            for f in walk(b):
                if not isinstance(f, Form):
                    continue
                sig = sigs.get((pair, f.head)) or sigs.get(("*", f.head))
                if sig is None:
                    continue
                args, ret = sig
                if args is not None:
                    fixed = [a for a in f.args if not isinstance(a, Var)]
                    if len(fixed) > len(args):
                        issues.append(_warn("sig-arity", f"'{f.head}' takes {len(args)} argument(s) "
                                            f"({', '.join(n for n, _ in args)}), got {len(fixed)}", m.id))
                for i, v in enumerate(f.args):
                    t = args[i][1] if args is not None and i < len(args) else None
                    if isinstance(v, Var):
                        if (t if t is not None else ret) is not None:
                            expect[v.name] = t if t is not None else ret
                    elif t is not None and _type_ok(v, t) is False:
                        issues.append(_warn("sig-type", f"argument '{args[i][0]}' of '{f.head}' should be "
                                            f"{to_text(t)}, got {to_text(v)}", m.id))
        if m.act == "ask" and expect:
            var_types[m.id] = expect

        act, r = m.act, m.reply
        if act == "ask":
            open_asks[m.id] = m
            if m.body and isinstance(m.body[0], Form) and m.body[0].head == "status":
                status_asks[m.id] = (m.body[0].args[0].args[0].name
                                     if m.body[0].args and _is_ref_form(m.body[0].args[0]) else None)
        elif act == "do":
            pending_do[m.id] = "sent"
            by = _as_datetime(m.kw.get("by"))
            if by is not None:
                do_by[m.id] = by
        elif act == "prop":
            pending_prop[m.id] = m
        elif act == "def" and m.body and isinstance(m.body[0], Symbol):
            s_args, s_ret, s_err = parse_signature(m)
            sig_val = (s_args, s_ret) if s_err is None and (s_args is not None or s_ret is not None) else None
            if m.receiver == "*":
                shared.add(m.body[0].name)                 # a broadcast def is shared at once
                if sig_val is not None:
                    sigs[("*", m.body[0].name)] = sig_val
            else:
                pending_def[m.id] = (m.body[0].name, _pair(m.sender, m.receiver), sig_val)
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
                    target_req = status_asks[r]
                    if target_req and any(isinstance(v, Symbol) and v.name in ("done", "failed") for v in vals):
                        status_claim[target_req] = m.id
                complete = True
                pi = _part_of(m)
                if pi is not None:
                    i, n = pi
                    got = parts.setdefault(r, (n, set()))
                    if got[0] != n or i in got[1]:
                        issues.append(_err("part-mismatch", f"slice {i}/{n} conflicts with the "
                                           f"earlier slices of ^{r}", m.id))
                    got[1].add(i)
                    complete = len(got[1]) >= got[0]
                if complete:
                    del open_asks[r]
            if r in var_types:
                for b in m.body:
                    for t_ in walk(b):
                        if not isinstance(t_, KMap):
                            continue
                        for k, v in t_.items:
                            exp = var_types[r].get(k.name) if isinstance(k, Var) else None
                            if exp is not None and not isinstance(v, Var) and _type_ok(v, exp) is False:
                                issues.append(_warn("sig-ret", f"the binding for ${k.name} should be "
                                                    f"{to_text(exp)}, got {to_text(v)}", m.id))
            if r in why_targets and "src" not in m.kw:
                issues.append(_err("why-needs-src", "an answer to 'why' must carry :src (structured evidence or (none))", m.id))
        elif act == "ok":
            if r in open_asks:
                issues.append(_err("ok-for-ask", "'ok' acknowledges a do/def/sub; an 'ask' is answered "
                                   "with tell/no/fail/clar", m.id))
            elif r in closed_do:
                issues.append(_err("ack-closed", f"^{r} is already closed; an 'ok' after done/fail/no/clar "
                                   "or after a retract acknowledges nothing (SPEC §4.4)", m.id))
            elif r in acked:
                issues.append(_err("ack-twice", f"^{r} was already acknowledged by #{acked[r]}; a second "
                                   "'ok' is not a new promise (SPEC §4.4: use status to report progress, "
                                   "retract to withdraw)", m.id))
            elif target is not None and target.act not in ("do", "def", "sub", "unsub"):
                issues.append(_warn("ok-misplaced", f"'ok' acknowledges a do/def/sub/unsub, not a '{target.act}'", m.id))
            if target is not None and target.act in ("do", "def", "sub", "unsub") and r not in acked and r not in closed_do:
                acked[r] = m.id
            if r in pending_do:
                pending_do[r] = "accepted"
                if "eta" in m.kw:
                    do_eta[r] = to_text(m.kw["eta"])
                    at, eta = _as_datetime(m.kw.get("at")), _as_timedelta(m.kw["eta"])
                    if at is not None and eta is not None:
                        do_finish[r] = at + eta
                        if r in do_by and at + eta > do_by[r]:
                            issues.append(_warn("eta-overrun", f"promised finish (:at + :eta) is after "
                                                f"the :by deadline of ^{r}", m.id))
            elif r in pending_def:
                term, def_pair, sig_val = pending_def.pop(r)
                pair_known.setdefault(def_pair, set()).add(term)
                if sig_val is not None:
                    sigs[(def_pair, term)] = sig_val
        elif act == "no":
            open_asks.pop(r, None)
            if pending_do.pop(r, None) is not None:
                closed_do.add(r)
            pending_def.pop(r, None)
        elif act == "clar":
            open_asks.pop(r, None)
            if pending_do.pop(r, None) is not None:
                closed_do.add(r)
        elif act in ("done", "fail"):
            if r in pending_do:
                if act == "done" and pending_do[r] != "accepted":
                    issues.append(_err("done-without-ok", f"'done' for ^{r} without a prior 'ok'", m.id))
                complete = True
                pi = _part_of(m) if act == "done" else None
                if pi is not None:
                    i, n = pi
                    got = parts.setdefault(r, (n, set()))
                    if got[0] != n or i in got[1]:
                        issues.append(_err("part-mismatch", f"slice {i}/{n} conflicts with the "
                                           f"earlier slices of ^{r}", m.id))
                    got[1].add(i)
                    complete = len(got[1]) >= got[0]
                if complete:
                    del pending_do[r]
                    closed_do.add(r)
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
            retracted[target.id] = m.id
            t, tr = target.act, target.reply
            if t in ("acc", "rej") and tr in closed_prop:
                del closed_prop[tr]
                if tr in seen:
                    pending_prop[tr] = seen[tr]
            elif t in ("done", "fail") and tr in seen and seen[tr].act == "do":
                pending_do[tr] = "accepted"
                closed_do.discard(tr)
            elif t == "ok" and tr in seen and seen[tr].act in ("do", "def", "sub"):
                acked.pop(tr, None)                      # the acknowledgement is withdrawn: a new ok may follow
                if seen[tr].act == "do":
                    pending_do[tr] = "sent"
            elif t == "tell" and tr in seen and seen[tr].act == "ask":
                open_asks[tr] = seen[tr]
            elif t in ("prop",):
                pending_prop.pop(target.id, None)
                closed_prop.pop(target.id, None)
            elif t in ("ask", "do"):
                open_asks.pop(target.id, None)
                if pending_do.pop(target.id, None) is not None:
                    closed_do.add(target.id)

    for req, (n, got) in parts.items():
        if req in open_asks or req in pending_do:
            issues.append(_warn("part-missing", f"only {len(got)} of {n} :part slices arrived "
                                f"(missing {sorted(set(range(1, n + 1)) - got)})", req))
    for req, mid in status_claim.items():
        if req in pending_do or req in open_asks:
            issues.append(_warn("status-unclosed", f"status of ^{req} was answered done/failed, but the "
                                "request was never closed with done/fail (SPEC §4.4)", mid))
    for mid in open_asks:
        issues.append(_warn("open-ask", "ask was never answered (tell/no/fail)", mid))
    for mid, state in pending_do.items():
        eta = f", eta {do_eta[mid]} promised" if mid in do_eta else ""
        issues.append(_warn("open-do", f"do was never closed (state: {state}{eta})", mid))
        if now is not None:
            if mid in do_by and now > do_by[mid]:
                issues.append(_warn("deadline-passed", f"the :by deadline has passed and the do is "
                                    "still open", mid))
            elif mid in do_finish and now > do_finish[mid]:
                issues.append(_warn("eta-expired", f"the promised :at + :eta has elapsed without "
                                    "done or fail", mid))
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
