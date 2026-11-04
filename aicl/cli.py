"""Command-line interface: aicl fmt|pretty|json|cbor|check|hash|stats FILE"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, cbor_codec, dense, json_codec, tokens
from .model import AICLError, Message, is_message
from .parser import parse
from .printer import digest, pretty, to_text
from .validate import nl_ratio, parse_now, validate_conversation, validate_message


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def _codebook(a):
    from .codebook import Codebook
    return Codebook.load(a.codebook) if getattr(a, "codebook", None) else None


def _load(path: str, codebook=None):
    if codebook is not None and not path.endswith((".json", ".cbor")):
        return codebook.unpack(_read(path))
    if path.endswith(".json"):
        import json
        data = json.loads(_read(path))
        objs = data if isinstance(data, list) and data and isinstance(data[0], dict) and "f" in data[0] else [data]
        return [json_codec.from_json(o) for o in objs]
    if path.endswith(".cbor"):
        with open(path, "rb") as f:
            return [cbor_codec.from_cbor(f.read())]
    text = _read(path)
    if path.endswith(".kd") or dense.looks_dense(text):
        return dense.from_dense(text)
    return parse(text)


def cmd_dense(a):
    for t in _load(a.file):
        print(dense.to_dense(t))


def cmd_pack(a):
    cb = _codebook(a)
    counter = tokens.get_counter(a.tokenizer)
    for t in _load(a.file, cb):
        print(cb.pack_text(t, counter, dense=not a.readable))


def cmd_unpack(a):
    cb = _codebook(a)
    text = _read(a.file)
    for t in cb.unpack(text):
        print(to_text(t))
    bad = cb.unresolved_forms(text)
    if bad:
        sys.exit("unpack: forms not in codebook (rule 3): " + ", ".join(sorted(set(bad))))


def cmd_codebook(a):
    cb = _codebook(a)
    counter = tokens.get_counter(a.tokenizer)
    best = cb.choose(counter)
    print(f"codebook: {cb.name or a.codebook}")
    if cb.published_id:
        print(f"published id: {cb.published_id} (standard, immutable; SPEC §8.2)")
    print(f"digest:   {cb.id}")
    print(f"concepts: {len(cb.concepts)}, forms: {len(cb.form_to_concept)}")
    for w in cb.warnings:
        print(f"warning:  {w}")
    print(f"cheapest form per concept for tokenizer {a.tokenizer or tokens.METHOD}:")
    for cid, f in sorted(best.items()):
        mark = "" if f == cid else f"  -> {f}  ({counter(' ' + cid)} -> {counter(' ' + f)} tokens)"
        print(f"  {cid}{mark}")


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


def cmd_blob(a):
    from .blob import file_hash, make_blob
    if a.expect:
        got = file_hash(a.file)
        print(f"{'ok' if got == a.expect else 'MISMATCH'}: {got}")
        sys.exit(0 if got == a.expect else 1)
    print(to_text(make_blob(a.file, uri=a.uri, media=a.media)))


def cmd_keygen(a):
    from .signing import generate_key
    priv, pub = generate_key()
    print(f'private: {priv}')
    print(f'public:  {pub}')
    print(f'keys-file entry: {{"{a.agent}": "{pub}"}}   (keep the private key out of the repository)')


def cmd_sign(a):
    from .signing import sign_form
    priv = Path(a.key).read_text(encoding="utf-8").strip() if Path(a.key).exists() else a.key
    out = []
    for t in _load(a.file):
        if is_message(t):
            m = Message.from_form(t)
            if a.agent in (None, m.sender):
                t = sign_form(m.to_form(), priv)
        out.append(to_text(t))
    text = "\n".join(out)
    if a.output:
        Path(a.output).write_text(text + "\n", encoding="utf-8")
        print(f"{len(out)} terms -> {a.output}")
    else:
        print(text)


def cmd_check(a):
    cb = _codebook(a)
    terms = _load(a.file, cb)
    if cb is not None:
        a.known = list(a.known) + list(cb.concepts)
    issues = []
    msgs = []
    for t in terms:
        if is_message(t):
            issues.extend(validate_message(t))
            try:
                msgs.append(Message.from_form(t))
            except AICLError:
                pass
        else:
            issues.append(("error", f"top-level term is not a message: {to_text(t)[:60]}"))
    if msgs:
        now = parse_now(a.now) if getattr(a, "now", None) else None
        keys = None
        if getattr(a, "keys", None):
            from .signing import load_keys
            keys = load_keys(a.keys)
        issues.extend(validate_conversation(msgs, a.known, now=now, keys=keys))
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
    cb = _codebook(a)
    text = _read(a.file)
    terms = _load(a.file, cb)
    msgs = [Message.from_form(t) for t in terms if is_message(t)]
    canon = "\n".join(to_text(t) for t in terms)
    dn = "\n".join(dense.to_dense(t) for t in terms)
    print(f"messages:          {len(msgs)}")
    print(f"chars (source):    {len(text)}")
    print(f"chars (canonical): {len(canon)}")
    print(f"chars (dense):     {len(dn)}")
    print(f"tokens (canonical, {tokens.METHOD}): {tokens.count(canon)}")
    print(f"tokens (dense, {tokens.METHOD}):     {tokens.count(dn)}")
    if cb is not None:
        pk = "\n".join(cb.pack_text(t) for t in terms)
        print(f"tokens (packed, {tokens.METHOD}):    {tokens.count(pk)}")
    print(f"nl ratio:          {nl_ratio(msgs):.1%}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="aicl", description="AICL agent language tools")
    p.add_argument("--version", action="version", version=f"aicl {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("fmt", help="print canonical single-line form");          s.add_argument("file"); s.set_defaults(fn=cmd_fmt)
    s = sub.add_parser("pretty", help="print human-readable multi-line form");    s.add_argument("file"); s.add_argument("--width", type=int, default=72); s.set_defaults(fn=cmd_pretty)
    s = sub.add_parser("dense", help="print dense (tokenizer-tuned) text encoding"); s.add_argument("file"); s.set_defaults(fn=cmd_dense)
    s = sub.add_parser("json", help="convert to JSON encoding");                  s.add_argument("file"); s.add_argument("--compact", action="store_true"); s.set_defaults(fn=cmd_json)
    s = sub.add_parser("cbor", help="convert a single term to CBOR");             s.add_argument("file"); s.add_argument("-o", "--output"); s.set_defaults(fn=cmd_cbor)
    s = sub.add_parser("hash", help="SHA-256 of canonical form, one per term");   s.add_argument("file"); s.set_defaults(fn=cmd_hash)
    s = sub.add_parser("check", help="validate a conversation");                  s.add_argument("file"); s.add_argument("--known", action="append", default=[], metavar="TERM", help="pre-agreed domain term (repeatable)"); s.add_argument("--codebook", metavar="JSON"); s.add_argument("--now", metavar="INSTANT", help="current time (ISO instant with offset); makes :by and :at+:eta deadlines checkable"); s.add_argument("--keys", metavar="JSON", help="agent -> base64url Ed25519 public key; makes identity checkable (:sig, SPEC §3.1)"); s.set_defaults(fn=cmd_check)
    s = sub.add_parser("stats", help="size, token estimate and nl ratio");        s.add_argument("file"); s.add_argument("--codebook", metavar="JSON"); s.set_defaults(fn=cmd_stats)
    s = sub.add_parser("pack", help="replace concept ids by the cheapest codebook forms"); s.add_argument("file"); s.add_argument("--codebook", required=True, metavar="JSON"); s.add_argument("--tokenizer", help="auto | chars | heuristic | cl100k_base | o200k_base | tiktoken:<name>"); s.add_argument("--readable", action="store_true", help="emit readable instead of dense text"); s.set_defaults(fn=cmd_pack)
    s = sub.add_parser("unpack", help="map codebook forms back to concept ids (canonical text)"); s.add_argument("file"); s.add_argument("--codebook", required=True, metavar="JSON"); s.set_defaults(fn=cmd_unpack)
    s = sub.add_parser("codebook", help="validate a codebook and show the chosen forms"); s.add_argument("codebook", metavar="JSON"); s.add_argument("--tokenizer"); s.set_defaults(fn=cmd_codebook)
    s = sub.add_parser("keygen", help="generate an Ed25519 keypair for an agent (SPEC §3.1)"); s.add_argument("agent"); s.set_defaults(fn=cmd_keygen)
    s = sub.add_parser("blob", help="print the (blob sha256:… …) form naming a file's content, or verify one (SPEC §5.2)"); s.add_argument("file"); s.add_argument("--uri", help="where a copy can currently be fetched (a hint, not an identity)"); s.add_argument("--media"); s.add_argument("--expect", metavar="HASH", help="verify: compare the file against sha256:<hex>"); s.set_defaults(fn=cmd_blob)
    s = sub.add_parser("sign", help="add :sig to each message (the whole file, or one sender's)"); s.add_argument("file"); s.add_argument("--key", required=True, metavar="PRIV", help="base64url Ed25519 private key, or a file holding it"); s.add_argument("--agent", help="sign only this sender's messages"); s.add_argument("-o", "--output"); s.set_defaults(fn=cmd_sign)

    a = p.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):   # codebook forms may be non-ASCII; never depend on the console code page
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        a.fn(a)
    except (AICLError, ValueError) as e:
        sys.exit(f"aicl: {e}")


if __name__ == "__main__":
    main()
