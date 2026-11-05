"""Agreements (SPEC §4.6): what two agents agreed to, extracted and verified from a transcript.

An agreement is a `prop` closed by an `acc` and not retracted. Its identity is the
digest of the proposal's canonical form (without `:sig`), and it is *verified* when
both messages carry valid signatures of their senders (SPEC §3.1) and the protocol
check raises no error on either message. Nothing here reads natural language: the
terms are the proposal's body, the parties are the route, the time is whatever the
terms say, and the proof is arithmetic over the canonical form.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .model import Agent, Form, KList, KMap, Message, Ref, Str, Symbol
from .printer import to_text
from .signing import payload, sig_of, verify_form
from .validate import Issue, validate_conversation


@dataclass
class Agreement:
    proposal: Message
    acceptance: Message
    signed: Dict[str, Optional[bool]] = field(default_factory=dict)   # agent -> verified? (None: no key)
    errors: List[Issue] = field(default_factory=list)                 # protocol errors on either message
    retracted_by: Optional[str] = None

    @property
    def parties(self) -> tuple:
        return (self.proposal.sender, self.proposal.receiver)

    @property
    def terms(self) -> Form:
        return self.proposal.body[0] if self.proposal.body and isinstance(self.proposal.body[0], Form) \
            else Form("terms", list(self.proposal.body))

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(payload(self.proposal.to_form())).hexdigest()

    @property
    def verified(self) -> bool:
        """Both parties signed and verify, no protocol error, not retracted."""
        return (self.retracted_by is None and not self.errors
                and all(self.signed.get(p) is True for p in self.parties))

    def report(self) -> Form:
        """An AICL form summarising the agreement, for logs and for other agents."""
        a, b = self.parties
        kw = {
            "between": KList([Agent(a), Agent(b)]),
            "terms": self.terms,
            "proposed": Form("ref", [Ref(self.proposal.id)]),
            "accepted": Form("ref", [Ref(self.acceptance.id)]),
            "digest": Str(self.digest),
            "signed": KMap([(Agent(p), _tri(self.signed.get(p))) for p in self.parties]),
            "verified": self.verified,
        }
        if self.retracted_by:
            kw["retracted-by"] = Form("ref", [Ref(self.retracted_by)])
        if self.errors:
            kw["errors"] = KList([Symbol(e.code) for e in self.errors])
        return Form("agreement", [], kw)


def _tri(v: Optional[bool]):
    return Symbol("unknown") if v is None else v


def extract_agreements(messages: Iterable[Message], keys: Optional[Dict[str, str]] = None,
                       known_terms: Iterable[str] = ()) -> List[Agreement]:
    """Every (prop, acc) pair in the transcript, with signature and protocol verdicts."""
    msgs = list(messages)
    by_id = {m.id: m for m in msgs}
    issues = validate_conversation(msgs, known_terms, keys=keys)
    retracted = {m.reply: m.id for m in msgs if m.act == "retract" and m.reply}
    out: List[Agreement] = []
    for m in msgs:
        if m.act != "acc" or m.reply not in by_id or by_id[m.reply].act != "prop":
            continue
        prop = by_id[m.reply]
        ag = Agreement(prop, m)
        for party, msg in ((prop.sender, prop), (m.sender, m)):
            if keys is None or party not in keys:
                ag.signed[party] = None if sig_of(msg.to_form()) is None or keys is None else None
            else:
                ag.signed[party] = verify_form(msg.to_form(), keys[party])
        ag.errors = [i for i in issues if i.level == "error" and i.msg_id in (prop.id, m.id)]
        ag.retracted_by = retracted.get(m.id) or retracted.get(prop.id)
        out.append(ag)
    return out


def describe(agreements: List[Agreement]) -> str:
    return "\n".join(to_text(a.report()) for a in agreements) or "; no agreement (no prop closed by acc)"
