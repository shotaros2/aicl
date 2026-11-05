"""An autonomous AICL network: nobody tells the agents what to do next.

Five agents come online. Two are models that were given a role and nothing else:
  @editor runs a tiny newsroom for visitors to Tokyo;
  @critic is its fact checker.
By default every model role runs on Gemini's free tier, so a run costs nothing; pass
--editor claude (or --critic / --artist) to use Claude's paid API for that role.
Three are specialists with real effects: @weather (live data from open-meteo.com),
@artist (draws an SVG), @desk (publishes a page). The script then just wakes the network.
Whether to publish, about what, whom to ask, what to verify, and when to stop is decided by
the agents, in dense AICL, at machine speed. The network signs every message with its
sender's key, stamps the real clock, validates everything, and stops when the agents fall
quiet or a limit is reached. Afterwards the transcript can be read back, checked and
verified - including the critic's acceptance, which is a signed agreement (SPEC §4.6).

Requires: GEMINI_API_KEY in .env (ANTHROPIC_API_KEY only for roles you move to Claude), cryptography
Run:      python examples/autonomous_network.py                          # all Gemini, free tier
          python examples/autonomous_network.py --editor claude          # the editor on Claude (paid)
          python examples/autonomous_network.py --max-messages 40 --max-calls 8
Stop it:  create the file out/network/STOP
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicl import vendors
from aicl.agreement import describe, extract_agreements
from aicl.env import load_dotenv
from aicl.network import Limits, ModelNode, Network
from aicl.skills import artist_node, desk_node, weather_node

load_dotenv()
OUT = ROOT / "out" / "network"
DENSE = (ROOT / "rulebook" / "aicl-rulebook-dense.md").read_text(encoding="utf-8").split("---", 1)[1].strip()
KNOWN = ("doc", "publish", "draw", "weather-now", "forecast", "weather", "source", "page")

EDITOR_ROLE = (
    "You are the editor of a small newsroom that publishes short pages for people visiting Tokyo. "
    "Whether to publish anything, about what and how, is your own call. You have no data of your own: "
    "work only from what other agents give you. A page goes to @desk only after @critic has accepted it: "
    "propose it to @critic with a prop whose body is the page, (doc :title … :body … :sources […]), and "
    "publish exactly what was accepted. Write page text in Japanese inside (nl ja \"…\").")

CRITIC_ROLE = (
    "You are the newsroom's fact checker. You never write pages. When a page is proposed to you, check "
    "each factual claim against data you obtain yourself from the agents in the directory, never from "
    "memory, and answer with (acc …) if every claim holds, or (rej … :why …) naming the claim that does "
    "not and the evidence. You may ask any agent anything.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--editor", default="gemini", choices=vendors.VENDORS)
    ap.add_argument("--critic", default="gemini", choices=vendors.VENDORS)
    ap.add_argument("--artist", default="gemini", choices=vendors.VENDORS, help="text model that draws the SVG")
    ap.add_argument("--max-messages", type=int, default=60)
    ap.add_argument("--max-calls", type=int, default=10, help="model calls per model agent")
    ap.add_argument("--max-seconds", type=float, default=900)
    args = ap.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    stop = OUT / "STOP"
    if stop.exists():
        stop.unlink()
    pause = lambda v: 0.0 if v == "claude" else 4.0
    nodes = [
        ModelNode("editor", EDITOR_ROLE, vendors.text_ask(args.editor, sleep=pause(args.editor)), DENSE),
        ModelNode("critic", CRITIC_ROLE, vendors.text_ask(args.critic, sleep=pause(args.critic)), DENSE),
        weather_node(),
        artist_node(vendors.text_ask(args.artist, sleep=pause(args.artist)), OUT),
        desk_node(OUT),
    ]
    net = Network(nodes, Limits(args.max_messages, args.max_calls, args.max_seconds, stop), known_terms=KNOWN)
    print(f"--- network online: @editor = {vendors.describe(args.editor)}, @critic = {vendors.describe(args.critic)}; "
          f"no further input from here on ---")
    res = net.run()
    res.save(OUT)

    print("\n--- what the agents decided ---")
    print(res.stats())
    for i in res.issues:
        print(f"  {i}")
    print("\n--- agreements (the critic's acceptance, signed by both) ---")
    print(describe(extract_agreements(res.messages, keys=res.keys, known_terms=KNOWN)))
    pages = sorted(OUT.glob("*.md"), key=lambda p: p.stat().st_mtime)
    print("\npublished:", pages[-1] if pages else "nothing (the agents chose not to, or did not get there)")
    print(f"transcript: {OUT / 'transcript.aicl'}   wire: {OUT / 'wire.aicl'}   keys: {OUT / 'keys.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
