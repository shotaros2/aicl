"""Command-line interface: koine fmt|pretty|json|cbor|check|hash|stats FILE"""
from __future__ import annotations

import argparse
import sys

from . import __version__, cbor_codec, json_codec, tokens
from .model import KoineError, Message, is_message
from .parser import parse
from .printer import digest, pretty, to_text
from .validate import nl_ratio, validate_conversation, validate_message


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def _load(path: str):
    if path.endswith(".json"):
        import json
        data = json.loads(_read(path))
        objs = data if isinstance(data, list) and data and isinstance(data[0], dict) and "f" in data[0] else [data]
        return [json_codec.from_json(o) for o in objs]
    if path.endswith(".cbor"):
        with open(path, "rb") as f:
            return [cbor_codec.from_cbor(f.read())]
    return parse(_read(path))


def cmd_fmt(a):
    for t in _load(a.file):
        print(to_text(t))


def cmd_pretty(a):
    for t in _load(a.file):
        print(pretty(t, width=a.width))


def cmd_json(a):
    import json
    terms = _load(a.file)
    objs = [json_codec.to_json(t) for t in terms]
    out = objs[0] if len(objs) == 1 else objs
    print(json.dumps(out, sort_keys=True, ensure_ascii=False,
                     indent=None if a.compact else 2, separators=(",", ":") if a.compact else None))


def cmd_cbor(a):
    terms = _load(a.file)
    if len(terms) != 1:
        sys.exit("cbor: input must contain exactly one term")
    data = cbor_codec.to_cbor(terms[0])
    if a.output:
        with open(a.output, "wb") as f:
            f.write(data)
        print(f"{len(data)} bytes -> {a.output}")
    else:
        print(data.hex())


def cmd_hash(a):
    for t in _load(a.file):
        print(digest(t))


def cmd_check(a):
    terms = _load(a.file)
    issues = []
    msgs = []
    for t in terms:
        if is_message(t):
            issues.extend(validate_message(t))
            try:
                msgs.append(Message.from_form(t))
            except KoineError:
                pass
        else:
            issues.append(("error", f"top-level term is not a message: {to_text(t)[:60]}"))
    if msgs:
        issues.extend(validate_conversation(msgs, a.known))
    errors = 0
    seen = set()
    for i in issues:
        s = str(i) if not isinstance(i, tuple) else f"{i[0]} {i[1]}"
        if s in seen:
            continue
        seen.add(s)
        print(s)
        errors += s.startswith("error")
    print(f"{len(msgs)} messages, {errors} errors, {len(seen) - errors} warnings")
    sys.exit(1 if errors else 0)


def cmd_stats(a):
    text = _read(a.file)
    terms = _load(a.file)
    msgs = [Message.from_form(t) for t in terms if is_message(t)]
    canon = "\n".join(to_text(t) for t in terms)
    print(f"messages:          {len(msgs)}")
    print(f"chars (source):    {len(text)}")
    print(f"chars (canonical): {len(canon)}")
    print(f"tokens (canonical, {tokens.METHOD}): {tokens.count(canon)}")
    print(f"nl ratio:          {nl_ratio(msgs):.1%}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="koine", description="Koine agent language tools")
    p.add_argument("--version", action="version", version=f"koine {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("fmt", help="print canonical single-line form");          s.add_argument("file"); s.set_defaults(fn=cmd_fmt)
    s = sub.add_parser("pretty", help="print human-readable multi-line form");    s.add_argument("file"); s.add_argument("--width", type=int, default=72); s.set_defaults(fn=cmd_pretty)
    s = sub.add_parser("json", help="convert to JSON encoding");                  s.add_argument("file"); s.add_argument("--compact", action="store_true"); s.set_defaults(fn=cmd_json)
    s = sub.add_parser("cbor", help="convert a single term to CBOR");             s.add_argument("file"); s.add_argument("-o", "--output"); s.set_defaults(fn=cmd_cbor)
    s = sub.add_parser("hash", help="SHA-256 of canonical form, one per term");   s.add_argument("file"); s.set_defaults(fn=cmd_hash)
    s = sub.add_parser("check", help="validate a conversation");                  s.add_argument("file"); s.add_argument("--known", action="append", default=[], metavar="TERM", help="pre-agreed domain term (repeatable)"); s.set_defaults(fn=cmd_check)
    s = sub.add_parser("stats", help="size, token estimate and nl ratio");        s.add_argument("file"); s.set_defaults(fn=cmd_stats)

    a = p.parse_args(argv)
    try:
        a.fn(a)
    except KoineError as e:
        sys.exit(f"koine: {e}")


if __name__ == "__main__":
    main()
