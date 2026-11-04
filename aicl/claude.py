"""Claude-backed ask function (same shape as gemini.text_ask), for dialogues.

Optional: the anthropic SDK is imported lazily and a clear error is raised when
ANTHROPIC_API_KEY is missing.
"""
from __future__ import annotations

from typing import Callable, List

from .env import load_dotenv

DEFAULT_MODEL = "claude-opus-5-5"


def text_ask(model: str = DEFAULT_MODEL, effort: str = "low", max_tokens: int = 2000,
             client=None) -> Callable[[str, List[dict]], str]:
    """ask(system, history) -> str, the shape AiclAgent and LLMPlanner expect."""
    load_dotenv()
    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    def ask(system: str, history: List[dict]) -> str:
        resp = client.beta.messages.create(
            model=model, max_tokens=max_tokens, system=system, messages=history,
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"claude refused ({resp.stop_details and resp.stop_details.category})")
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    return ask
