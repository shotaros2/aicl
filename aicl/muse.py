"""Meta Muse Spark (Meta Model API) ask function, same shape as gemini.text_ask / claude.text_ask.

The Meta Model API is OpenAI-compatible, so this needs no SDK: a POST to
<base_url>/chat/completions with the standard library. The same function therefore
drives any OpenAI-compatible endpoint (set base_url / key_env / model), which keeps
`aicl/` dependency-free.

Facts as of 2026-11 (dev.meta.ai): base URL https://api.meta.ai/v1, model ids
muse-spark-1.1 / 1.2 / 1.3, key in MODEL_API_KEY created at dev.meta.ai/api-keys,
public preview open to developers in the US, pay-as-you-go. Meta recommends a
`developer` message over `system`. The model is also free in "Thinking" mode on
meta.ai, where the dense rulebook can be pasted by hand (see HANDOFF.md).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Callable, List, Optional

from .env import load_dotenv

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.1"
DEFAULT_KEY_ENV = "MODEL_API_KEY"


class AccessDenied(RuntimeError):
    """The endpoint refused the key: wrong key, or a region the preview is not open in."""


def _post(url: str, key: str, body: dict, timeout: float, opener=None) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "aicl/0.3"},
    )
    opener = opener or urllib.request.urlopen
    try:
        with opener(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 403):
            raise AccessDenied(
                f"{url} answered {e.code}: {detail}\n"
                "Check the key, and note that the Meta Model API public preview is open to developers "
                "in the US only; outside it, run the manual meta.ai experiment described in HANDOFF.md."
            ) from None
        raise RuntimeError(f"{url} answered {e.code}: {detail}") from None


def text_ask(model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE_URL, key_env: str = DEFAULT_KEY_ENV,
             api_key: Optional[str] = None, sleep: float = 0.0, timeout: float = 120.0,
             system_role: str = "developer", attempts: int = 4,
             opener=None) -> Callable[[str, List[dict]], str]:
    """ask(system, history) -> str over an OpenAI-compatible chat-completions endpoint.

    Defaults target Meta's Muse Spark. `opener` replaces urllib.request.urlopen in tests.
    """
    load_dotenv()
    key = api_key or os.environ.get(key_env, "")
    if not key:
        raise RuntimeError(f"{key_env} is not set (put it in .env; keys are created at dev.meta.ai/api-keys)")
    url = base_url.rstrip("/") + "/chat/completions"

    def ask(system: str, history: List[dict]) -> str:
        body = {
            "model": model,
            "messages": [{"role": system_role, "content": system}]
                        + [{"role": h["role"], "content": h["content"]} for h in history],
            "temperature": 0,
        }
        wait = 5.0
        data = {}
        for i in range(attempts):
            try:
                data = _post(url, key, body, timeout, opener)
                break
            except AccessDenied:
                raise
            except Exception as e:                     # 429 / 5xx / network: retry with backoff
                msg = str(e)
                if i == attempts - 1 or not any(k in msg for k in ("429", "500", "502", "503", "504", "timed out")):
                    raise
                print(f"  transient error, retrying in {wait:.0f}s: {msg[:80]}", file=sys.stderr)
                time.sleep(wait)
                wait = min(wait * 2, 60)
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        if isinstance(content, list):                 # some servers return content parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if sleep:
            time.sleep(sleep)
        return content.strip()
    return ask
