"""Pick a vendor's ask function by name, so runners can take --a claude --b muse.

Each entry returns ask(system, history) -> str. Keys and SDKs are only needed for
the vendors actually chosen. `sleep` is a pause after each call for free tiers.
`local` is a model on this PC (Ollama by default, aicl/local.py): free, so the busy roles go there.

`fallback` is what a role does when its API is unavailable - no key, no SDK, quota used up, the
host cannot be resolved, the key refused, the local server down:
  fallback=True or "web"  switch for the rest of the run to the vendor's chat website through
                          aicl/webchat.py (Gemini -> gemini.google.com, Muse -> meta.ai). Claude has
                          no web fallback. Set AICL_FORCE_WEB=gemini (or muse) to test the browser path.
  fallback="local"        switch to the local model instead.

`escalate_to` (for a local role) moves the role to a cloud vendor when the local model is in
trouble: two invalid AICL answers in a row, two rejections (rej) from the checker, an answer
slower than `slow_seconds`, or the local server down. The network records each escalation
and why, so the morning report shows how often (and so roughly how much) the cloud was used.
"""
from __future__ import annotations

import os
import time
from typing import Callable, List, Optional, Union

Ask = Callable[[str, List[dict]], str]

VENDORS = ("claude", "gemini", "muse", "local")
WEB_SITE = {"gemini": "gemini", "muse": "meta"}

UNAVAILABLE = ("is not set", "No module named", "PerDay", "per day", "quota", "RESOURCE_EXHAUSTED", "429",
               "getaddrinfo", "Name or service not known", "NameResolution", "ConnectError", "ConnectionError",
               "Failed to establish", "401", "403", "PERMISSION_DENIED", "API key", "api_key", "US only",
               "UNAVAILABLE", "503", "URLError", "Connection refused", "10061")


def is_unavailable(e: BaseException) -> bool:
    """True for failures of the service itself (key, quota, network), never for a bad answer."""
    text = f"{type(e).__name__}: {e}"
    return isinstance(e, (ImportError, ConnectionError)) or any(k in text for k in UNAVAILABLE)


def is_timeout(e: BaseException) -> bool:
    return isinstance(e, TimeoutError) or "timed out" in str(e)


def _api_ask(vendor: str, model: Optional[str], sleep: float) -> Ask:
    vendor = vendor.lower()
    kw = {"model": model} if model else {}
    if vendor == "claude":
        from . import claude
        return claude.text_ask(**kw)
    if vendor == "gemini":
        from . import gemini
        return gemini.text_ask(sleep=sleep, **kw)
    if vendor == "muse":
        from . import muse
        return muse.text_ask(sleep=sleep, **kw)
    if vendor == "local":
        from . import local
        return local.text_ask(sleep=sleep, **kw)
    raise ValueError(f"unknown vendor {vendor!r}; choose one of {', '.join(VENDORS)}")


def with_web_fallback(vendor: str, api_factory: Callable[[], Ask], web_factory: Callable[[], Ask],
                      note: Callable[[str], None] = print, target: str = "the browser version") -> Ask:
    """Try the API; on an availability failure switch to the fallback for good and retry the turn there."""
    state = {"api": None, "web": None, "why": None}
    forced = target == "the browser version" and \
        vendor in [v.strip().lower() for v in os.environ.get("AICL_FORCE_WEB", "").split(",")]

    def switch(why: str) -> None:
        state["why"] = why
        note(f"! {vendor} API unavailable ({why[:120]}); switching this role to {target}")
        state["web"] = web_factory()

    def ask(system: str, history: List[dict], **kw) -> str:
        if state["web"] is None:
            if forced:
                switch("AICL_FORCE_WEB")
            else:
                try:
                    if state["api"] is None:
                        state["api"] = api_factory()
                    return state["api"](system, history, **kw)
                except Exception as e:
                    if not is_unavailable(e):
                        raise
                    switch(f"{type(e).__name__}: {e}")
        return state["web"](system, history, **kw)

    ask.state = state
    return ask


