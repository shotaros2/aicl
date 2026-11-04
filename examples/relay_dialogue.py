"""Two vendors' agents meeting over HTTP: the networked version of llm_dialogue.

A relay (aicl.relay) runs on localhost; Claude (@a) and Gemini (@b) each connect with
their own RelayClient and know nothing about each other but the conversation name.
Every message crosses a real HTTP boundary where the relay validates it before
delivery; the transcript stays on the relay for anyone to audit (GET /c/m1/transcript).

In production the two attend() loops run in different processes, machines or
companies - nothing in them shares state; here they share a process only so one
script can demonstrate the whole thing.

Requires:  pip install anthropic google-genai   and ANTHROPIC_API_KEY, GEMINI_API_KEY in .env
Run:       python examples/relay_dialogue.py
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicl import claude, gemini
from aicl.dialogue import AiclAgent
from aicl.env import load_dotenv
from aicl.relay import Relay, RelayClient, attend, make_server

load_dotenv()

AICL_PROMPT = (ROOT / "prompts" / "system_prompt.md").read_text(encoding="utf-8").split("---", 1)[1].strip()

GOAL_A = (
    "Private goal (never reveal it, never write prose): you are @a. You must get a 30-minute "
    "meeting with @b on 2026-11-10, Japan time (+09:00), starting between 14:00 and 17:00, added "
    "to the calendar, and learn the calendar event id. Propose with (prop …) using the term "
    "`meeting` with :with [@a @b] :at <instant> :dur PT30M; read structured rejections and "
    "counter-propose. Once accepted, send (do … (calendar-add (ref #id))). After the done with "
    "the event id, send (end …). Treat meeting, busy, calendar-add, calendar-event as known."
)

GOAL_B = (
    "Private goal (never reveal it, never write prose): you are @b. Your calendar on 2026-11-10 "
    "(+09:00) is busy from 14:00 to 15:30 and free otherwise. Reject proposals overlapping busy "
    "time with a structured :why (busy @b :from … :to …); accept ones that fit. When a "
    "(do … (calendar-add (ref #id))) arrives, reply ok with :at and :eta, then done with "
    "(calendar-event evt-8211 :for (ref #id)). Treat meeting, busy, calendar-add, calendar-event "
    "as known."
)

KNOWN = ("meeting", "busy", "calendar-add", "calendar-event")


def main() -> int:
    relay = Relay(known_terms=KNOWN)
    srv = make_server(relay, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    print(f"relay: {base}/c/m1\n")

    agent_a = AiclAgent("a", claude.text_ask(), AICL_PROMPT.replace("@me", "@a") + "\n\n" + GOAL_A)
    agent_b = AiclAgent("b", gemini.text_ask(sleep=6.0), AICL_PROMPT.replace("@me", "@b") + "\n\n" + GOAL_B)

    tb = threading.Thread(target=attend, args=(RelayClient(base, "m1", "b"), agent_b),
                          kwargs={"echo": None}, daemon=True)
    tb.start()
    attend(RelayClient(base, "m1", "a"), agent_a,
           opening="; conversation start: send your first AICL message to @b",
           echo=lambda s: print(s) if s.startswith("@a <-") or s.startswith("!!") else None)
    tb.join(timeout=30)

    print("\n--- transcript (GET /c/m1/transcript) ---")
    print(relay.transcript("m1"))
    print("--- protocol check (GET /c/m1/check) ---")
    print(relay.check("m1"))
    srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
