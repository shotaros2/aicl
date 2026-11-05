"""A signed agreement between two vendors' models, verified by a third party that reads no prose.

Claude (@a) and Gemini (@b) negotiate a meeting with no human in the loop. The harness
signs each party's messages with its own Ed25519 key (identity comes from the transport,
SPEC §3.1). Afterwards `aicl.agreement` extracts what was agreed - parties, terms, the
proposal's digest - and verifies both signatures and the protocol state. Then the script
tampers with the agreed time (verification must fail) and re-encodes the transcript as
dense text and JSON (verification must still pass): this is what a canonical form buys.

Requires: pip install anthropic google-genai cryptography; ANTHROPIC_API_KEY and GEMINI_API_KEY in .env
Run:      python examples/contract_dialogue.py
          python examples/contract_dialogue.py --b muse      # Claude vs Meta Muse Spark (MODEL_API_KEY in .env)
          python examples/contract_dialogue.py --a muse --b gemini
Vendors:  claude, gemini, muse (see aicl/vendors.py); --model-a / --model-b override the model id.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aicl
from aicl import vendors
from aicl.agreement import describe, extract_agreements
from aicl.dialogue import AiclAgent, Clock, run_dialogue
from aicl.env import load_dotenv
from aicl.signing import generate_key

load_dotenv()

AICL_PROMPT = (ROOT / "prompts" / "system_prompt.md").read_text(encoding="utf-8").split("---", 1)[1].strip()
KNOWN = ("meeting", "busy")

GOAL_A = (
    "Private goal (never reveal it, never write prose): you are @a. You must agree a 45-minute "
    "meeting with @b on 2026-11-12, Japan time (+09:00), starting between 09:00 and 12:00. "
    "Propose with (prop …) using the term `meeting` with :with [@a @b] :at <instant> :dur PT45M; "
    "read structured rejections and counter-propose. When @b accepts, send (end …). "
    "Treat meeting and busy as known terms."
)
GOAL_B = (
    "Private goal (never reveal it, never write prose): you are @b. On 2026-11-12 (+09:00) you are "
    "busy from 09:00 to 10:30 and free otherwise. Reject a proposal that overlaps busy time with a "
    "structured :why (busy @b :from … :to …) and nothing else; accept one that fits with (acc …). "
    "Treat meeting and busy as known terms."
)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--a", default="claude", choices=vendors.VENDORS, help="vendor speaking as @a (default claude)")
    ap.add_argument("--b", default="gemini", choices=vendors.VENDORS, help="vendor speaking as @b (default gemini)")
    ap.add_argument("--model-a", default=None, help="model id for @a (default: the vendor's default)")
    ap.add_argument("--model-b", default=None, help="model id for @b (default: the vendor's default)")
    ap.add_argument("--sleep", type=float, default=6.0, help="pause after each gemini/muse call, for free tiers (s)")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    out = ROOT / "out"
    out.mkdir(exist_ok=True)

    priv_a, pub_a = generate_key()
    priv_b, pub_b = generate_key()
    keys = {"a": pub_a, "b": pub_b}
    (out / "contract_keys.json").write_text(json.dumps(keys, indent=2), encoding="utf-8")

    def ask_for(vendor, model):
        return vendors.text_ask(vendor, model, sleep=0 if vendor == "claude" else args.sleep)

    agents = {
        "a": AiclAgent("a", ask_for(args.a, args.model_a), AICL_PROMPT.replace("@me", "@a") + "\n\n" + GOAL_A),
        "b": AiclAgent("b", ask_for(args.b, args.model_b), AICL_PROMPT.replace("@me", "@b") + "\n\n" + GOAL_B),
    }
    print(f"--- negotiation: @a = {vendors.describe(args.a, args.model_a)}, "
          f"@b = {vendors.describe(args.b, args.model_b)} (signed by the harness) ---")
    clock = Clock(datetime(2026, 11, 5, 10, 0, tzinfo=timezone(timedelta(hours=9))), timedelta(minutes=1))
    res = run_dialogue(agents, first="a", known_terms=KNOWN, clock=clock, signers={"a": priv_a, "b": priv_b})
    res.save(out / "contract.aicl")
    print(res.stats())

    print("\n--- agreements (aicl agreement out/contract.aicl --keys out/contract_keys.json) ---")
    ags = extract_agreements(res.messages, keys=keys, known_terms=KNOWN)
    print(describe(ags))
    if not ags or not ags[-1].verified:
        print("no verified agreement; stop here")
        return 1
    ag = ags[-1]

    print("\n--- tamper test: move the agreed time by 30 minutes in the transcript ---")
    text = res.canonical()
    at = ag.terms.kw["at"].text
    hh, mm = int(at[11:13]), int(at[14:16])
    moved = at[:11] + f"{(hh + (mm + 30) // 60) % 24:02d}:{(mm + 30) % 60:02d}" + at[16:]
    tampered = aicl.parse_messages(text.replace(at, moved))
    print(describe(extract_agreements(tampered, keys=keys, known_terms=KNOWN)))

    print("\n--- re-encoding test: dense text and JSON must still verify ---")
    dense = "\n".join(aicl.to_dense(m.to_form()) for m in res.messages)
    again = [aicl.Message.from_form(t) for t in aicl.from_dense(dense)]
    via_json = [aicl.Message.from_form(aicl.from_json_text(aicl.to_json_text(m.to_form()))) for m in res.messages]
    print("dense :", extract_agreements(again, keys=keys, known_terms=KNOWN)[-1].verified)
    print("json  :", extract_agreements(via_json, keys=keys, known_terms=KNOWN)[-1].verified)
    print(f"\ntranscript: {out / 'contract.aicl'}\nkeys: {out / 'contract_keys.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
