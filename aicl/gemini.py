"""Gemini-backed building blocks for specialists (shared by the examples and the gateway).

Everything here is optional: the google-genai SDK is imported lazily and the
functions raise a clear error when GEMINI_API_KEY is missing.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List

from .env import load_dotenv
from .model import Str, Term
from .printer import to_text

DEFAULT_TEXT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_IMAGE_MODEL = "gemini-nano-banana-2.1"


class QuotaExhausted(RuntimeError):
    pass


def with_retry(fn, attempts: int = 5, wait: float = 5.0, what: str = ""):
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            if "PerDay" in msg or "per day" in msg:
                raise QuotaExhausted(f"daily free-tier quota exhausted for {what or 'this model'}") from None
            if i == attempts - 1 or not any(k in msg for k in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                raise
            print(f"  transient error, retrying in {wait:.0f}s: {msg[:80]}", file=sys.stderr)
            time.sleep(wait)
            wait = min(wait * 2, 60)


def client():
    load_dotenv()
    from google import genai
    return genai.Client()   # reads GEMINI_API_KEY


def text_ask(model: str = DEFAULT_TEXT_MODEL, sleep: float = 0.0, cl=None) -> Callable[[str, List[dict]], str]:
    """ask(system, history) -> str, the shape LLMAgent and LLMPlanner expect."""
    from google.genai import types
    cl = cl or client()

    def ask(system: str, history: List[dict]) -> str:
        contents = [types.Content(role="user" if h["role"] == "user" else "model",
                                  parts=[types.Part.from_text(text=h["content"])]) for h in history]
        cfg = types.GenerateContentConfig(system_instruction=system, temperature=0)
        resp = with_retry(lambda: cl.models.generate_content(model=model, contents=contents, config=cfg),
                          what=f"text model {model}")
        if sleep:
            time.sleep(sleep)
        return resp.text or ""
    return ask


def _prompt_of(inputs: Dict[str, Term]) -> str:
    p = inputs.get("prompt")
    return p.text if isinstance(p, Str) else to_text(p) if p is not None else "an image"


def image_fn(model: str = DEFAULT_IMAGE_MODEL, out_dir: Path = Path("out"), sleep: float = 0.0, cl=None):
    """SkillAgent function: calls a Gemini image model, saves the file, returns a coop:artifact dict."""
    from google.genai import types
    cl = cl or client()

    def generate(inputs: Dict[str, Term], task_id: str) -> dict:
        cfg = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
        resp = with_retry(lambda: cl.models.generate_content(model=model, contents=_prompt_of(inputs), config=cfg),
                          what=f"image model {model}")
        if sleep:
            time.sleep(sleep)
        for part in resp.candidates[0].content.parts:
            data = getattr(part, "inline_data", None)
            if data and data.data:
                out_dir.mkdir(parents=True, exist_ok=True)
                ext = "png" if "png" in data.mime_type else "jpg"
                path = out_dir / f"{task_id}.{ext}"
                path.write_bytes(data.data)
                return {"id": f"img-{task_id}", "type": "image", "uri": path.resolve().as_uri(), "mime": data.mime_type}
        raise RuntimeError("image model returned no image")
    return generate


def svg_image_fn(ask: Callable[[str, List[dict]], str], out_dir: Path = Path("out")):
    """SkillAgent function: the text model draws the image as SVG (works on the free tier)."""

    def generate(inputs: Dict[str, Term], task_id: str) -> dict:
        raw = ask("You are an illustrator. Answer with one complete <svg …>…</svg> element (viewBox 0 0 1920 1080, "
                  "no external references, no scripts) and nothing else.",
                  [{"role": "user", "content": f"Draw: {_prompt_of(inputs)}"}])
        m = re.search(r"<svg.*?</svg>", raw, re.S)
        if not m:
            raise RuntimeError("text model returned no <svg> element")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{task_id}.svg"
        path.write_text(m.group(0), encoding="utf-8")
        return {"id": f"img-{task_id}", "type": "image", "uri": path.resolve().as_uri(), "mime": "image/svg+xml"}
    return generate
