"""A signed agreement with a model that has no API: the browser window is the transport.

Same scenario as contract_dialogue.py (@a wants a 45-minute meeting, @b is busy part of the
morning), but @b is a chat window - meta.ai, a Gemini Gem, any consumer product - and a
human or an agent with a browser relays the messages one turn at a time. This script is
the harness split into steps so it can wait between turns:

  python examples/browser_relay.py init [--a claude] [--b muse]
      generates keys, runs @a's first turn, and writes out/browser_relay/first_message.txt:
      the dense rulebook for @b, its private goal, the clock line and @a's first message.
      Paste that as the first chat message.
  python examples/browser_relay.py step --file reply.txt      (or:  step < reply.txt)
      feeds @b's reply in, signs it with @b's transport key, runs @a's next turn and prints
      the next message to paste (with a fresh `; now` line). Repeat until it says done.
  python examples/browser_relay.py finish
      validates the whole conversation, saves out/browser_relay/transcript.aicl and keys.json,
      and extracts and verifies the agreement, with the tamper and re-encoding checks.

Identity comes from the transport (SPEC §3.1): the relay signs each party's messages with
that party's key, so the model never sees a private key and cannot forge the other side.
The clock is the relay's real wall clock, rounded to the minute.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

import aicl
from aicl import vendors
from aicl.agreement import describe, extract_agreements
from aicl.dense import expand as dense_expand
from aicl.dialogue import AiclAgent
from aicl.env import load_dotenv
from aicl.model import AICLError, Message, ModelError
from aicl.parser import parse
from aicl.printer import to_text
from aicl.signing import generate_key, sign_form
from aicl.validate import validate_conversation, validate_message
from contract_dialogue import AICL_PROMPT, GOAL_A, GOAL_B, KNOWN

load_dotenv()
DIR = ROOT / "out" / "browser_relay"
STATE = DIR / "state.json"
JST = timezone(timedelta(hours=9))
DENSE_RULEBOOK = (ROOT / "rulebook" / "aicl-rulebook-dense.md").read_text(encoding="utf-8").split("---", 1)[1].strip()


def now_line() -> str:
    return "; now " + datetime.now(JST).strftime("%Y-%m-%dT%H:%M+09:00")


def load() -> dict:
    if not STATE.exists():
        sys.exit("no state: run `init` first")
    return json.loads(STATE.read_text(encoding="utf-8"))


def save(st: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")


def accept(raw: str, speaker: str, st: dict) -> Message:
    """Parse one message from `speaker` (dense or readable), sign it as the transport, log it."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("lisp").removeprefix("aicl").strip()
    terms = parse(dense_expand(raw))
    if len(terms) != 1:
        raise ModelError(f"{len(terms)} terms in one turn")
    m = Message.from_form(terms[0])
    if m.sender != speaker:
        raise ModelError(f"sender is @{m.sender}, expected @{speaker}")
    if "sig" in m.to_form().kw:
        st["notes"].append(f"@{speaker} sent its own :sig on #{m.id}; replaced by the transport's")
    m = Message.from_form(sign_form(m.to_form(), st["priv"][speaker]))
    canon = to_text(m.to_form())
    st["messages"].append(canon)
    st["wire"].append(raw)
    print(f"@{speaker}: {canon}")
    for i in validate_message(m.to_form()):
        print(f"    {i}")
    return m


def a_turn(st: dict, incoming: str) -> Message:
    ag = AiclAgent("a", vendors.text_ask(st["a_vendor"]), AICL_PROMPT.replace("@me", "@a") + "\n\n" + GOAL_A)
    ag.history = st["a_history"]
    for attempt in range(2):
        raw = ag.turn(incoming)
        st["a_history"] = ag.history
        try:
            return accept(raw, "a", st)
        except AICLError as e:
            st["notes"].append(f"@a invalid (attempt {attempt + 1}): {e} | {raw[:200]}")
            incoming = f"; harness: your message was not valid AICL ({e}); resend one valid AICL message"
    sys.exit("@a failed twice; aborted")


def to_send(m: Message) -> str:
    return now_line() + "\n" + aicl.to_dense(m.to_form())


