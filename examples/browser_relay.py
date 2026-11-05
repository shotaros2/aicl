"""A signed agreement with parties that have no API: the browser window is the transport.

Same scenario as contract_dialogue.py (@a wants a 45-minute meeting, @b is busy part of the
morning), but either party may be a chat window - meta.ai, gemini.google.com, a Gem, any
consumer product - and a human or an agent with a browser relays the messages one turn at
a time. This script is the dialogue harness split into steps so it can wait between turns.

  python examples/browser_relay.py init --a claude --b muse
  python examples/browser_relay.py init --a muse --b gemini-web      # two chat windows, no API at all
      A party named after a vendor (claude, gemini, muse) is driven through its API; any
      other name is a browser party. For each browser party this writes
      out/browser_relay/first_message_<side>.txt: the dense rulebook for that side, its
      private goal, and (once something is to be delivered) the clock line and the message.
      Paste that as the first chat message of that window.
  python examples/browser_relay.py step --from b --file reply.txt   (or:  step < reply.txt)
      feeds a browser party's reply in, signs it with that party's transport key, and either
      runs the other party's API turn or prints what to paste into the other window.
      Repeat until it says to run `finish`.
  python examples/browser_relay.py finish
      validates the whole conversation, saves out/browser_relay/transcript.aicl and keys.json,
      and extracts and verifies the agreement, with the tamper and re-encoding checks.

Identity comes from the transport (SPEC §3.1): the relay signs each party's messages with
that party's key, so no model ever sees a private key or can forge the other side. The
clock is the relay's real wall clock, rounded to the minute.
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
GOALS = {"a": GOAL_A, "b": GOAL_B}
OTHER = {"a": "b", "b": "a"}


def now_line() -> str:
    return "; now " + datetime.now(JST).strftime("%Y-%m-%dT%H:%M+09:00")


def load() -> dict:
    if not STATE.exists():
        sys.exit("no state: run `init` first")
    return json.loads(STATE.read_text(encoding="utf-8"))


def save(st: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")


def is_api(st: dict, side: str) -> bool:
    return st["party"][side] in vendors.VENDORS


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


def api_turn(st: dict, side: str, incoming: str) -> Message:
    ag = AiclAgent(side, vendors.text_ask(st["party"][side]), AICL_PROMPT.replace("@me", f"@{side}") + "\n\n" + GOALS[side])
    ag.history = st["history"][side]
    for attempt in range(2):
        raw = ag.turn(incoming)
        st["history"][side] = ag.history
        try:
            return accept(raw, side, st)
        except AICLError as e:
            st["notes"].append(f"@{side} invalid (attempt {attempt + 1}): {e} | {raw[:200]}")
            incoming = f"; harness: your message was not valid AICL ({e}); resend one valid AICL message"
    sys.exit(f"@{side} failed twice; aborted")


def to_send(m: Message) -> str:
    return now_line() + "\n" + aicl.to_dense(m.to_form())


def briefing(side: str) -> str:
    other = OTHER[side]
    return (re.sub(r"\bme\b", side, DENSE_RULEBOOK) + "\n\n" + GOALS[side]
            + f"\n\nThe other agent is `{other}`. From now on every message you receive is AICL from @{other}, "
              "possibly preceded by the transport's `; now` clock line. Reply with exactly one AICL "
              "message, nothing else.")


def deliver(st: dict, side: str, m: Message | None) -> None:
    """Hand `m` (or, with None, the opening) to a browser party: the first time inside its briefing."""
    body = to_send(m) if m is not None else now_line() + "\n; conversation start: send your first AICL message"
    if not st["briefed"][side]:
        path = DIR / f"first_message_{side}.txt"
        path.write_text(briefing(side) + "\n\n" + body, encoding="utf-8", newline="\n")
        st["briefed"][side] = True
        print(f"\n=== paste {path} as the first chat message of @{side} ({st['party'][side]}) ===")
        print(f"(it ends with)\n{body}")
    else:
        print(f"\n=== paste this to @{side} ({st['party'][side]}) ===")
        print(body)


def advance(st: dict, speaker: str, m: Message) -> bool:
    """After `m` from `speaker` was logged, move the conversation on. True when finished."""
    other = OTHER[speaker]
    if m.act == "end":
        if not is_api(st, other):
            deliver(st, other, m)
        print("\n=== the conversation is closed: run `finish` ===")
        return True
    if is_api(st, other):
        reply = api_turn(st, other, now_line() + "\n" + to_text(m.to_form()))
        return advance(st, other, reply)
    deliver(st, other, m)
    return False


def cmd_init(args) -> int:
    priv_a, pub_a = generate_key()
    priv_b, pub_b = generate_key()
    st = {"party": {"a": args.a, "b": args.b}, "pub": {"a": pub_a, "b": pub_b},
          "priv": {"a": priv_a, "b": priv_b}, "history": {"a": [], "b": []}, "briefed": {"a": False, "b": False},
          "messages": [], "wire": [], "notes": [], "started": now_line()[6:]}
    DIR.mkdir(parents=True, exist_ok=True)
    for stale in DIR.glob("first_message*.txt"):
        stale.unlink()
    if is_api(st, "a"):
        m = api_turn(st, "a", now_line() + "\n; conversation start: send your first AICL message")
        advance(st, "a", m)
    else:
        deliver(st, "a", None)
    save(st)
    return 0


def cmd_step(args) -> int:
    st = load()
    side = args.from_side
    if is_api(st, side):
        sys.exit(f"@{side} is driven through the API; `step` takes a browser party's reply")
    raw = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    try:
        m = accept(raw, side, st)
    except AICLError as e:
        save(st)
        print(f"\n=== @{side}'s message is not valid AICL ({e}); paste this to @{side} ===")
        print(f"; harness: your message was not valid AICL ({e}); resend one valid AICL message")
        return 1
    advance(st, side, m)
    save(st)
    return 0


def cmd_finish(args) -> int:
    st = load()
    msgs = [Message.from_form(parse(c)[0]) for c in st["messages"]]
    keys = st["pub"]
    (DIR / "transcript.aicl").write_text("\n".join(st["messages"]) + "\n", encoding="utf-8", newline="\n")
    (DIR / "keys.json").write_text(json.dumps(keys, indent=2), encoding="utf-8")
    who = ", ".join(f"@{s} = {vendors.describe(p) if p in vendors.VENDORS else p + ' via browser'}"
                    for s, p in st["party"].items())
    print(f"--- {len(msgs)} messages, relay started {st['started']}, {who} ---")
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
    p = sub.add_parser("init")
    p.add_argument("--a", default="claude", help="party speaking as @a: claude/gemini/muse (API) or a browser name")
    p.add_argument("--b", default="muse", help="party speaking as @b: claude/gemini/muse (API) or a browser name")
    p = sub.add_parser("step")
    p.add_argument("--from", dest="from_side", default="b", choices=("a", "b"), help="which browser party replied")
    p.add_argument("--file", default=None, help="file holding the reply (default: stdin)")
    sub.add_parser("finish")
    args = ap.parse_args(argv)
    return {"init": cmd_init, "step": cmd_step, "finish": cmd_finish}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
