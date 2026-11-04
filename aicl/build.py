"""Small helpers for constructing terms programmatically."""
from __future__ import annotations

from typing import Optional

from .model import Form, Quantity, Ref, ReplyRef, Route, Str, Symbol


def form(head: str, *args, conf: Optional[float] = None, kw: Optional[dict] = None) -> Form:
    """(head args… :k v… ~conf)"""
    return Form(head, list(args), dict(kw or {}), conf)


def msg(act: str, mid: str, src: str, dst: str, *body,
        reply: Optional[str] = None, conf: Optional[float] = None,
        kw: Optional[dict] = None) -> Form:
    """(act #mid @src>@dst [^reply] body… :k v… ~conf)"""
    args: list = [Ref(mid), Route(src, dst)]
    if reply is not None:
        args.append(ReplyRef(reply))
    args.extend(body)
    return Form(act, args, dict(kw or {}), conf)


def sym(name: str) -> Symbol:
    return Symbol(name)


def q(value, unit: str) -> Quantity:
    return Quantity(value, unit)


def nl(lang: str, text: str) -> Form:
    """Quarantined natural language: (nl lang "text")"""
    return Form("nl", [Symbol(lang), Str(text)])
