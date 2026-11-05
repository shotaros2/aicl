"""Agents that act through schema-checked JSON; the network writes the AICL.

Measured on 2026-11-05 (HANDOFF section 6): most failed night-shift tasks did not fail on the
task but on writing AICL text - an unclosed parenthesis in a long publish request, a wrong
timestamp token, an act letter inside an ask. A model can be made to return JSON that always
matches a schema (Claude's output_config.format, Ollama's format), so a `StructuredModelNode`
asks for that and turns each action into an ordinary AICL message. Everything after that point is
unchanged: the network validates, signs and records every message, the desk publishes only what
the critic accepted, and agreements stay verifiable by a third party. Long text travels inside
JSON strings, never inside hand-balanced parentheses, and content is passed on by message id
(`copy_of`, `publish_accepted`), never copied by hand.
"""
from __future__ import annotations

import copy
import json
from typing import Dict, List, Optional

from .build import form, msg, nl
from .model import FAIL_CODES, Form, KList, Message, ParseError, Ref, Str, Symbol
from .network import ModelNode, Network
from .parser import parse
from .printer import to_text

ACTS = ["ask", "tell", "do", "ok", "no", "done", "fail", "prop", "acc", "rej", "clar"]


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, {"type": "null"}]}


def _obj(props: Dict[str, dict]) -> dict:
    return {"type": "object", "additionalProperties": False, "properties": props, "required": list(props)}


STRING = {"type": "string"}
STRINGS = {"type": "array", "items": STRING}


def schema(agents: List[str]) -> dict:
    """The answer every structured agent gives: zero or more actions, each one AICL message."""
    action = _obj({
        "act": {"type": "string", "enum": ACTS},
        "to": {"type": "string", "enum": sorted(agents)},
        "reply_to": _nullable(STRING),
        "request": _nullable(STRING),
        "draft": _nullable(_obj({"about": STRING, "facts": STRINGS, "sources": STRINGS})),
        "doc": _nullable(_obj({"title": STRING, "body": STRING, "sources": STRINGS})),
        "copy_of": _nullable(STRING),
        "publish_accepted": _nullable(STRING),
        "advice": _nullable(STRING),
        "why": _nullable(STRING),
        "code": _nullable({"type": "string", "enum": sorted(FAIL_CODES)}),
    })
    return _obj({"messages": {"type": "array", "items": action}})


RULES = """\
## How you answer

You read AICL messages (the readable form: `(act #id @from>@to ^reply-to body… :key value)`).
You answer with JSON only: {"messages": [ … ]}, zero or more actions. The network turns each
action into an AICL message, numbers it, signs it and delivers it. An empty list means you
have nothing to do right now.

Each action:
- act: ask (a question; answered with tell), do (a request to act; answered with ok, then done
  or fail), tell (an answer to an ask), ok, no, done, fail, prop (a proposal; answered with acc or
  rej), acc, rej, clar (you did not understand).
- to: the agent's name from the directory.
- reply_to: the id of the message you answer (e.g. "owner.1"); required for ok, no, done, fail,
  acc, rej, clar, and for tell when it answers an ask; otherwise null.
- the body: at most ONE of
  - request: a short AICL form for a specialist, exactly as the directory shows, e.g.
    (search (nl ja "東京タワー") $r) or (read "https://…" $p)
  - draft: {about, facts, sources} - a request to the writer to draft a page (act do)
  - doc: {title, body, sources} - a page (the writer's done, or a prop to the checker); body is
    plain Japanese text, sources are the exact URLs you were given
  - copy_of: the id of an earlier message whose content you pass on unchanged - for example the
    writer's page to the checker (act prop), or the desk's blob to the owner (act done)
  - publish_accepted: the id of YOUR prop that the checker accepted (act do, to the desk); the
    desk publishes exactly that
  - advice: one sentence of advice to a teammate (act prop, in a retrospective)
- why: the reason, in plain text; required for no, fail and rej
- code: for fail only - one of the codes listed (e.g. not-found, unsupported)
Every field is present; unused ones are null.
"""

NETWORK_RULES = """\
## You are one agent in an autonomous network

Nobody will instruct you and nobody relays for you: you decide for yourself what to do,
whom to ask and when to stop. Your agent name is @{me}. Your role, set once by whoever started
the network:

{role}

Directory - the agents you can reach, and what they say they can do:
{directory}

Each input is one event: the transport's clock line `; now <instant>`, then either a comment
(a wake-up, a retrospective, a correction) or one AICL message that was addressed to you.
A `do` you send is a request, not an order: the other agent may refuse. You only see messages
addressed to you. Keep every request you open on track and close what you started."""


