"""Autonomous AICL network: agents that decide for themselves whom to ask and what to do.

No human relays messages and no script says who speaks next. Each agent has a role, set
once, and reacts to whatever reaches it: a wake-up or a message. A model agent answers each
event with zero or more AICL messages of its own choosing, to anyone in the directory, and
the network delivers them. Who talks to whom, about what, and in what order is decided by
the agents; the run ends when nobody has anything left to say, or a limit is hit.

The network owns what a model must not: identity (it signs every message with the sender's
Ed25519 key, SPEC §3.1), the clock (`; now`, from the real wall clock), message numbering,
the directory, and the limits - a per-agent budget of model calls, a message cap, a wall
clock cap and a STOP file. Every message is validated at the boundary, and the dense wire
and the canonical transcript are both kept: the agents talk faster than anyone could read
along, and a human can still read back, verify and audit all of it afterwards.
"""
from __future__ import annotations

import time
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Deque, Dict, Iterable, List, Optional

from .build import msg as build_msg, nl
from .dense import expand as dense_expand, to_dense
from .model import AICLError, Form, Message, ParseError, Symbol
from .parser import parse
from .printer import to_text
from .validate import Issue, validate_conversation, validate_message

Ask = Callable[[str, List[dict]], str]
JST = timezone(timedelta(hours=9))

NETWORK_RULES = """\
## You are one agent in an autonomous network

Nobody will instruct you and nobody relays for you: you decide for yourself what to do,
whom to ask and when to stop. Your role, set once by whoever started the network:

{role}

Directory - the agents you can reach, and what they say they can do (`x` = your own id):
{directory}

Each input is one event: the transport's clock line `; now <instant>`, then either a wake-up
comment or one AICL message that was addressed to you (or broadcast with `>*`).
Answer with zero or more AICL messages, one per line, and nothing else. An empty answer means
you have nothing to do right now. Your next free id is given as `; next-id <id>`; number any
further messages upward from it. Address only agents in the directory. A `do` you send is a
request, not an order: the other agent may refuse. You only see messages addressed to you.
Keep every request you open on track and close what you started."""


@dataclass
class Limits:
    max_messages: int = 80            # delivered messages, all agents together
    max_calls_per_agent: int = 12     # model calls per model agent (corrections included)
    max_seconds: float = 900.0        # wall clock for the whole run
    stop_file: Optional[Path] = None  # create this file to stop the network at the next message


def now_line(now: Optional[datetime] = None) -> str:
    t = (now or datetime.now(JST)).astimezone(JST)
    return "; now " + t.strftime("%Y-%m-%dT%H:%M:%S+09:00")


class Node:
    """Anything with a name that reacts to messages. `offers` are example messages showing
    what others can ask of it; they go into every model agent's directory."""

    def __init__(self, name: str, role: str, offers: Iterable[str] = ()):
        self.name = name
        self.role = role
        self.offers = list(offers)
        self.seq = 0

    def next_id(self) -> str:
        self.seq += 1
        return f"{self.name}.{self.seq}"

    def msg(self, act: str, to: str, *body, reply: str = None, kw: dict = None) -> Form:
        return build_msg(act, self.next_id(), self.name, to, *body, reply=reply, kw=kw)

    def react(self, net: "Network", event: str, incoming: Optional[Message]) -> List[Form]:
        return []


class SkillNode(Node):
    """A deterministic specialist: `handler(node, message) -> [forms]`. No model, no judgment:
    it does what it advertises, and says `no`, `clar` or `fail` when it cannot."""

    def __init__(self, name: str, role: str, handler: Callable[["SkillNode", Message], List[Form]],
                 offers: Iterable[str] = ()):
        super().__init__(name, role, offers)
        self.handler = handler

    def react(self, net, event, incoming):
        if incoming is None or incoming.act in ("ok", "no", "done", "fail", "end", "tell", "acc", "rej", "clar"):
            return []
        self.net = net          # lets a specialist check the record, e.g. the desk's acceptance gate
        try:
            return self.handler(self, incoming)
        except Exception as e:  # the specialist's own failure, reported, never hidden
            return [self.msg("fail", incoming.sender, reply=incoming.id,
                             kw={"code": Symbol("internal"), "why": nl("en", str(e)[:200])})]


