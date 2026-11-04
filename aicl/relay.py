"""An AICL relay: the place where independent agents meet over HTTP.

Everything before this module ran both agents in one process. The relay hosts
conversations on the network instead: each agent POSTs its messages and long-polls
for the ones addressed to it, from its own process, machine or vendor. The language
rules are enforced at the network boundary — an invalid message is rejected with 400
and never delivered — and the whole conversation stays auditable (`/transcript`,
`/check`) for humans and validators alike.

Pure stdlib. No authentication: bind it to localhost, or put your own auth in front.
With `keys` ({agent: base64url Ed25519 public key}), every message from a bound agent
must carry a valid `:sig` (SPEC §3.1) or it is rejected at the door.

HTTP API (text/plain AICL in, JSON out unless noted):
  POST /c/{conv}                     one AICL message (readable or dense)
                                     -> 200 {"n": index, "warnings": […]}
                                     -> 400 {"errors": […]} and the message is NOT delivered
  GET  /c/{conv}?for=a&after=0&wait=25
                                     -> 200 {"messages": [{"n": i, "text": "…"}], "next": i}
                                        (messages to @a or *, long-polling up to `wait` s)
  GET  /c/{conv}/transcript          -> 200 text/plain, the canonical conversation
  GET  /c/{conv}/check               -> 200 text/plain, validate_conversation output
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional

from datetime import datetime

from .dense import expand as dense_expand
from .model import AICLError, Message
from .parser import parse
from .printer import to_text
from .validate import _as_datetime, validate_conversation, validate_message

MAX_MESSAGE_BYTES = 1 << 20


class Relay:
    """Conversation state shared by the HTTP handlers."""

    def __init__(self, known_terms: tuple = (), keys: Optional[Dict[str, str]] = None,
                 max_skew: Optional[float] = 300.0, now_fn=None):
        """`max_skew`: reject a message whose :at differs from the relay clock by more
        than this many seconds (None disables). The relay is the conversation's clock:
        an LLM cannot know the time, so the transport supplies it (`now` in every poll,
        `; now` prefixed by attend()) and polices claims about it (`at-skew`)."""
        self.known = tuple(known_terms)
        self.keys = keys
        self.max_skew = max_skew
        self.now_fn = now_fn or (lambda: datetime.now().astimezone())
        self.convs: Dict[str, List[Message]] = {}
        self.lock = threading.Condition()

    def now_text(self) -> str:
        return self.now_fn().isoformat(timespec="minutes")

    # ------------------------------------------------------------------ write

    def post(self, conv: str, text: str) -> tuple:
        """Validate and append one message; returns (index, warnings) or raises RelayReject."""
        try:
            terms = parse(dense_expand(text))
            if len(terms) != 1:
                raise AICLError(f"{len(terms)} terms in one request; send one message at a time")
            m = Message.from_form(terms[0])
        except AICLError as e:
            raise RelayReject([f"error parse: {e}"]) from None
        issues = validate_message(m.to_form())
        if self.keys is not None:
            from .signing import sig_of, verify_form
            if m.sender in self.keys:
                if sig_of(m.to_form()) is None:
                    raise RelayReject([f"error sig-missing: @{m.sender} must sign (SPEC §3.1)"])
                if not verify_form(m.to_form(), self.keys[m.sender]):
                    raise RelayReject([f"error sig-invalid: the :sig does not verify against @{m.sender}'s key"])
        errors = [str(i) for i in issues if i.level == "error"]
        if errors:
            raise RelayReject(errors)
        if self.max_skew is not None:
            at = _as_datetime(m.kw.get("at"))
            if at is not None:
                skew = abs((at - self.now_fn()).total_seconds())
                if skew > self.max_skew:
                    raise RelayReject([f"error at-skew: your :at is off the relay clock by {skew:.0f}s; "
                                       f"now is {self.now_text()}"])
        with self.lock:
            log = self.convs.setdefault(conv, [])
            if any(prev.id == m.id for prev in log):
                raise RelayReject([f"error dup-id: #{m.id} was already sent in this conversation"])
            log.append(m)
            n = len(log)
            self.lock.notify_all()
        return n, [str(i) for i in issues]

    # ------------------------------------------------------------------- read

    def read(self, conv: str, for_agent: Optional[str], after: int, wait: float) -> tuple:
        """Messages after index `after` addressed to `for_agent` (or *); long-polls up to `wait` s."""
        def visible():
            log = self.convs.get(conv, [])
            out = [(i + 1, m) for i, m in enumerate(log[after:], start=after)
                   if for_agent is None or m.receiver in (for_agent, "*")]
            return out, len(log)
        with self.lock:
            msgs, total = visible()
            if not msgs and wait > 0:
                self.lock.wait_for(lambda: visible()[0], timeout=wait)
                msgs, total = visible()
        return msgs, total

    def transcript(self, conv: str) -> str:
        with self.lock:
            return "\n".join(to_text(m.to_form()) for m in self.convs.get(conv, []))

    def check(self, conv: str) -> str:
        with self.lock:
            log = list(self.convs.get(conv, []))
        issues = validate_conversation(log, self.known, now=self.now_fn(), keys=self.keys)
        return "\n".join(str(i) for i in issues) or "clean"


class RelayReject(Exception):
    def __init__(self, issues: List[str]):
        super().__init__("; ".join(issues))
        self.issues = issues


# ---------------------------------------------------------------------- server

def make_server(relay: Relay, host: str = "127.0.0.1", port: int = 8700) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):   # quiet
            pass

        def _send(self, code: int, body: str, ctype: str = "application/json"):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            path = urllib.parse.urlparse(self.path)
            parts = [p for p in path.path.split("/") if p]
            if len(parts) != 2 or parts[0] != "c":
                return self._send(404, '{"errors": ["no such endpoint"]}')
            size = int(self.headers.get("Content-Length", 0))
            if size > MAX_MESSAGE_BYTES:
                return self._send(413, '{"errors": ["message too large"]}')
            text = self.rfile.read(size).decode("utf-8", errors="replace")
            try:
                n, warnings = relay.post(parts[1], text)
            except RelayReject as e:
                return self._send(400, json.dumps({"errors": e.issues}, ensure_ascii=False))
            self._send(200, json.dumps({"n": n, "warnings": warnings}, ensure_ascii=False))

        def do_GET(self):
            path = urllib.parse.urlparse(self.path)
            parts = [p for p in path.path.split("/") if p]
            if len(parts) >= 2 and parts[0] == "c":
                conv = parts[1]
                if len(parts) == 3 and parts[2] == "transcript":
                    return self._send(200, relay.transcript(conv) + "\n", "text/plain")
                if len(parts) == 3 and parts[2] == "check":
                    return self._send(200, relay.check(conv) + "\n", "text/plain")
                if len(parts) == 2:
                    q = urllib.parse.parse_qs(path.query)
                    for_agent = q.get("for", [None])[0]
                    after = int(q.get("after", ["0"])[0])
                    wait = min(float(q.get("wait", ["0"])[0]), 60.0)
                    msgs, total = relay.read(conv, for_agent and for_agent.lstrip("@"), after, wait)
                    return self._send(200, json.dumps(
                        {"messages": [{"n": n, "text": to_text(m.to_form())} for n, m in msgs],
                         "next": total, "now": relay.now_text()}, ensure_ascii=False))
            self._send(404, '{"errors": ["no such endpoint"]}')

    return ThreadingHTTPServer((host, port), Handler)


# ---------------------------------------------------------------------- client

class RelayClient:
    """One agent's connection to a conversation on a relay."""

    def __init__(self, base: str, conv: str, agent: str):
        self.base = base.rstrip("/")
        self.conv = conv
        self.agent = agent.lstrip("@")
        self.cursor = 0
        self.now: Optional[str] = None       # the relay's clock, updated by every poll

    def _url(self, suffix: str = "", **params) -> str:
        q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        return f"{self.base}/c/{self.conv}{suffix}" + (f"?{q}" if q else "")

    def send(self, text: str) -> dict:
        """POST one message; raises RelayReject if the relay refuses it."""
        req = urllib.request.Request(self._url(), data=text.encode("utf-8"), method="POST",
                                     headers={"Content-Type": "text/plain; charset=utf-8"})
        try:
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                issues = json.loads(body).get("errors", [body])
            except ValueError:
                issues = [body]
            raise RelayReject(issues) from None

    def poll(self, wait: float = 25.0) -> List[str]:
        """Messages addressed to this agent since the last poll (long-polling)."""
        with urllib.request.urlopen(self._url(**{"for": self.agent},
                                              after=self.cursor, wait=wait)) as r:
            data = json.loads(r.read().decode("utf-8"))
        self.cursor = data["next"]
        self.now = data.get("now")
        return [m["text"] for m in data["messages"]]

    def transcript(self) -> str:
        with urllib.request.urlopen(self._url("/transcript")) as r:
            return r.read().decode("utf-8")