def _lang(text: str) -> str:
    return "ja" if any(ord(c) > 0x2FFF for c in text) else "en"


def _id(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return text.strip().lstrip("^#").strip() or None


class StructuredModelNode(ModelNode):
    """A ModelNode whose model answers in schema-checked JSON (see the module doc). Its `ask` takes
    `schema=`: aicl.claude and aicl.local pass it to the provider as a hard output constraint.
    It reads incoming messages in the readable form, which its rules describe."""

    def __init__(self, *a, readable_input: bool = True, **kw):
        super().__init__(*a, readable_input=readable_input, **kw)

    def _system(self, net: Network) -> str:
        if self.system is None:
            self.system = RULES + "\n" + NETWORK_RULES.format(me=self.name, role=self.role,
                                                              directory=net.directory(self.name))
        return self.system

    def _call(self, net: Network) -> str:
        names = [n for n in net.nodes if n != self.name]
        return self.ask(self._system(net), self.history, schema=schema(names))

    def _parse(self, raw: str, net: Network) -> List[Message]:
        try:
            data = json.loads(raw)
        except ValueError as e:
            raise ParseError(f"not JSON: {e}") from None
        actions = data.get("messages") if isinstance(data, dict) else None
        if not isinstance(actions, list):
            raise ParseError('expected {"messages": [ … ]}')
        known = {m.id: m for m in net.log}
        lines = []
        for i, a in enumerate(actions):
            f = self._to_form(a, f"{self.name}.{self.seq + 1 + i}", known)
            lines.append(to_text(f))
        # The ordinary checks (validation, directory, repeats, acts inside asks) run on the AICL.
        return super()._parse("\n".join(lines), net)

    def _to_form(self, a: dict, mid: str, known: Dict[str, Message]) -> Form:
        if not isinstance(a, dict) or a.get("act") not in ACTS or not a.get("to"):
            raise ParseError("each action needs act and to")
        act, to = a["act"], str(a["to"]).lstrip("@")

        def earlier(field: str) -> Message:
            ref = _id(a.get(field))
            if ref not in known:
                raise ParseError(f"{field}: no earlier message #{ref}; use an id you have seen")
            return known[ref]

        reply = _id(a.get("reply_to"))
        if reply is not None and reply not in known:
            raise ParseError(f"reply_to: no earlier message #{reply}")
        body: List = []
        if a.get("request"):
            try:
                forms = parse(a["request"])
            except Exception as e:
                raise ParseError(f"request is not one AICL form: {e}") from None
            if len(forms) != 1:
                raise ParseError("request must be exactly one AICL form")
            body.append(forms[0])
        elif a.get("draft"):
            d = a["draft"]
            body.append(form("draft", kw={
                "about": nl(_lang(d.get("about", "")), d.get("about", "")),
                "facts": KList([nl(_lang(t), t) for t in d.get("facts") or []]),
                "sources": KList([form("source", kw={"uri": Str(u)}) for u in d.get("sources") or []])}))
        elif a.get("doc"):
            d = a["doc"]
            body.append(form("doc", kw={
                "title": nl(_lang(d.get("title", "")), d.get("title", "")),
                "body": nl(_lang(d.get("body", "")), d.get("body", "")),
                "sources": KList([form("source", kw={"uri": Str(u)}) for u in d.get("sources") or []])}))
        elif a.get("copy_of"):
            src = earlier("copy_of")
            if not src.body:
                raise ParseError(f"copy_of: #{src.id} carries no content")
            body.append(copy.deepcopy(src.body[0]))
        elif a.get("publish_accepted"):
            src = earlier("publish_accepted")
            body.append(form("publish", form("ref", Ref(src.id))))
        elif a.get("advice"):
            body.append(form("advice", nl(_lang(a["advice"]), a["advice"])))
        kw = {}
        if a.get("why"):
            kw["why"] = nl(_lang(a["why"]), a["why"])
        if a.get("code") and act == "fail":
            kw["code"] = Symbol(a["code"])
        return msg(act, mid, self.name, to, *body, reply=reply, kw=kw)
