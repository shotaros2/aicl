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
from .dense import ACT_CODE, expand as dense_expand, to_dense
from .model import ACTS, AICLError, Form, Message, ParseError, Str, Symbol
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
            return [self._with_example(f, incoming) for f in self.handler(self, incoming)]
        except Exception as e:  # the specialist's own failure, reported, never hidden
            return [self.msg("fail", incoming.sender, reply=incoming.id,
                             kw={"code": Symbol("internal"), "why": nl("en", str(e)[:200])})]


    def _with_example(self, f: Form, incoming: Message) -> Form:
        """A bare `(unsupported do)` refusal also shows how to ask. Seen live: a critic sent the
        reader a do instead of an ask, read `(unsupported do)` as a bad address, and retried the
        same request with other spellings of the URL until it gave up."""
        why = f.kw.get("why")
        if (f.head == "no" and self.offers and isinstance(why, Form) and why.head == "unsupported"
                and "use" not in why.kw):
            f.kw["why"] = Form("unsupported", why.args, dict(why.kw, use=Str(self.offers[0])))
        return f


class ModelNode(Node):
    """An agent backed by a language model. It sees the dense rulebook, the network rules,
    its role and the directory, and decides every reply itself."""

    def __init__(self, name: str, role: str, ask: Ask, rulebook: str, offers: Iterable[str] = (),
                 attempts: int = 2, readable_input: bool = False):
        super().__init__(name, role, offers)
        self.ask = ask
        self.rulebook = rulebook
        self.attempts = attempts
        # Show incoming messages in the readable form (#user.1 @user>@me) instead of dense
        # (user.1>me). Smaller models mirror the dense header into `me.1>user.1`, addressing a
        # message id instead of an agent; the readable header gives them nothing to mirror.
        self.readable_input = readable_input
        self.history: List[dict] = []
        self.calls = 0
        self.system: Optional[str] = None
        self.sent: Counter = Counter()      # (act, receiver, body) -> times sent; see _parse

    def _system(self, net: "Network") -> str:
        if self.system is None:
            import re
            rb = re.sub(r"\bme\b", self.name, self.rulebook)
            self.system = rb + "\n\n" + NETWORK_RULES.format(role=self.role, directory=net.directory(self.name))
        return self.system

    def _attach(self, raw: str, net: "Network") -> str:
        """Files travel beside messages, never inside them (SPEC: bytes are sent as a blob). A model puts
        each file in a fenced block (```html … ```) and refers to it as (file 1), (file 2) … in its AICL;
        the network stores the bytes, hashes them, and puts the (blob sha256:…) form in their place.
        A fenced block of AICL itself (```aicl / ```lisp / unlabelled, starting with "(") is just unwrapped."""
        import hashlib
        import re
        fence = re.compile(r"```([A-Za-z0-9_+-]*)[ \t]*\r?\n(.*?)```", re.S)
        files, kept = [], []
        for lang, body in fence.findall(raw):
            if lang.lower() in ("", "aicl", "lisp", "scheme") and body.lstrip().startswith("("):
                kept.append(body)
            else:
                files.append((lang.lower(), body))
        text = fence.sub("", raw)
        text = "\n".join([text] + kept)
        refs = sorted({int(n) for n in re.findall(r"\(file (\d+)\)", text)})
        if not refs and not files:
            return text
        if net.files_dir is None:
            raise ParseError("this network does not accept files")
        mimes = {"html": "text/html", "htm": "text/html", "js": "text/javascript", "javascript": "text/javascript",
                 "css": "text/css", "svg": "image/svg+xml", "json": "application/json", "md": "text/markdown"}
        for n in refs:
            if n < 1 or n > len(files):
                raise ParseError(f"(file {n}) has no matching ``` block; put the file's content in a fenced block")
            lang, body = files[n - 1]
            ext = {"javascript": "js", "htm": "html"}.get(lang, lang if lang in mimes else "txt")
            data = body.encode("utf-8")
            Path(net.files_dir).mkdir(parents=True, exist_ok=True)
            path = Path(net.files_dir) / f"{self.name}-{self.seq + 1}-file{n}.{ext}"
            path.write_bytes(data)
            blob = (f'(blob sha256:{hashlib.sha256(data).hexdigest()} :media "{mimes.get(lang, "text/plain")}" '
                    f':bytes {len(data)} :uri "{path.resolve().as_uri()}")')
            text = text.replace(f"(file {n})", blob)
        return text

    def _parse(self, raw: str, net: "Network") -> List[Message]:
        raw = self._attach(raw.strip(), net).strip()
        lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith(";")]
        if not lines:
            return []
        out = []
        batch: Counter = Counter()
        for f in parse(dense_expand("\n".join(lines))):
            errors = [i for i in validate_message(f) if i.level == "error"]
            if errors:
                raise ParseError("; ".join(str(e) for e in errors))
            m = Message.from_form(f)
            if m.sender != self.name:
                raise ParseError(f"message claims to be from @{m.sender}; you are @{self.name}")
            if m.receiver != "*" and m.receiver not in net.nodes:
                raise ParseError(f"@{m.receiver} is not in the directory")
            first = m.body[0] if m.body else None
            if (m.act in ("ask", "do") and isinstance(first, Symbol)
                    and (first.name in ACTS or first.name in ACT_CODE.values())):
                raise ParseError(f"{first.name} is an act, not a body: the act goes first, e.g. "
                                 f"(K {m.id}>{m.receiver} ^<the id you answer>) for ok")
            batch[self._key(m)] += 1
            if m.act in ("ask", "do", "prop", "def") and self.sent[self._key(m)] + batch[self._key(m)] > 2:
                # Seen with qwen3.5:9b, thinking off: the same draft request twelve times, each
                # answered ok, until the call budget was gone. A third copy is bounced, so a stuck
                # local model counts as invalid and moves to the cloud.
                raise ParseError(f"you already sent this exact {m.act} to @{m.receiver} twice; wait for "
                                 "its answer or take a different step")
            inner = first if isinstance(first, Form) else None
            if m.act in ("ask", "do") and inner is not None and inner.head in ACTS:
                # Valid AICL, wrong meaning: a small model wraps every act in an ask, e.g.
                # (A chief.6>owner (fail …)), which nobody can read as the fail it meant.
                raise ParseError(
                    f"{inner.head} is an act: write ({ACT_CODE[inner.head]} {m.id}>{m.receiver} …), "
                    f"with ^ and the id it answers where it is a reply, not an {m.act} whose body is "
                    f"({inner.head} …)")
            out.append(m)
        return out

    def _call(self, net: "Network") -> str:
        """One model call on the history so far (aicl.actions.StructuredModelNode adds a schema)."""
        return self.ask(self._system(net), self.history)

    @staticmethod
    def _key(m: Message):
        return (m.act, m.receiver, tuple(repr(b) for b in m.body))

    def _observe(self, net: "Network", kind: str, detail: str = "") -> bool:
        """Tell an escalating ask (vendors.with_escalation) how its answers fared, and record
        any escalation it reports. Returns True if the role moved to the cloud just now."""
        observe = getattr(self.ask, "observe", None)
        moved = bool(observe(kind, detail)) if observe is not None else False
        self._drain_notes(net)
        return moved

    def _drain_notes(self, net: "Network") -> None:
        for n in getattr(self.ask, "pending_notes", lambda: [])():
            net.note(f"@{self.name} {n}")

    def react(self, net, event, incoming):
        nxt = f"{self.name}.{self.seq + 1}"
        show = to_text if self.readable_input else to_dense
        content = event + (("\n" + show(incoming.to_form())) if incoming is not None else "") + f"\n; next-id {nxt}"
        if incoming is not None and incoming.act == "rej":
            why = incoming.kw.get("why")
            self._observe(net, "rejected", f"#{incoming.id} from @{incoming.sender}"
                          + (f": {to_text(why)}" if why is not None else ""))
        msgs: List[Message] = []
        error = ""
        attempt, tries = 0, self.attempts
        while attempt < tries:
            if self.calls >= net.limits.max_calls_per_agent:
                net.note(f"@{self.name} reached its budget of {net.limits.max_calls_per_agent} model calls")
                return []
            text = content if attempt == 0 else f"; your answer was not valid AICL: {error}\n; resend.\n{content}"
            self.history.append({"role": "user", "content": text})
            self.calls += 1
            try:
                raw = self._call(net).strip()
            except Exception as e:  # provider outage or quota: reported, never guessed around
                self.history.append({"role": "assistant", "content": ""})
                self._drain_notes(net)
                net.note(f"@{self.name} model call failed: {str(e)[:160]}")
                if incoming is not None and incoming.act in ("ask", "do", "prop", "def"):
                    return [self.msg("fail", incoming.sender, reply=incoming.id,
                                     kw={"code": Symbol("internal"), "why": nl("en", "model unavailable")})]
                return []
            self._drain_notes(net)
            self.history.append({"role": "assistant", "content": raw})
            try:
                msgs = self._parse(raw, net)
                if attempt > 0 and not msgs:
                    # Silence is a fine answer to news, never to "resend": seen with qwen3.5:9b, whose
                    # empty retry of a broken publish left a finished, accepted page unpublished.
                    raise ParseError("empty answer; resend the corrected message")
                self._observe(net, "valid")
                break
            except AICLError as e:
                error = str(e)[:200]
                shown = raw if len(raw) <= 260 else raw[:160] + " … " + raw[-100:]   # the end shows truncation
                net.note(f"@{self.name} invalid (attempt {attempt + 1}): {error} | {shown}")
                if self._observe(net, "invalid", error):
                    tries += 1      # the role just moved to the cloud: give the new model one try at this event
            attempt += 1
        else:
            return []
        for m in msgs:
            self.sent[self._key(m)] += 1
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
                 on_message: Optional[Callable[[Message], None]] = None,
                 files_dir: Optional[Path] = None):
        self.on_message = on_message      # an observer of every delivered message, e.g. the Discord mirror
        self.files_dir = files_dir        # where files that models attach (```html … ``` + (file 1)) are stored
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

    def run(self, wake: Iterable[str] = None, wake_event="; wake: you are online") -> NetworkResult:
        """Wake the given agents (default: every model agent) with `wake_event` (a string, or a
        function of the agent's name), then deliver until quiet. A network may run again (e.g. a
        retrospective after a task); each result is a snapshot of the whole record so far."""
        started = time.monotonic()
        stopped = ""
        for name in (wake if wake is not None else [n.name for n in self.nodes.values() if isinstance(n, ModelNode)]):
            event = wake_event(name) if callable(wake_event) else wake_event
            for f in self.nodes[name].react(self, now_line(self.clock()) + "\n" + event, None):
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
                # An ask counts too: seen live, a chief sent (ask … (draft …)), the writer answered ok
                # and never drafted.
                accepted_do = m.act in ("do", "ask") and any(f.head == "ok" and Message.from_form(f).reply == m.id
                                                             for f in out)
                if isinstance(t, ModelNode) and out and all(f.head == "ok" for f in out) and accepted_do:
                    for f in t.react(self, now_line(self.clock()) + "\n; continue: you only acknowledged; "
                                     "take your next step now, or send nothing if there is none", None):
                        self.post(f)
        stopped = stopped or "quiet: no agent had anything left to say"
        issues = validate_conversation(self.log, self.known_terms, keys=self.keys or None)
        calls = {n.name: n.calls for n in self.nodes.values() if isinstance(n, ModelNode)}
        return NetworkResult(list(self.log), list(self.wire), issues, list(self.notes), dict(self.keys), stopped,
                             time.monotonic() - started, calls)
