"""Claude-backed ask function (same shape as gemini.text_ask), for dialogues.

Optional: the anthropic SDK is imported lazily and a clear error is raised when
ANTHROPIC_API_KEY is missing.

Server-side refusal fallbacks (`fallbacks="default"`) are sent only to the models that
accept them; Claude Haiku 5.5 has none, so a Haiku call is a plain messages.create.
"""
from __future__ import annotations

from typing import Callable, List

from .env import load_dotenv

DEFAULT_MODEL = "claude-opus-5-5"
CHEAP_MODEL = "claude-haiku-5-5"      # about 1/40 of Opus 5.5's price per token
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


def text_ask(model: str = DEFAULT_MODEL, effort: str = "low", max_tokens: int = 16000,
             client=None) -> Callable[[str, List[dict]], str]:
    """ask(system, history) -> str, the shape AiclAgent and LLMPlanner expect.

    `max_tokens` covers thinking as well as the answer, and an app the coder writes runs to
    several thousand tokens, so it is not kept small."""
    load_dotenv()
    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    def ask(system: str, history: List[dict]) -> str:
        kw = dict(model=model, max_tokens=max_tokens, system=system, messages=history,
                  output_config={"effort": effort})
        if model in FALLBACK_MODELS:
            resp = client.beta.messages.create(**kw, betas=["server-side-fallback-2026-07-01"],
                                               fallbacks="default")
        else:
            resp = client.messages.create(**kw)
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"claude refused ({resp.stop_details and resp.stop_details.category})")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError(f"claude stopped at max_tokens ({max_tokens}); the answer is incomplete")
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    return ask
