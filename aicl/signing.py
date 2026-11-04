"""Signatures and identity (SPEC §3.1): @agent → Ed25519 public key.

Signing is the transport's job, not the LLM's - like the wall clock, identity comes
from the layer that delivers messages. The payload is the canonical text (SPEC §7) of
the message with the `:sig` key removed, so a signature survives re-encoding (dense,
JSON, CBOR) and any whitespace changes, and breaks on any semantic change.

Optional dependency: `pip install aicl-lang[crypto]` (the cryptography package),
imported lazily. `payload()` and the key-file helpers work without it.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Dict, Optional

from .model import Form, ModelError, Str, Symbol, Term
from .printer import to_text

ALG = "ed25519"


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _ed25519():
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        return ed25519
    except ImportError:
        raise ModelError("signing needs the optional dependency: pip install aicl-lang[crypto]") from None


def payload(form: Form) -> bytes:
    """What is signed: the canonical text of the message without its :sig key."""
    bare = Form(form.head, list(form.args), {k: v for k, v in form.kw.items() if k != "sig"}, form.conf)
    return to_text(bare).encode("utf-8")


def generate_key() -> tuple[str, str]:
    """A new Ed25519 keypair as (private_b64, public_b64), base64url without padding."""
    ed25519 = _ed25519()
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    from cryptography.hazmat.primitives import serialization as ser
    return (_b64e(priv.private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption())),
            _b64e(pub.public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)))


def sign_form(form: Form, private_b64: str) -> Form:
    """A copy of the message with `:sig (ed25519 "<base64url signature>")`."""
    ed25519 = _ed25519()
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(_b64d(private_b64))
    sig = priv.sign(payload(form))
    signed = Form(form.head, list(form.args), {k: v for k, v in form.kw.items() if k != "sig"}, form.conf)
    signed.kw["sig"] = Form(ALG, [Str(_b64e(sig))])
    return signed


def sig_of(form: Form) -> Optional[Form]:
    """The :sig form if present and well-shaped, else None."""
    s = form.kw.get("sig")
    if (isinstance(s, Form) and s.head == ALG and not s.kw and s.conf is None
            and len(s.args) == 1 and isinstance(s.args[0], Str)):
        return s
    return None


def verify_form(form: Form, public_b64: str) -> bool:
    """True iff the message carries a well-shaped :sig valid for this public key."""
    ed25519 = _ed25519()
    s = sig_of(form)
    if s is None:
        return False
    pub = ed25519.Ed25519PublicKey.from_public_bytes(_b64d(public_b64))
    try:
        pub.verify(_b64d(s.args[0].text), payload(form))
        return True
    except Exception:
        return False


# ------------------------------------------------------------------- key files

def load_keys(path: str) -> Dict[str, str]:
    """A keys file: {"agent name": "base64url public key", …} (no @ in the names)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
        raise ModelError("keys file must be a JSON object of agent name -> base64 public key")
    return {k.lstrip("@"): v for k, v in data.items()}
