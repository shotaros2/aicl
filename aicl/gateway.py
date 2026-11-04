"""Gateway: one requester (e.g. Claude) talking AICL to a bus of specialists.

The requester composes AICL messages itself; the gateway validates them,
delivers them, and hands back every reply addressed to the requester plus
the artifacts it received. This is what an MCP tool, an HTTP endpoint or a
chat relay wraps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .coop import Agent, Bus, Hub, LLMPlanner, ProtocolError, RecipePlanner, SkillAgent, TaskSpec, _is
from .dense import expand as dense_expand
from .model import Form, KList, Message, Str
from .parser import parse
from .printer import to_text


@dataclass
class Exchange:
    sent: List[Message]
    replies: List[Message]
    artifacts: List[Form] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def text(self) -> str:
        return "\n".join(to_text(m.to_form()) for m in self.replies)


class Gateway:
    def __init__(self, requester_id: str = "claude", specialists: Iterable[Agent] = (), planner=None):
        self.bus = Bus()
        self.requester = Agent(requester_id)
        self.hub = Hub(planner or RecipePlanner([]))
        self.bus.add(self.hub, self.requester, *specialists)
        for s in specialists:
            for f in s.announce("hub"):
                self.bus.send(f)

    # ------------------------------------------------------------ queries

    def capabilities(self) -> Dict[str, str]:
        return dict(self.hub.registry)

    def transcript(self) -> str:
        return self.bus.text()

    def artifacts(self) -> List[Form]:
        out = []
        for m in self.bus.transcript:
            if m.act == "done" and m.receiver == self.requester.id:
                for b in m.body:
                    items = b.items if isinstance(b, KList) else [b]
                    out += [a for a in items if _is(a, "artifact")]
        return out

    # --------------------------------------------------------------- send

    def send(self, text: str) -> Exchange:
        """Deliver one or more AICL messages (dense or readable) from the requester."""
        start = len(self.bus.transcript)
        sent: List[Message] = []
        errors: List[str] = []
        try:
            forms = parse(dense_expand(text))
        except Exception as e:
            return Exchange([], [], [], [f"not AICL: {e}"])
        for f in forms:
            try:
                m = Message.from_form(f)
            except Exception as e:
                errors.append(str(e))
                continue
            if m.sender != self.requester.id:
                errors.append(f"message #{m.id} claims to be from @{m.sender}; this gateway sends as @{self.requester.id}")
                continue
            # the requester's own numbering is respected but kept monotonic
            try:
                n = int(m.id.rsplit(".", 1)[1]) if m.id.startswith(self.requester.id + ".") else 0
                self.requester.seq = max(self.requester.seq, n)
            except ValueError:
                pass
            try:
                self.bus.send(m.to_form())
                sent.append(m)
            except ProtocolError as e:
                errors.append(f"#{m.id}: {e}")
        new = self.bus.transcript[start:]
        replies = [m for m in new if m.receiver == self.requester.id]
        artifacts = []
        for m in replies:
            if m.act == "done":
                for b in m.body:
                    items = b.items if isinstance(b, KList) else [b]
                    artifacts += [a for a in items if _is(a, "artifact")]
        return Exchange(sent, replies, artifacts, errors)


def artifact_path(art: Form) -> Optional[Path]:
    """Local file path of an artifact's :uri, if it is a file:// uri."""
    uri = art.kw.get("uri")
    if isinstance(uri, Str) and uri.text.startswith("file:"):
        from urllib.parse import unquote, urlparse
        p = urlparse(uri.text).path
        if len(p) > 2 and p[0] == "/" and p[2] == ":":   # /C:/… on Windows
            p = p[1:]
        return Path(unquote(p))
    return None


def default_gateway(requester_id: str = "claude", image_model: str = "svg", text_model: str = None,
                    out_dir: Path = Path("out")) -> Gateway:
    """Image specialist backed by Gemini (real image model, or SVG via the text model) and a Gemini planner."""
    from . import gemini
    text_model = text_model or gemini.DEFAULT_TEXT_MODEL
    ask = gemini.text_ask(text_model)
    fn = gemini.svg_image_fn(ask, out_dir) if image_model == "svg" else gemini.image_fn(image_model, out_dir)
    img = SkillAgent("img", "image-gen", fn)
    planner = LLMPlanner(lambda prompt: ask("You answer with exactly one AICL form and nothing else.",
                                            [{"role": "user", "content": prompt}]))
    return Gateway(requester_id, [img], planner)