def with_escalation(vendor: str, primary_factory: Callable[[], Ask], cloud: str,
                    cloud_factory: Callable[[], Ask], max_invalid: int = 2, max_rejected: int = 2,
                    slow_seconds: float = 180.0, note: Callable[[str], None] = print) -> Ask:
    """Run the role on `vendor` (normally local) and move it to `cloud` for the rest of the run
    when it is in trouble. The network tells the ask what happened to each answer through
    `ask.observe("valid" | "invalid" | "rejected")` and collects `ask.pending_notes()` into its
    record, so every escalation and its reason reaches the report."""
    state = {"primary": None, "cloud": None, "invalid_streak": 0, "rejected": 0,
             "escalations": [], "pending": []}

    def escalate(why: str) -> None:
        state["escalations"].append(why)
        msg = f"escalated to {cloud}: {why}"
        state["pending"].append(msg)
        note(f"! {vendor} role {msg}")
        state["cloud"] = cloud_factory()

    def ask(system: str, history: List[dict], **kw) -> str:     # kw: schema= for aicl.actions
        if state["cloud"] is None:
            try:
                if state["primary"] is None:
                    state["primary"] = primary_factory()
                started = time.monotonic()
                out = state["primary"](system, history, **kw)
                took = time.monotonic() - started
                if took > slow_seconds:            # this answer is kept; the next ones go to the cloud
                    escalate(f"too slow ({took:.0f}s for one answer)"
                             + (", and it was empty" if not out.strip() else ""))
                    if not out.strip():
                        # Seen with qwen3.5:9b as chief: 201 s of thinking, then nothing, and the
                        # network fell quiet. The cloud answers this same event instead.
                        return state["cloud"](system, history, **kw)
                return out
            except Exception as e:
                if not (is_unavailable(e) or is_timeout(e)):
                    raise
                escalate(f"{vendor} unavailable or stalled ({type(e).__name__}: {str(e)[:100]})")
        return state["cloud"](system, history, **kw)

    def observe(kind: str, detail: str = "") -> bool:
        """Returns True when this observation moved the role to the cloud just now."""
        if state["cloud"] is not None:
            return False
        if kind == "valid":
            state["invalid_streak"] = 0
        elif kind == "invalid":
            state["invalid_streak"] += 1
            if state["invalid_streak"] >= max_invalid:
                escalate(f"{state['invalid_streak']} invalid AICL answers in a row ({detail[:80]})")
                return True
        elif kind == "rejected":
            state["rejected"] += 1
            if state["rejected"] >= max_rejected:
                escalate(f"rejected {state['rejected']} times ({detail[:80]})")
                return True
        return False

    def pending_notes() -> List[str]:
        out, state["pending"] = state["pending"], []
        return out

    ask.state = state
    ask.observe = observe
    ask.pending_notes = pending_notes
    return ask


def text_ask(vendor: str, model: Optional[str] = None, sleep: float = 0.0,
             fallback: Union[bool, str] = False, escalate_to: Optional[str] = None,
             escalate_model: Optional[str] = None,
             note: Callable[[str], None] = print) -> Ask:
    vendor = vendor.lower()
    if vendor not in VENDORS:
        raise ValueError(f"unknown vendor {vendor!r}; choose one of {', '.join(VENDORS)}")
    api = lambda: _api_ask(vendor, model, sleep)

    if escalate_to:
        escalate_to = escalate_to.lower()
        if escalate_to not in VENDORS or escalate_to == vendor:
            raise ValueError(f"cannot escalate {vendor} to {escalate_to!r}")
        cloud_sleep = 0.0 if escalate_to in ("claude", "local") else 4.0
        label = f"{escalate_to} ({escalate_model})" if escalate_model else escalate_to
        return with_escalation(vendor, api, label, lambda: _api_ask(escalate_to, escalate_model, cloud_sleep),
                               note=note)

    if fallback == "local" and vendor != "local":
        return with_web_fallback(vendor, api, lambda: _api_ask("local", None, 0.0), note,
                                 target=f"the local model ({describe('local')})")
    if fallback in (True, "web") and vendor in WEB_SITE:
        def web():
            from . import webchat
            return webchat.text_ask(WEB_SITE[vendor])
        return with_web_fallback(vendor, api, web, note)
    return api()


def default_model(vendor: str) -> str:
    vendor = vendor.lower()
    if vendor not in VENDORS:
        raise ValueError(f"unknown vendor {vendor!r}; choose one of {', '.join(VENDORS)}")
    if vendor == "local":
        from . import local
        return local.model_name()
    mod = __import__(f"aicl.{vendor}", fromlist=["x"])
    return getattr(mod, "DEFAULT_MODEL", None) or getattr(mod, "DEFAULT_TEXT_MODEL")


def describe(vendor: str, model: Optional[str] = None) -> str:
    return f"{vendor} ({model or default_model(vendor)})"