def cmd_init(args) -> int:
    priv_a, pub_a = generate_key()
    priv_b, pub_b = generate_key()
    st = {"a_vendor": args.a, "b_name": args.b, "pub": {"a": pub_a, "b": pub_b},
          "priv": {"a": priv_a, "b": priv_b}, "a_history": [], "messages": [], "wire": [], "notes": [],
          "started": now_line()[6:]}
    m = a_turn(st, now_line() + "\n; conversation start: send your first AICL message")
    first = (re.sub(r"\bme\b", "b", DENSE_RULEBOOK)
             + "\n\n" + GOAL_B
             + "\n\nThe other agent is `a`. From now on every message you receive is AICL from @a, "
               "possibly preceded by the transport's `; now` clock line. Reply with exactly one AICL "
               "message, nothing else.\n\n" + to_send(m))
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "first_message.txt").write_text(first, encoding="utf-8", newline="\n")
    save(st)
    print(f"\n=== paste {DIR / 'first_message.txt'} as the first chat message of @{args.b} ===")
    print(f"(it ends with)\n{to_send(m)}")
    return 0


def cmd_step(args) -> int:
    st = load()
    raw = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    try:
        mb = accept(raw, "b", st)
    except AICLError as e:
        save(st)
        print(f"\n=== @b's message is not valid AICL ({e}); paste this to @b ===")
        print(f"; harness: your message was not valid AICL ({e}); resend one valid AICL message")
        return 1
    if mb.act == "end":
        save(st)
        print("\n=== @b ended the conversation: run `finish` ===")
        return 0
    ma = a_turn(st, now_line() + "\n" + to_text(mb.to_form()))
    save(st)
    if ma.act == "end":
        print(f"\n=== @a ended the conversation; paste this to @b for the record, then run `finish` ===")
    else:
        print(f"\n=== paste this to @{st['b_name']} ===")
    print(to_send(ma))
    return 0


def cmd_finish(args) -> int:
    st = load()
    msgs = [Message.from_form(parse(c)[0]) for c in st["messages"]]
    keys = st["pub"]
    (DIR / "transcript.aicl").write_text("\n".join(st["messages"]) + "\n", encoding="utf-8", newline="\n")
    (DIR / "keys.json").write_text(json.dumps(keys, indent=2), encoding="utf-8")
    print(f"--- {len(msgs)} messages, relay started {st['started']}, @a = {vendors.describe(st['a_vendor'])}, "
          f"@b = {st['b_name']} via browser ---")
    for i in validate_conversation(msgs, KNOWN):
        print(f"  {i}")
    for n in st["notes"]:
        print(f"  note: {n}")
    print(f"\n--- agreements (aicl agreement {DIR / 'transcript.aicl'} --keys {DIR / 'keys.json'}) ---")
    ags = extract_agreements(msgs, keys=keys, known_terms=KNOWN)
    print(describe(ags))
    if not ags or not ags[-1].verified:
        print("no verified agreement")
        return 1
    ag = ags[-1]
    print("\n--- tamper test: move the agreed time by 30 minutes ---")
    text = "\n".join(st["messages"])
    at = ag.terms.kw["at"].text
    hh, mm = int(at[11:13]), int(at[14:16])
    moved = at[:11] + f"{(hh + (mm + 30) // 60) % 24:02d}:{(mm + 30) % 60:02d}" + at[16:]
    print(describe(extract_agreements(aicl.parse_messages(text.replace(at, moved)), keys=keys, known_terms=KNOWN)))
    print("\n--- re-encoding test ---")
    dense = "\n".join(aicl.to_dense(m.to_form()) for m in msgs)
    again = [Message.from_form(t) for t in aicl.from_dense(dense)]
    via_json = [Message.from_form(aicl.from_json_text(aicl.to_json_text(m.to_form()))) for m in msgs]
    print("dense :", extract_agreements(again, keys=keys, known_terms=KNOWN)[-1].verified)
    print("json  :", extract_agreements(via_json, keys=keys, known_terms=KNOWN)[-1].verified)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("--a", default="claude", choices=vendors.VENDORS)
    p.add_argument("--b", default="muse", help="name of the chat-window party (default muse)")
    p = sub.add_parser("step"); p.add_argument("--file", default=None, help="file holding @b's reply (default: stdin)")
    sub.add_parser("finish")
    args = ap.parse_args(argv)
    return {"init": cmd_init, "step": cmd_step, "finish": cmd_finish}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
