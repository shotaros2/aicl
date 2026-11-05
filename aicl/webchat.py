"""Browser fallback: drive a consumer chat window (gemini.google.com, meta.ai) as an ask() function.

When a vendor's API is unavailable - no key, quota used up, the host cannot be resolved - the
network can switch that role to the vendor's chat website instead (vendors.text_ask(…, fallback=True)).
This module opens your installed Chrome with a dedicated profile, signs in once by hand
(`python -m aicl.webchat login gemini`), and then types each turn into the page and reads the
reply back, exactly as was done by hand in examples 18-22.

Read this before relying on it:
- Automating a consumer chat site may break that site's terms of use; your account is at risk.
- It breaks when the site changes its page; it stops at any robot check, which it never solves.
- The profile folder (out/web-profile) holds your sign-in cookies: keep it private, never commit it.
Optional dependency: pip install playwright (it drives the installed Chrome; no browser download).
"""
from __future__ import annotations

import atexit
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "out" / "web-profile"


class NeedsSignIn(RuntimeError):
    """The chat page shows no input box: the profile is not signed in (run `python -m aicl.webchat login <site>`)."""


@dataclass
class Site:
    url: str
    put: str        # JS (text) -> puts text into the composer; returns its length
    send: str       # JS () -> clicks send; returns true when a send button was found
    count: str      # JS () -> number of replies on the page
    last: str       # JS () -> text of the newest reply


_PASTE = """(text) => { const c = document.querySelector('[contenteditable=true]'); if (!c) return -1; c.focus();
  const dt = new DataTransfer(); dt.setData('text/plain', text);
  c.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
  return c.innerText.length; }"""
_CLICK_SEND = """() => { const b = [...document.querySelectorAll('button')].find(b =>
  /送信|Send/i.test(b.getAttribute('aria-label') || '') && b.offsetParent !== null && !b.disabled);
  if (b) { b.click(); return true; } return false; }"""

SITES = {
    "gemini": Site(
        url="https://gemini.google.com/app",
        put="""(text) => { const c = document.querySelector('.ql-editor[contenteditable=true]'); if (!c) return -1;
          const q = c.parentElement.__quill; if (!q) return -1; q.setText(text); c.focus();
          q.setSelection(q.getLength() - 1, 0); document.execCommand('insertText', false, ' ');
          return q.getLength(); }""",
        send=_CLICK_SEND,
        count="() => document.querySelectorAll('model-response').length",
        last="""() => { const e = [...document.querySelectorAll('model-response')].pop(); if (!e) return '';
          return ((e.querySelector('.model-response-text') || e).innerText || '').trim(); }"""),
    "meta": Site(
        url="https://www.meta.ai/",
        put=_PASTE,
        send=_CLICK_SEND,
        count="() => document.querySelectorAll('main [dir=auto]').length",
        last="""() => { const t = (document.querySelector('main') || document.body).innerText;
          const i = t.lastIndexOf(window.__aiclMarker || '\\u0000'); if (i < 0) return '';
          let a = t.slice(i + window.__aiclMarker.length); const j = a.search(/Meta AIに聞く|Ask Meta AI/);
          if (j >= 0) a = a.slice(0, j); return a.replace(/思考を表示|Show thinking|今日|Today/g, '').trim(); }"""),
}

_browser = {"pw": None, "ctx": None}


def _context(headless: bool = False):
    """One persistent Chrome context for every chat window in this process."""
    if _browser["ctx"] is None:
        from playwright.sync_api import sync_playwright
        PROFILE.mkdir(parents=True, exist_ok=True)
        pw = sync_playwright().start()
        ctx = pw.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=headless,
                                                    viewport={"width": 1200, "height": 900})
        _browser.update(pw=pw, ctx=ctx)
        atexit.register(close)
    return _browser["ctx"]


def close() -> None:
    if _browser["ctx"] is not None:
        try:
            _browser["ctx"].close()
            _browser["pw"].stop()
        except Exception:
            pass
        _browser.update(pw=None, ctx=None)


def _transcript(system: str, history: List[dict]) -> str:
    """The first message of a fresh chat: the role, any turns that happened before the switch, the new turn."""
    parts = [system]
    if len(history) > 1:
        parts.append("Conversation so far (you are the assistant; continue it):")
        parts += [f"[{h['role']}]\n{h['content']}" for h in history[:-1]]
    parts.append(history[-1]["content"] if history else "")
    return "\n\n".join(parts)


def text_ask(site: str = "gemini", timeout: float = 150.0, settle: float = 3.0,
             headless: bool = False) -> Callable[[str, List[dict]], str]:
    """ask(system, history) -> str over a chat website: one fresh chat per ask function."""
    s = SITES[site]
    state = {"page": None, "sent": 0}

    def ask(system: str, history: List[dict]) -> str:
        if state["page"] is None:
            page = _context(headless).new_page()
            page.goto(s.url, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            state["page"] = page
            text = _transcript(system, history)
        else:
            new = [h["content"] for h in history[state["sent"]:] if h["role"] == "user"]
            text = "\n\n".join(new) if new else (history[-1]["content"] if history else "")
        page = state["page"]
        before = page.evaluate(s.count)
        lines = [l for l in text.splitlines() if l.strip()] or [text]
        page.evaluate("(m) => { window.__aiclMarker = m; }", lines[-1].strip()[-60:])
        if page.evaluate(s.put, text) < 0:
            raise NeedsSignIn(f"{site}: no input box on {s.url}; sign in once with: python -m aicl.webchat login {site}")
        page.wait_for_timeout(600)
        if not page.evaluate(s.send):
            raise NeedsSignIn(f"{site}: no send button; the page may need a sign-in or a robot check")
        state["sent"] = len(history)
        t0, last, stable = time.monotonic(), "", time.monotonic()
        while time.monotonic() - t0 < timeout:
            page.wait_for_timeout(1500)
            if site == "gemini" and page.evaluate(s.count) <= before:
                continue
            txt = page.evaluate(s.last)
            if txt and txt == last:
                if time.monotonic() - stable >= settle:
                    return txt
            else:
                last, stable = txt, time.monotonic()
        if last:
            return last
        raise TimeoutError(f"{site}: no reply within {timeout:.0f}s")

    return ask


def login(site: str) -> None:
    """Open the chat site in the automation profile so you can sign in by hand, once."""
    ctx = _context(headless=False)
    page = ctx.new_page()
    page.goto(SITES[site].url)
    print(f"Sign in to {SITES[site].url} in the Chrome window that opened, then press Enter here.")
    try:
        input()
    finally:
        close()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "login" and sys.argv[2] in SITES:
        login(sys.argv[2])
    else:
        print("usage: python -m aicl.webchat login gemini|meta")