class ModelNode(Node):
    """An agent backed by a language model. It sees the dense rulebook, the network rules,
    its role and the directory, and decides every reply itself."""

    def __init__(self, name: str, role: str, ask: Ask, rulebook: str, offers: Iterable[str] = (),
                 attempts: int = 2):
        super().__init__(name, role, offers)
        self.ask = ask
        self.rulebook = rulebook
        self.attempts = attempts
        self.history: List[dict] = []
        self.calls = 0
        self.system: Optional[str] = None

    def _system(self, net: "Network") -> str:
        if self.system is None:
            import re
            rb = re.sub(r"\bme\b", self.name, self.rulebook)
            self.system = rb + "\n\n" + NETWORK_RULES.format(role=self.role, directory=net.directory(self.name))
        return self.system

    def _parse(self, raw: str, net: "Network") -> List[Message]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").removeprefix("lisp").removeprefix("aicl").strip()
        lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith(";")]
        if not lines:
            return []
        out = []
        for f in parse(dense_expand("\n".join(lines))):
            errors = [i for i in validate_message(f) if i.level == "error"]
            if errors:
                raise ParseError("; ".join(str(e) for e in errors))
            m = Message.from_form(f)
            if m.sender != self.name:
                raise ParseError(f"message claims to be from @{m.sender}; you are @{self.name}")
            if m.receiver != "*" and m.receiver not in net.nodes:
                raise ParseError(f"@{m.receiver} is not in the directory")
            out.append(m)
        return out

    def react(self, net, event, incoming):
        nxt = f"{self.name}.{self.seq + 1}"
        content = event + (("\n" + to_dense(incoming.to_form())) if incoming is not None else "") + f"\n; next-id {nxt}"
        msgs: List[Message] = []
        error = ""
        for attempt in range(self.attempts):
            if self.calls >= net.limits.max_calls_per_agent:
                net.note(f"@{self.name} reached its budget of {net.limits.max_calls_per_agent} model calls")
                return []
            text = content if attempt == 0 else f"; your answer was not valid AICL: {error}\n; resend.\n{content}"
            self.history.append({"role": "user", "content": text})
            self.calls += 1
            try:
                raw = self.ask(self._system(net), self.history).strip()
            except Exception as e:  # provider outage or quota: reported, never guessed around
                self.history.append({"role": "assistant", "content": ""})
                net.note(f"@{self.name} model call failed: {str(e)[:160]}")
                if incoming is not None and incoming.act in ("ask", "do", "prop", "def"):
                    return [self.msg("fail", incoming.sender, reply=incoming.id,
                                     kw={"code": Symbol("internal"), "why": nl("en", "model unavailable")})]
                return []
            self.history.append({"role": "assistant", "content": raw})
            try:
                msgs = self._parse(raw, net)
                break
            except AICLError as e:
                error = str(e)[:200]
                net.note(f"@{self.name} invalid (attempt {attempt + 1}): {error} | {raw[:160]}")
        else:
            return []
        # The network owns numbering: a reused or out-of-order id is renumbered, and the agent's
        # own ^references to it follow, so ids stay unique without trusting the model.
        renamed: Dict[str, str] = {}
        for m in msgs:
            try:
                prefix, n = m.id.rsplit(".", 1)
                n = int(n)
            except ValueError:
                prefix, n = "", 0
            if prefix != self.name or n <= self.seq:
                new = self.next_id()
                renamed[m.id] = new
                m.id = new
            else:
                self.seq = n
            if m.reply in renamed:
                m.reply = renamed[m.reply]
        return [m.to_form() for m in msgs]


@dataclass
class NetworkResult:
    messages: List[Message]
    wire: List[str]
    issues: List[Issue]
    notes: List[str]
    keys: Dict[str, str]
    stopped: str
    seconds: float
    calls: Dict[str, int] = field(default_factory=dict)

    def canonical(self) -> str:
        return "\n".join(to_text(m.to_form()) for m in self.messages)

    def save(self, out_dir: Path) -> None:
        import json
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "transcript.aicl").write_text(self.canonical() + "\n", encoding="utf-8", newline="\n")
        (out_dir / "wire.aicl").write_text("\n".join(self.wire) + "\n", encoding="utf-8", newline="\n")
        (out_dir / "keys.json").write_text(json.dumps(self.keys, indent=2), encoding="utf-8")

    def stats(self) -> str:
        """Who decided what: messages each agent sent, by act, and how many it started itself."""
        lines = [f"{len(self.messages)} messages in {self.seconds:.0f}s, stopped: {self.stopped}"]
        by: Dict[str, Counter] = {}
        for m in self.messages:
            by.setdefault(m.sender, Counter())[m.act] += 1
        for name, c in by.items():
            started = sum(c[a] for a in ("ask", "do", "prop", "def", "sub"))
            acts = " ".join(f"{a}:{n}" for a, n in sorted(c.items()))
            calls = f", {self.calls[name]} model calls" if name in self.calls else ""
            lines.append(f"  @{name}: {sum(c.values())} sent ({acts}); started {started} requests itself{calls}")
        errors = [i for i in self.issues if i.level == "error"]
        lines.append(f"  validator: {len(errors)} errors, {len(self.issues) - len(errors)} warnings")
        return "\n".join(lines)


