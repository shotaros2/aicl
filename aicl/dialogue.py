"""Machine-speed AICL dialogues between LLM agents, with the validator at the boundary.

This is the harness behind examples 10-13, promoted from the experiment runners into
the library: each agent is an LLM asked to produce exactly one AICL message per turn;
every message is parsed and validated before delivery; an invalid one is bounced back
once with the parse error; the whole conversation is checked and logged at the end.

No human sits in the loop - this is the layer that removes the hand relay - but every
byte that crossed the wire stays in the transcript, so a human (or `aicl check`) can
always read it back.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .codebook import Codebook
from .dense import expand as dense_expand
from .model import AICLError, Message, ModelError
from .parser import parse
from .printer import to_text
from .validate import Issue, nl_ratio, validate_conversation, validate_message

Ask = Callable[[str, List[dict]], str]   # ask(system, history) -> raw text


class AiclAgent:
    """An LLM speaking AICL: one message per turn, chat history kept per agent.

    `ask` is an ask(system, history) function - aicl.gemini.text_ask() or
    aicl.claude.text_ask() - and `system` is the full system prompt: the language
    reference (readable or dense), any harness rules, and the agent's private goal.
    """

    def __init__(self, name: str, ask: Ask, system: str):
        self.name = name
        self.ask = ask
        self.system = system
        self.history: List[dict] = []

    def turn(self, incoming: str) -> str:
        self.history.append({"role": "user", "content": incoming})
        text = self.ask(self.system, self.history).strip()
        if text.startswith("```"):   # some models wrap output in a code fence
            text = text.strip("`").removeprefix("lisp").removeprefix("aicl").strip()
        self.history.append({"role": "assistant", "content": text})
        return text


@dataclass
class Clock:
    """A simulated wall clock the harness injects as a `; now <instant>` line."""
    start: datetime
    step: timedelta

    def __post_init__(self):
        if self.start.tzinfo is None:
            raise ValueError("Clock.start must be timezone-aware")
        self.now = self.start

    def line(self) -> str:
        t = self.now
        off = t.strftime("%z")
        return f"; now {t.strftime('%Y-%m-%dT%H:%M')}{off[:3]}:{off[3:]}"

    def tick(self) -> None:
        self.now += self.step


@dataclass
class DialogueResult:
    messages: List[Message]
    wire: List[str]                      # exactly what each sender emitted
    issues: List[Issue]                  # per-message + whole-conversation validation
    notes: List[str] = field(default_factory=list)   # retries, rule-3 violations, aborts

    @property
    def ok(self) -> bool:
        return not any(i.level == "error" for i in self.issues) and not self.notes

    def canonical(self) -> str:
        return "\n".join(to_text(m.to_form()) for m in self.messages)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.canonical() + "\n", encoding="utf-8")
        if self.wire != [to_text(m.to_form()) for m in self.messages]:
            Path(str(path) + ".wire.txt").write_text("\n".join(self.wire) + "\n", encoding="utf-8")

    def stats(self) -> str:
        from . import tokens
        canon = self.canonical()
        wire = "\n".join(self.wire)
        s = f"{len(self.messages)} messages, {tokens.count(canon)} tokens canonical ({tokens.METHOD})"
        if wire != canon:
            s += f", {tokens.count(wire)} on the wire"
        return s + f", nl ratio {nl_ratio(self.messages):.0%}"


def run_dialogue(agents: Dict[str, AiclAgent],
                 first: str,
                 opening: str = "; conversation start: send your first AICL message",
                 max_turns: int = 20,
                 known_terms: tuple = (),
                 clock: Optional[Clock] = None,
                 codebook: Optional[Codebook] = None,
                 retries: int = 1,
                 now: Optional[datetime] = None,
                 signers: Optional[Dict[str, str]] = None,
                 echo: Optional[Callable[[str], None]] = print) -> DialogueResult:
    """Run one conversation between `agents` until (end …), an abort, or max_turns.

    Every outgoing message is parsed (and, with `codebook`, unpacked) and validated at
    the boundary; an invalid one is bounced back to its author up to `retries` times
    with a harness comment naming the error. Each delivery is the sender's wire text,
    untouched; with `clock`, a `; now <instant>` line precedes it and the clock advances
    one step per message.

    With `signers` ({agent name: base64url Ed25519 private key}, SPEC §3.1) the harness
    signs each of that agent's messages before delivery - identity, like the clock, is
    supplied by the transport, not the model - and the wire carries the signed form.
    """
    say = echo or (lambda s: None)
    log: List[Message] = []
    wire: List[str] = []
    issues: List[Issue] = []
    notes: List[str] = []
    speaker = first
    prefix = (clock.line() + "\n") if clock else ""
    incoming = prefix + opening

    for _ in range(max_turns):
        m, raw = None, ""
        for attempt in range(retries + 1):
            raw = agents[speaker].turn(incoming)
            if codebook is not None:
                bad = codebook.unresolved_forms(raw)
                if bad:
                    notes.append(f"@{speaker} rule-3 violation: unknown forms {bad}")
            try:
                terms = codebook.unpack(raw) if codebook is not None else parse(dense_expand(raw))
                if len(terms) != 1:
                    raise ModelError(f"{len(terms)} terms in one turn")
                m = Message.from_form(terms[0])
                break
            except AICLError as e:
                notes.append(f"@{speaker} invalid (attempt {attempt + 1}): {e} | {raw[:200]}")
                incoming = f"; harness: your message was not valid AICL ({e}); resend one valid AICL message"
        if m is None:
            notes.append(f"@{speaker} failed {retries + 1} times; aborted")
            say(f"!! @{speaker} failed {retries + 1} times; aborting")
            break
        if signers and speaker in signers:
            from .signing import sign_form
            m = Message.from_form(sign_form(m.to_form(), signers[speaker]))
            raw = to_text(m.to_form())        # the wire carries the signed form
        canon = to_text(m.to_form())
        say(canon if raw == canon else f"wire:  {raw}\ncanon: {canon}")
        for i in validate_message(m.to_form()):
            say(f"    {i}")
        log.append(m)
        wire.append(raw)
        if m.act == "end":
            break
        if clock:
            clock.tick()
            prefix = clock.line() + "\n"
        incoming = prefix + raw
        speaker = m.receiver if m.receiver in agents else next(n for n in agents if n != speaker)

    issues = validate_conversation(log, known_terms, now=now)
    for i in issues:
        say(f"  {i}")
    return DialogueResult(log, wire, issues, notes)