def attend(client: RelayClient, agent, opening: Optional[str] = None,
           max_turns: int = 50, retries: int = 1, echo=print) -> None:
    """Connect an AiclAgent (aicl.dialogue) to a relay and converse until (end …).

    Runs in this process; the counterpart runs wherever it likes. `opening` makes this
    agent speak first (it is a harness note handed to the LLM, not sent to the relay).
    The relay's clock is prefixed to every input as a `; now <instant>` line, so the
    agent has a true time to stamp `:at` with; a rejected message (at-skew included)
    is bounced back once with the relay's reason.
    """
    say = echo or (lambda s: None)

    def clocked(text: str) -> str:
        return (f"; now {client.now}\n" + text) if client.now else text

    def speak(incoming: str) -> Optional[Message]:
        for attempt in range(retries + 1):
            raw = agent.turn(incoming)
            try:
                client.send(raw)
                return Message.from_form(parse(dense_expand(raw))[0])
            except RelayReject as e:
                say(f"!! relay rejected @{client.agent} (attempt {attempt + 1}): {'; '.join(e.issues)}")
                incoming = clocked("; harness: the relay rejected your message (" + "; ".join(e.issues)
                                   + "); resend one valid AICL message")
        return None

    if opening is not None:
        client.poll(wait=0)                   # learn the relay's clock before speaking
        m = speak(clocked(opening))
        if m is None or m.act == "end":
            return
    for _ in range(max_turns):
        for text in client.poll():
            say(f"@{client.agent} <- {text}")
            incoming_act = Message.from_form(parse(dense_expand(text))[0]).act
            if incoming_act == "end":
                return
            m = speak(clocked(text))
            if m is None or m.act == "end":
                return