class Network:
    """Delivers messages between nodes until the network falls quiet or a limit is reached."""

    def __init__(self, nodes: Iterable[Node], limits: Limits = None, sign: bool = True,
                 known_terms: Iterable[str] = (), clock: Callable[[], datetime] = None,
                 echo: Optional[Callable[[str], None]] = print,
                 on_message: Optional[Callable[[Message], None]] = None):
        self.on_message = on_message      # an observer of every delivered message, e.g. the Discord mirror
        self.nodes: Dict[str, Node] = {n.name: n for n in nodes}
        self.limits = limits or Limits()
        self.known_terms = tuple(known_terms)
        self.clock = clock or (lambda: datetime.now(JST))
        self.say = echo or (lambda s: None)
        self.queue: Deque[Message] = deque()
        self.log: List[Message] = []
        self.wire: List[str] = []
        self.notes: List[str] = []
        self.priv: Dict[str, str] = {}
        self.keys: Dict[str, str] = {}
        if sign:
            from .signing import generate_key
            for name in self.nodes:
                self.priv[name], self.keys[name] = generate_key()

    def directory(self, viewer: str = "") -> str:
        rows = []
        for n in self.nodes.values():
            if n.name == viewer:
                continue
            offers = "".join(f"\n    e.g. {o}" for o in n.offers)
            rows.append(f"- @{n.name}: {getattr(n, 'blurb', None) or n.role}{offers}")
        return "\n".join(rows)

    def note(self, text: str) -> None:
        self.notes.append(text)
        self.say(f"  ! {text}")

    def post(self, f: Form) -> None:
        errors = [i for i in validate_message(f) if i.level == "error"]
        if errors:
            self.note(f"dropped an invalid message: {'; '.join(str(e) for e in errors)}")
            return
        m = Message.from_form(f)
        if self.priv:
            from .signing import sign_form
            m = Message.from_form(sign_form(m.to_form(), self.priv[m.sender]))
        self.log.append(m)
        self.wire.append(to_dense(m.to_form()))
        shown = self.wire[-1]
        if self.on_message is not None:
            try:
                self.on_message(m)
            except Exception as e:          # an observer must never break the network
                self.notes.append(f"observer failed: {str(e)[:120]}")
        self.say(shown if len(shown) < 400 else shown[:400] + " …")
        self.queue.append(m)

    def _stop_reason(self, started: float) -> str:
        if len(self.log) >= self.limits.max_messages:
            return f"message cap ({self.limits.max_messages})"
        if time.monotonic() - started > self.limits.max_seconds:
            return f"time cap ({self.limits.max_seconds:.0f}s)"
        if self.limits.stop_file is not None and Path(self.limits.stop_file).exists():
            return f"stop file {self.limits.stop_file}"
        return ""

    def run(self, wake: Iterable[str] = None) -> NetworkResult:
        """Wake the given agents (default: every model agent), then deliver until quiet."""
        started = time.monotonic()
        stopped = ""
        for name in (wake if wake is not None else [n.name for n in self.nodes.values() if isinstance(n, ModelNode)]):
            for f in self.nodes[name].react(self, now_line(self.clock()) + "\n; wake: you are online", None):
                self.post(f)
        while self.queue:
            stopped = self._stop_reason(started)
            if stopped:
                break
            m = self.queue.popleft()
            if m.receiver == "*":
                targets = [n for n in self.nodes.values() if n.name != m.sender]
            elif m.receiver in self.nodes:
                targets = [self.nodes[m.receiver]]
            else:
                self.note(f"#{m.id} is addressed to unknown @{m.receiver}; not delivered")
                continue
            for t in targets:
                out = t.react(self, now_line(self.clock()), m)
                for f in out:
                    self.post(f)
                # A model that only acknowledged (ok) has no event left to act on: nothing will be sent
                # to it until it acts. Give it one turn to take its next step, as a human would.
                accepted_do = m.act == "do" and any(f.head == "ok" and Message.from_form(f).reply == m.id for f in out)
                if isinstance(t, ModelNode) and out and all(f.head == "ok" for f in out) and accepted_do:
                    for f in t.react(self, now_line(self.clock()) + "\n; continue: you only acknowledged; "
                                     "take your next step now, or send nothing if there is none", None):
                        self.post(f)
        stopped = stopped or "quiet: no agent had anything left to say"
        issues = validate_conversation(self.log, self.known_terms, keys=self.keys or None)
        calls = {n.name: n.calls for n in self.nodes.values() if isinstance(n, ModelNode)}
        return NetworkResult(self.log, self.wire, issues, self.notes, self.keys, stopped,
                             time.monotonic() - started, calls)
