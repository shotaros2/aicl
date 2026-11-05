"""Acceptance test for a model on this PC (Ollama), scored like examples/18 (Muse) and 16 (Gem).

The dense v0.3 rulebook (me -> local) is the system prompt; a scripted user then sends the
same probes the chat-window tests used, one per turn, each preceded by the real clock line:
an ask it has no data for, an undefined term, a typed def, a do with a deadline, a status
query, a why, and end. Every answer is parsed and the whole exchange is validated; the
checklist at the end says which habits the model has.

Run:  python examples/local_acceptance.py                 (AICL_LOCAL_MODEL, default qwen3:8b)
      python examples/local_acceptance.py --model llama3.1:8b
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aicl
from aicl import local, vendors
from aicl.dense import expand as dense_expand
from aicl.dialogue import AiclAgent
from aicl.network import now_line

DENSE = (ROOT / "rulebook" / "aicl-rulebook-dense.md").read_text(encoding="utf-8").split("---", 1)[1].strip()

PROBES = [
    ("no-data",   "(A user.1>local (temp tokyo $t :a 20261105T1900+9 :u C))"),
    ("unknown",   "(A user.2>local (shinjuku-crowd-index $x))"),
    ("typed-def", '(E user.3>local haiku :g (nl en "compose one original haiku about the topic; deliver it in your done '
                  'as (nl en \\"…\\")") :r [(topic symbol)] :v term)'),
    ("deadline",  "(D user.4>local (haiku broccoli) :b 20261106T2359+9)"),
    ("status",    "(A user.5>local (status (ref #user.4) $s))"),
    ("why",       None),                  # filled in: a why on the model's latest tell
    ("end",       "(X user.7>local)"),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--model", default=None, help="Ollama model (default AICL_LOCAL_MODEL or qwen3:8b)")
    ap.add_argument("--bare", action="store_true",
                    help="omit the '; next-id local.N' line the network adds to every input (harsher)")
    ap.add_argument("--dense-input", action="store_true",
                    help="send the probes in dense form; by default they are readable, as the night-shift "
                         "network shows incoming messages to local roles")
    args = ap.parse_args(argv)
    model = args.model or local.model_name()

    import re
    system = re.sub(r"\bme\b", "local", DENSE)
    agent = AiclAgent("local", local.text_ask(model=model), system)
    log, raw_log, notes = [], [], []
    started = time.monotonic()
    print(f"--- acceptance test: {vendors.describe('local', model)} ---")

    for label, probe in PROBES:
        if probe is None:
            tells = [m for m in log if m.sender == "local" and m.act == "tell"]
            if not tells:
                notes.append("why: skipped, the model never sent a tell")
                continue
            probe = f"(W user.6>local ^{tells[-1].id})"
        sent = aicl.Message.from_form(aicl.parse(dense_expand(probe))[0])
        log.append(sent)
        t0 = time.monotonic()
        own = sum(1 for m in log if m.sender == "local")
        hint = "" if args.bare else f"\n; next-id local.{own + 1}"   # as aicl.network.ModelNode does
        shown = probe if args.dense_input else aicl.to_text(sent.to_form())
        raw = agent.turn(now_line() + "\n" + shown + hint)
        took = time.monotonic() - t0
        raw_log.append(f"; {label} ({took:.1f}s)\n{probe}\n{raw}")
        print(f"\n[{label}] {took:.1f}s\n  -> {probe}")
        lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith(";")]
        try:
            for f in aicl.parse(dense_expand("\n".join(lines))) if lines else []:
                m = aicl.Message.from_form(f)
                log.append(m)
                print(f"  <- {aicl.to_text(f)}")
        except aicl.AICLError as e:
            notes.append(f"{label}: not valid AICL ({e}) | {raw[:160]}")
            print(f"  !! not valid AICL: {e}\n     {raw[:200]}")

    issues = aicl.validate_conversation(log, ["temp", "haiku"])
    errors = [i for i in issues if i.level == "error"]
    replies = {m.reply: m for m in log if m.sender == "local" and m.reply}
    acts = lambda rid: [m.act for m in log if m.sender == "local" and m.reply == rid]

    def has(rid, *want):
        return any(a in want for a in acts(rid))

    ok_do = [m for m in log if m.sender == "local" and m.act == "ok" and m.reply == "user.4"]
    checklist = [
        ("no data -> no / clar (does not invent a temperature)", has("user.1", "no", "clar")),
        ("undefined term -> clar (unk …)", has("user.2", "clar")),
        ("typed def -> ok", has("user.3", "ok")),
        ("deadline do -> ok", bool(ok_do)),
        ("  ok carries :at from the clock line", any("at" in m.kw for m in ok_do)),
        ("haiku delivered with done", has("user.4", "done")),
        ("status -> tell (not ok/done)", has("user.5", "tell")),
        ("why -> tell with :src", any(m.act == "tell" and "src" in m.kw for m in log
                                      if m.sender == "local" and m.reply == "user.6")),
        ("every answer was valid AICL", not notes),
    ]
    print(f"\n--- result ({time.monotonic() - started:.0f}s) ---")
    for text, passed in checklist:
        print(f"  [{'x' if passed else ' '}] {text}")
    print(f"  validator: {len(errors)} errors, {len(issues) - len(errors)} warnings")
    for i in issues:
        print(f"    {i}")
    for n in notes:
        print(f"  note: {n}")

    out = ROOT / "out" / f"local_acceptance_{model.replace(':', '_').replace('/', '_')}.aicl"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(aicl.to_text(m.to_form()) for m in log) + "\n", encoding="utf-8")
    out.with_suffix(".raw.txt").write_text("\n\n".join(raw_log) + "\n", encoding="utf-8")
    print(f"\ntranscript: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
