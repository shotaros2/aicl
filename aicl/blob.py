"""Binary attachments by content hash (SPEC §5.2).

A blob names its content: `(blob sha256:<64 hex> :media "image/png" :bytes 48213
:uri "https://…")`. The hash is the identity; `:uri` is only a hint about where a
copy may currently be fetched (it may expire or lie), and a receiver MUST verify
the hash of whatever it fetched before trusting it. Pure stdlib.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path
from typing import Optional

from .model import Form, Str, Symbol

HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def make_blob(path: str | Path, uri: Optional[str] = None, media: Optional[str] = None) -> Form:
    """The blob form naming a local file's content."""
    p = Path(path)
    f = Form("blob", [Symbol(file_hash(p))])
    f.kw["media"] = Str(media or mimetypes.guess_type(p.name)[0] or "application/octet-stream")
    f.kw["bytes"] = p.stat().st_size
    if uri:
        f.kw["uri"] = Str(uri)
    return f


def blob_hash(form: Form) -> Optional[str]:
    """The sha256:<hex> of a well-shaped blob form, else None."""
    if (isinstance(form, Form) and form.head == "blob" and len(form.args) == 1
            and isinstance(form.args[0], Symbol) and HASH_RE.match(form.args[0].name)):
        return form.args[0].name
    return None


def verify_blob(path: str | Path, form: Form) -> bool:
    """True iff the local file's content is what the blob form names."""
    want = blob_hash(form)
    return want is not None and file_hash(Path(path)) == want
