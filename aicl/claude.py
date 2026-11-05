"""Claude-backed ask function (same shape as gemini.text_ask), for dialogues.

Optional: the anthropic SDK is imported lazily and a clear error is raised when
ANTHROPIC_API_KEY is missing.

Server-side refusal fallbacks (`fallbacks="default"`) are sent only to the models that
accept them; Claude Haiku 5.5 has none, so a Haiku call is a plain messages.create.
"""
from __future__ import annotations

from typing import Callable, Dict, List

from .env import load_dotenv

DEFAULT_MODEL = "claude-opus-5-5"
CHEAP_MODEL = "claude-haiku-5-5"      # about 1/40 of Opus 5.5's price per token
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
# USD per 1M tokens (input, output); a cache write costs 1.25x input, a cache read 0.1x.
PRICES = {"claude-haiku-5-5": (0.10, 0.50)}

# Tokens used in this process, per model: what the night report prints as the cost of a run.
USAGE: Dict[str, Dict[str, int]] = {}


def _tally(model: str, usage) -> None:
    if usage is None:
        return
    u = USAGE.setdefault(model, {"calls": 0, "input": 0, "output": 0, "cache_write": 0, "cache_read": 0})
    u["calls"] += 1
    u["input"] += getattr(usage, "input_tokens", 0) or 0
    u["output"] += getattr(usage, "output_tokens", 0) or 0
    u["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0
    u["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0


def cost_usd(model: str, u: Dict[str, int]):
    """Estimated cost of `u` in USD, or None for a model without a price here."""
    if model not in PRICES:
        return None
    pin, pout = PRICES[model]
    return (u["input"] * pin + u["cache_write"] * pin * 1.25 + u["cache_read"] * pin * 0.1
            + u["output"] * pout) / 1_000_000


def usage_lines() -> List[str]:
    out = []
    for model, u in USAGE.items():
        c = cost_usd(model, u)
        out.append(f"{model}: {u['calls']} calls, input {u['input']:,} + cache write {u['cache_write']:,} "
                   f"+ cache read {u['cache_read']:,} tokens, output {u['output']:,} tokens"
                   + (f", about ${c:.4f}" if c is not None else ""))
    return out


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
        # Automatic caching: the system prompt (rulebook, role, directory: thousands of tokens)
        # and the history so far are the same prefix on every call of a network agent.
        kw = dict(model=model, max_tokens=max_tokens, system=system, messages=history,
                  output_config={"effort": effort}, cache_control={"type": "ephemeral"})
        if model in FALLBACK_MODELS:
            resp = client.beta.messages.create(**kw, betas=["server-side-fallback-2026-07-01"],
                                               fallbacks="default")
        else:
            resp = client.messages.create(**kw)
        _tally(model, getattr(resp, "usage", None))
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"claude refused ({resp.stop_details and resp.stop_details.category})")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError(f"claude stopped at max_tokens ({max_tokens}); the answer is incomplete")
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    return ask
