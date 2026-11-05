"""A model running on this PC (Ollama by default), same shape as gemini.text_ask / claude.text_ask.

Ollama serves an OpenAI-compatible endpoint, so this reuses aicl/muse.py's standard-library
client: no SDK, no key. Calls cost nothing, which is why the busy roles (chief, writer,
scout) belong here and the cloud is kept for what needs quality (see vendors.with_escalation).

Configuration (.env or the environment):
    AICL_LOCAL_URL    default http://localhost:11434/v1   (LM Studio: http://localhost:1234/v1)
    AICL_LOCAL_MODEL  default qwen3:8b                     (fits an 8 GB GPU at Q4)

Reasoning models (qwen3, deepseek-r1) may put their thinking in <think>…</think>; it is
removed, because the network expects AICL and nothing else.
"""
from __future__ import annotations

import os
import re
from typing import Callable, List, Optional

from . import muse
from .env import load_dotenv

DEFAULT_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen3:8b"

_THINK = re.compile(r"<think>.*?(</think>|$)", re.S | re.I)


def model_name() -> str:
    load_dotenv()
    return os.environ.get("AICL_LOCAL_MODEL") or DEFAULT_MODEL


def strip_think(text: str) -> str:
    return _THINK.sub("", text).strip()


def text_ask(model: Optional[str] = None, base_url: Optional[str] = None, sleep: float = 0.0,
             timeout: float = 300.0, opener=None) -> Callable[[str, List[dict]], str]:
    """ask(system, history) -> str against the local OpenAI-compatible server.

    No retries here: a local server that is down or too slow is a reason to escalate to the
    cloud (vendors.with_escalation), not to wait. `opener` replaces urlopen in tests.
    """
    load_dotenv()
    inner = muse.text_ask(model=model or model_name(),
                          base_url=base_url or os.environ.get("AICL_LOCAL_URL") or DEFAULT_URL,
                          api_key="ollama", system_role="system", sleep=sleep, timeout=timeout,
                          attempts=1, opener=opener)

    def ask(system: str, history: List[dict]) -> str:
        return strip_think(inner(system, history))
    return ask
