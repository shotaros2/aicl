"""A model inside the real aicl.network, as the night shift runs it: same rules, directory,
readable input for local roles, bounces. Scores what production sees: how many answers the
network had to bounce, model calls, time, validator errors, and the answers themselves.

Complements examples/local_acceptance.py, which tests a model alone: there, a small local
model may misaddress (`@user.1`) because nothing names its counterpart; here the role text
and the directory do, as in the night shift.

Run:  python examples/network_probe.py --model qwen3.5:9b
      python examples/network_probe.py --model qwen3:14b --dense-input   (compare)
      python examples/network_probe.py --vendor claude --model claude-haiku-5-5
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
from aicl.network import Limits, ModelNode, Network, Node

DENSE = (ROOT / "rulebook" / "aicl-rulebook-dense.md").read_text(encoding="utf-8").split("---", 1)[1].strip()
PROBES = ("(shinjuku-crowd-index $x)",                              # unknown term
          "(temp tokyo $t :at 2026-11-05T19:00+09:00 :unit C)",     # no data
          "(status (ref #user.9) $s)")                              # a request that never existed
ROLE = ("You answer questions from @user honestly. You have no data sources: if you do not know "
        "something, say so in AICL.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--vendor", default="local", choices=vendors.VENDORS)
    ap.add_argument("--model", default=None)
    ap.add_argument("--dense-input", action="store_true", help="show incoming messages dense (as cloud roles see them)")
    args = ap.parse_args(argv)
    model = args.model or (local.model_name() if args.vendor == "local" else vendors.default_model(args.vendor))
    ask = (local.text_ask(model=model) if args.vendor == "local"
           else vendors.text_ask(args.vendor, model=model, sleep=4.0 if args.vendor == "gemini" else 0.0))

    owner = Node("user", "the person asking")
    agent = ModelNode("local", ROLE, ask, DENSE, readable_input=not args.dense_input)
    net = Network([owner, agent], Limits(max_messages=10, max_calls_per_agent=8, max_seconds=900),
                  sign=False, echo=None)
    for p in PROBES:
        net.post(owner.msg("ask", "local", aicl.parse_one(p)))
    t0 = time.monotonic()
    res = net.run(wake=[])
    bounces = [n for n in res.notes if "invalid" in n]
    errors = [i for i in res.issues if i.level == "error"]
    answered = {m.reply for m in res.messages if m.sender == "local" and m.reply}
    print(f"--- {vendors.describe(args.vendor, model)}, {'dense' if args.dense_input else 'readable'} input ---")
    print(f"answered {len(answered & {'user.1', 'user.2', 'user.3'})}/3, {len(bounces)} bounces, "
          f"{res.calls['local']} model calls, {time.monotonic() - t0:.0f}s, {len(errors)} validator errors")
    for m in res.messages:
        if m.sender == "local":
            print("  ", aicl.to_text(m.to_form()))
    for n in res.notes:
        print("   note:", n[:180])
    return 0


if __name__ == "__main__":
    sys.exit(main())
