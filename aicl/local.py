"""A model running on this PC (Ollama by default), same shape as gemini.text_ask / claude.text_ask.

Calls cost nothing, which is why the busy roles (chief, writer, scout) belong here and the
cloud is kept for what needs quality (see vendors.with_escalation).

Ollama is called through its own /api/chat, not its OpenAI-compatible endpoint, because only
the native API takes `num_ctx`: Ollama's default context is 4096 tokens, the dense rulebook
alone is about 2,200, and a night-shift history overflows the rest - Ollama then drops the
oldest tokens, the rulebook first. Measured on the home PC (RTX 3070, qwen3.5:9b): 4096 runs
100% on the GPU, 8192 puts 12% on the CPU, 12288 14%, 16384 16%; so 12288 is the default.
Other OpenAI-compatible servers (LM Studio, …) are reached with AICL_LOCAL_API=openai.

Configuration (.env or the environment):
    AICL_LOCAL_URL    default http://localhost:11434/v1   (LM Studio: http://localhost:1234/v1)
    AICL_LOCAL_MODEL  default qwen3:8b
    AICL_LOCAL_CTX    default 12288   (Ollama only)
    AICL_LOCAL_API    ollama (default) | openai

Reasoning models may put their thinking in <think>…</think>; it is removed, because the
network expects AICL and nothing else.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Callable, List, Optional

from . import muse
from .env import load_dotenv

DEFAULT_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen3:8b"
DEFAULT_CTX = 12288

_THINK = re.compile(r"<think>.*?(</think>|$)", re.S | re.I)


def model_name() -> str:
    load_dotenv()
    return os.environ.get("AICL_LOCAL_MODEL") or DEFAULT_MODEL


def strip_think(text: str) -> str:
    return _THINK.sub("", text).strip()


def _native_ask(model: str, base_url: str, ctx: int, sleep: float, timeout: float, opener):
    root = base_url.rstrip("/")
    root = root[:-3] if root.endswith("/v1") else root
    url = root + "/api/chat"
    opener = opener or urllib.request.urlopen

    def ask(system: str, history: List[dict]) -> str:
        body = {"model": model, "stream": False,
                "options": {"num_ctx": ctx, "temperature": 0},
                "messages": [{"role": "system", "content": system}]
                            + [{"role": h["role"], "content": h["content"]} for h in history]}
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": "aicl/0.3"})
        try:
            with opener(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{url} answered {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
        if sleep:
            time.sleep(sleep)
        return strip_think((data.get("message") or {}).get("content") or "")
    return ask


def text_ask(model: Optional[str] = None, base_url: Optional[str] = None, sleep: float = 0.0,
             timeout: float = 300.0, ctx: Optional[int] = None, api: Optional[str] = None,
             opener=None) -> Callable[[str, List[dict]], str]:
    """ask(system, history) -> str against the local server.

    No retries here: a local server that is down or too slow is a reason to escalate to the
    cloud (vendors.with_escalation), not to wait. `opener` replaces urlopen in tests.
    """
    load_dotenv()
    model = model or model_name()
    base_url = base_url or os.environ.get("AICL_LOCAL_URL") or DEFAULT_URL
    api = (api or os.environ.get("AICL_LOCAL_API") or "ollama").lower()
    if api == "ollama":
        ctx = ctx or int(os.environ.get("AICL_LOCAL_CTX") or DEFAULT_CTX)
        return _native_ask(model, base_url, ctx, sleep, timeout, opener)
    inner = muse.text_ask(model=model, base_url=base_url, api_key="ollama", system_role="system",
                          sleep=sleep, timeout=timeout, attempts=1, opener=opener)

    def ask(system: str, history: List[dict]) -> str:
        return strip_think(inner(system, history))
    return ask
