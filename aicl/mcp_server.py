"""AICL gateway as an MCP server, so a model such as Claude can talk AICL to specialists.

The model composes AICL messages itself (as @claude), calls `aicl_send`, and gets
back the replies plus any image artifacts, which the client can display to the
user. Specialists are the cooperation-layer agents (today: a Gemini image agent
and a Gemini planner behind the hub).

Run (stdio):  python -m aicl.mcp_server
Register in Claude Code via the project's .mcp.json, or in Claude Desktop's config:
  {"mcpServers": {"aicl": {"command": "python", "args": ["-m", "aicl.mcp_server"], "cwd": "<repo>"}}}

Environment: GEMINI_API_KEY (or .env), AICL_IMAGE_MODEL (default "svg"; set e.g.
gemini-nano-banana-2.1 with API billing), AICL_TEXT_MODEL, AICL_OUT_DIR, AICL_REQUESTER (default claude).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from mcp.server.mcpserver import Image, MCPServer

from . import gateway as gw
from .env import load_dotenv
from .model import Str
from .printer import to_text

ROOT = Path(__file__).resolve().parents[1]
RULEBOOK = ROOT / "prompts" / "system_prompt_dense.md"

server = MCPServer(
    "aicl",
    instructions=(
        "AICL (AI Common Language) gateway. You are @claude on a bus of specialist agents. "
        "Call aicl_rulebook once to learn the language, aicl_capabilities to see skills, then send "
        "AICL messages with aicl_send, e.g. (D claude.1>img (coop:task t1 image-gen :in {prompt \"...\"})). "
        "Replies come back as AICL; image artifacts are returned as images you can show the user."
    ),
)
_gateway: Optional[gw.Gateway] = None


def get_gateway() -> gw.Gateway:
    global _gateway
    if _gateway is None:
        load_dotenv()
        _gateway = gw.default_gateway(
            requester_id=os.environ.get("AICL_REQUESTER", "claude"),
            image_model=os.environ.get("AICL_IMAGE_MODEL", "svg"),
            text_model=os.environ.get("AICL_TEXT_MODEL"),
            out_dir=Path(os.environ.get("AICL_OUT_DIR", ROOT / "out")),
        )
    return _gateway


@server.tool()
def aicl_rulebook() -> str:
    """The AICL dense-form language reference. Read it once; then speak only AICL to the specialists."""
    text = RULEBOOK.read_text(encoding="utf-8").split("---", 1)[1].strip()
    return text.replace("`me`", "`claude`").replace("me.N", "claude.N")


@server.tool()
def aicl_capabilities() -> str:
    """Skills registered on the bus and which agent provides each, as an AICL binding list."""
    caps = get_gateway().capabilities()
    rows = " ".join(f"{{$skill {s} $agent @{a}}}" for s, a in sorted(caps.items()))
    return f"[{rows}]" if rows else "(none)"


@server.tool()
def aicl_send(message: str) -> list:
    """Send one or more AICL messages from @claude (dense or readable form).

    Returns the AICL replies addressed to you, gateway errors (if your message was not valid
    AICL), and any image artifacts as images. Example:
    (D claude.1>img (coop:task t1 image-gen :in {prompt "Tokyo skyline at night, photorealistic"}))
    """
    ex = get_gateway().send(message)
    parts: list = []
    if ex.errors:
        parts.append("; gateway errors:\n" + "\n".join(f"; {e}" for e in ex.errors))
    parts.append(ex.text() if ex.replies else "; no reply addressed to you")
    for art in ex.artifacts:
        path = gw.artifact_path(art)
        mime = art.kw.get("mime")
        if path and path.exists() and isinstance(mime, Str) and mime.text in ("image/png", "image/jpeg"):
            parts.append(Image(path=str(path)))
        elif path:
            parts.append(f"; artifact {art.args[0].name}: {path}")
    return parts


@server.tool()
def aicl_transcript() -> str:
    """Every message exchanged on the bus so far, in readable AICL."""
    return get_gateway().transcript() or "; (empty)"


@server.tool()
def aicl_check() -> str:
    """Validate the whole conversation so far against the AICL protocol rules."""
    issues = get_gateway().bus.check()
    return "\n".join(str(i) for i in issues) or "; 0 issues"


def main() -> None:
    # stdio is the protocol channel: keep every library log off stdout.
    import logging
    import sys
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, force=True)
    for name in ("httpx", "httpcore", "google_genai", "google.genai", "mcp"):
        logging.getLogger(name).setLevel(logging.WARNING)
    server.run("stdio")


if __name__ == "__main__":
    main()
