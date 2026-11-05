"""Apps built by the team: a deterministic tester for single-file web apps.

The coder (a model) writes an app as one HTML file - markup, style and script together - attached
as a blob (see ModelNode._attach). Before the desk publishes it, @tester checks it mechanically:

- the file is the one named: its sha256 and size match the blob;
- it is a web page: it parses, and has a <script> or at least a <body>;
- it stays on the device: no external scripts, styles, images, fonts or frames, and no fetch,
  XMLHttpRequest, WebSocket, EventSource, sendBeacon or form posting to another address - so an app
  can neither leak what you type into it nor pull code from somewhere else;
- its JavaScript is syntactically valid, checked with `node --check` (which parses and does not run);
  where Node.js is not installed the report says the syntax was not checked;
- it is not huge (300 KB).

@tester answers a prop whose body is (app :title … :file (blob …)) with acc, or rej with every problem.
It never runs the app and never judges whether the app is good - only whether it is safe to publish.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import unquote, urlparse

from .build import nl
from .model import Form, Message, Str, Symbol
from .network import SkillNode

MAX_BYTES = 300_000
EXTERNAL = re.compile(r"""(?ix)
    \b(?:src|href|action|poster|data)\s*=\s*["']?\s*(?:https?:)?//      # an attribute pointing off the device
  | url\(\s*["']?\s*(?:https?:)?//                                       # a CSS url(...) to another host
  | @import\s+["']?\s*(?:url\()?\s*["']?(?:https?:)?//
""")
NETWORK_JS = re.compile(r"\b(fetch\s*\(|XMLHttpRequest|WebSocket\s*\(|EventSource\s*\(|sendBeacon\s*\(|importScripts\s*\()")


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts: List[Tuple[str, str]] = []      # (type, code)
        self.tags = set()
        self._in = None

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        if tag == "script":
            a = dict(attrs)
            self._in = (a.get("type") or "text/javascript").lower()
            self.scripts.append((self._in, ""))

    def handle_endtag(self, tag):
        if tag == "script":
            self._in = None

    def handle_data(self, data):
        if self._in is not None and self.scripts:
            t, code = self.scripts[-1]
            self.scripts[-1] = (t, code + data)


def blob_file(b: Form) -> Optional[Path]:
    if not (isinstance(b, Form) and b.head == "blob" and isinstance(b.kw.get("uri"), Str)):
        return None
    u = urlparse(b.kw["uri"].text)
    if u.scheme != "file":
        return None
    p = unquote(u.path)
    if len(p) > 2 and p[0] == "/" and p[2] == ":":
        p = p[1:]
    return Path(p)


def blob_ok(b: Form) -> Tuple[Optional[bytes], str]:
    """(bytes, "") when the blob names a local file whose hash and size match; (None, why) otherwise."""
    path = blob_file(b)
    if path is None or not path.is_file():
        return None, "the blob does not name a local file"
    data = path.read_bytes()
    stated = b.args[0].name if b.args and isinstance(b.args[0], Symbol) else ""
    if stated != "sha256:" + hashlib.sha256(data).hexdigest():
        return None, "the file's sha256 does not match the blob"
    size = b.kw.get("bytes")
    if size is not None and str(size) != str(len(data)):
        return None, "the file's size does not match the blob"
    return data, ""


def check_html(html: str, node: Optional[str] = "auto") -> Tuple[List[str], List[str]]:
    """(problems, notes) for one single-file web app."""
    problems, notes = [], []
    if len(html.encode("utf-8")) > MAX_BYTES:
        problems.append(f"larger than {MAX_BYTES // 1000} KB")
    p = _Scripts()
    try:
        p.feed(html)
        p.close()
    except Exception as e:
        problems.append(f"the HTML does not parse: {e}")
        return problems, notes
    if "body" not in p.tags and not p.scripts:
        problems.append("no <body> and no <script>: this is not an app page")
    for m in EXTERNAL.finditer(html):
        problems.append(f"loads something from another address: {m.group(0).strip()[:60]}")
    for m in NETWORK_JS.finditer(html):
        problems.append(f"talks to the network: {m.group(0).strip()}")
    if "viewport" not in html:
        notes.append("no viewport meta tag: it may look tiny on a phone")
    exe = shutil.which("node") if node == "auto" else node
    js = [(t, c) for t, c in p.scripts if c.strip() and ("javascript" in t or "ecmascript" in t or t == "module")]
    if exe and js:
        with tempfile.TemporaryDirectory() as tmp:
            for i, (t, code) in enumerate(js):
                f = Path(tmp) / (f"s{i}.mjs" if t == "module" else f"s{i}.js")
                f.write_text(code, encoding="utf-8")
                try:
                    r = subprocess.run([exe, "--check", str(f)], capture_output=True, text=True, timeout=20)
                except (OSError, subprocess.TimeoutExpired) as e:
                    notes.append(f"syntax not checked: {e}")
                    break
                if r.returncode != 0:
                    err = next((l for l in r.stderr.splitlines() if "Error" in l), r.stderr.strip()[:160])
                    line = re.search(r":(\d+)\n", r.stderr)
                    problems.append(f"JavaScript syntax error in script {i + 1}"
                                    + (f" at line {line.group(1)}" if line else "") + f": {err.strip()[:160]}")
    elif js:
        notes.append("JavaScript syntax not checked (Node.js not installed)")
    return problems, notes


def tester_node(name: str = "tester", node: Optional[str] = "auto") -> SkillNode:
    def handler(n: SkillNode, m: Message) -> List[Form]:
        if m.act != "prop":
            return [n.msg("no", m.sender, reply=m.id, kw={"why": nl("en", "propose an app: (prop (app :title … :file (blob …)))")})] \
                if m.act in ("ask", "do", "def") else []
        app = m.body[0] if m.body and isinstance(m.body[0], Form) else None
        if app is None or app.head != "app" or "file" not in app.kw:
            return [n.msg("rej", m.sender, reply=m.id, kw={"why": nl("en", "expected (app :title … :file (blob …))")})]
        data, why = blob_ok(app.kw["file"])
        if data is None:
            return [n.msg("rej", m.sender, reply=m.id, kw={"why": nl("en", why)})]
        problems, notes = check_html(data.decode("utf-8", "replace"), node)
        if problems:
            return [n.msg("rej", m.sender, reply=m.id, kw={"why": nl("en", "; ".join(problems[:8]))})]
        kw = {"why": nl("en", "; ".join(notes))} if notes else None
        return [n.msg("acc", m.sender, reply=m.id, kw=kw)]

    return SkillNode(name, "app tester (no model): checks a single-file web app before it is published - the file "
                           "matches its blob, it parses, it loads nothing from other addresses and sends nothing "
                           "out, its JavaScript has no syntax errors; answers acc or rej with every problem; it "
                           "does not run the app or judge whether it is good", handler,
                     offers=["(P x.1>tester (app :title (nl ja \"…\") :file (blob sha256:… :uri \"…\")))"])
