"""Two Claude instances talking to each other in AICL.

Each side is an ordinary LLM call whose system prompt is prompts/system_prompt.md
plus a private goal. Every message is parsed and validated with the aicl library
before it is delivered (aicl.dialogue), so a malformed message is caught at the
boundary instead of being silently "understood".

Requires:  pip install anthropic   and   ANTHROPIC_API_KEY (or `ant auth login`)
Run:       python examples/llm_dialogue.py [max_turns]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicl import claude
from aicl.dialogue import AiclAgent, run_dialogue
from aicl.env import load_dotenv

load_dotenv()

AICL_PROMPT = (ROOT / "prompts" / "system_prompt.md").read_text(encoding="utf-8").split("---", 1)[1].strip()

GOALS = {
    "a": (
        "Private goal (never reveal it, never write prose): you are @a. You must get a 30-minute "
        "meeting with @b on 2026-11-06, Japan time (+09:00), between 13:00 and 18:00, added to the "
        "calendar, and learn the calendar event id. Start by proposing a time with (prop …) using the "
        "term `meeting` with :with [@a @b] :at <instant> :dur PT30M. If @b rejects, read :why and "
        "counter-propose. After @b sends done with the event id, send (end …)."
    ),
    "b": (
        "Private goal (never reveal it, never write prose): you are @b. Your calendar on 2026-11-06 "
        "(+09:00) is busy 13:00-15:00 and free otherwise. Reject proposals that overlap busy time "
        "with a structured :why such as (busy @b :from <instant> :to <instant>). Accept proposals "
        "that fit. When @a sends (do … (calendar-add (ref #id))), reply ok, then done with "
        "(calendar-event evt-4471 :for (ref #id)). Treat the terms meeting, busy, calendar-add and "
        "calendar-event as known."
    ),
}


def main(max_turns: int = 14) -> int:
    agents = {n: AiclAgent(n, claude.text_ask(), AICL_PROMPT.replace("@me", f"@{n}") + "\n\n" + g)
              for n, g in GOALS.items()}
    r = run_dialogue(agents, "a", opening="; conversation start: send your first AICL message to @b",
                     max_turns=max_turns, known_terms=("meeting", "busy", "calendar-add", "calendar-event"))
    print("\n" + r.stats())
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 14))
