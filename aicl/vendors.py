"""Pick a vendor's ask function by name, so runners can take --a claude --b muse.

Each entry returns ask(system, history) -> str. Keys and SDKs are only needed for
the vendors actually chosen. `sleep` is a pause after each call for free tiers.

With `fallback=True`, a role whose API is unavailable - no key, no SDK, quota used up, the
host cannot be resolved, the key refused - switches for the rest of the run to the vendor's
chat website through aicl/webchat.py (Gemini -> gemini.google.com, Muse -> meta.ai). Claude has
no web fallback. Set AICL_FORCE_WEB=gemini (or muse) to skip the API and test the browser path.
"""
from __future__ import annotations

import os
from typing import Callable, List, Optional

Ask = Callable[[str, List[dict]], str]

VENDORS = ("claude", "gemini", "muse")
WEB_SITE = {"gemini": "gemini", "muse": "meta"}

UNAVAILABLE = ("is not set", "No module named", "PerDay", "per day", "quota", "RESOURCE_EXHAUSTED", "429",
               "getaddrinfo", "Name or service not known", "NameResolution", "ConnectError", "ConnectionError",
               "Failed to establish", "401", "403", "PERMISSION_DENIED", "API key", "api_key", "US only",
               "UNAVAILABLE", "503")


def is_unavailable(e: BaseException) -> bool:
    """True for failures of the service itself (key, quota, network), never for a bad answer."""
    text = f"{type(e).__name__}: {e}"
    return isinstance(e, (ImportError, ConnectionError)) or any(k in text for k in UNAVAILABLE)


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
    raise ValueError(f"unknown vendor {vendor!r}; choose one of {', '.join(VENDORS)}")


def with_web_fallback(vendor: str, api_factory: Callable[[], Ask], web_factory: Callable[[], Ask],
                      note: Callable[[str], None] = print) -> Ask:
    """Try the API; on an availability failure switch to the web chat for good and retry the turn there."""
    state = {"api": None, "web": None, "why": None}
    forced = vendor in [v.strip().lower() for v in os.environ.get("AICL_FORCE_WEB", "").split(",")]

    def switch(why: str) -> None:
        state["why"] = why
        note(f"! {vendor} API unavailable ({why[:120]}); switching this role to the browser version")
        state["web"] = web_factory()

    def ask(system: str, history: List[dict]) -> str:
        if state["web"] is None:
            if forced:
                switch("AICL_FORCE_WEB")
            else:
                try:
                    if state["api"] is None:
                        state["api"] = api_factory()
                    return state["api"](system, history)
                except Exception as e:
                    if not is_unavailable(e):
                        raise
                    switch(f"{type(e).__name__}: {e}")
        return state["web"](system, history)

    ask.state = state
    return ask


def text_ask(vendor: str, model: Optional[str] = None, sleep: float = 0.0, fallback: bool = False,
             note: Callable[[str], None] = print) -> Ask:
    vendor = vendor.lower()
    if vendor not in VENDORS:
        raise ValueError(f"unknown vendor {vendor!r}; choose one of {', '.join(VENDORS)}")
    if not fallback or vendor not in WEB_SITE:
        return _api_ask(vendor, model, sleep)

    def web():
        from . import webchat
        return webchat.text_ask(WEB_SITE[vendor])

    return with_web_fallback(vendor, lambda: _api_ask(vendor, model, sleep), web, note)


def default_model(vendor: str) -> str:
    vendor = vendor.lower()
    if vendor not in VENDORS:
        raise ValueError(f"unknown vendor {vendor!r}; choose one of {', '.join(VENDORS)}")
    mod = __import__(f"aicl.{vendor}", fromlist=["x"])
    return getattr(mod, "DEFAULT_MODEL", None) or getattr(mod, "DEFAULT_TEXT_MODEL")


def describe(vendor: str, model: Optional[str] = None) -> str:
    return f"{vendor} ({model or default_model(vendor)})"
