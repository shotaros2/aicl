"""Pick a vendor's ask function by name, so runners can take --a claude --b muse.

Each entry returns ask(system, history) -> str. Keys and SDKs are only needed for
the vendors actually chosen. `sleep` is a pause after each call for free tiers.
"""
from __future__ import annotations

from typing import Callable, List, Optional

Ask = Callable[[str, List[dict]], str]

VENDORS = ("claude", "gemini", "muse")


def text_ask(vendor: str, model: Optional[str] = None, sleep: float = 0.0) -> Ask:
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


def default_model(vendor: str) -> str:
    vendor = vendor.lower()
    if vendor not in VENDORS:
        raise ValueError(f"unknown vendor {vendor!r}; choose one of {', '.join(VENDORS)}")
    mod = __import__(f"aicl.{vendor}", fromlist=["x"])
    return getattr(mod, "DEFAULT_MODEL", None) or getattr(mod, "DEFAULT_TEXT_MODEL")


def describe(vendor: str, model: Optional[str] = None) -> str:
    return f"{vendor} ({model or default_model(vendor)})"
