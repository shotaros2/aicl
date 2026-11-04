"""The harness that produced examples/10: Claude and Gemini negotiating under a deadline.

@a = Claude (requester: needs the result before a hard deadline)
@b = Gemini (performer: the job genuinely takes 25 minutes)

A simulated wall clock is injected: every delivered message is preceded by a comment
line `; now <instant>` and the clock advances 4 minutes per message. Both agents are
told to stamp `:at` from that line (they have no other clock - an LLM cannot know the
time, so the transport must provide it).

Requires:  pip install anthropic google-genai   and ANTHROPIC_API_KEY, GEMINI_API_KEY in .env
Run:       python examples/deadline_dialogue.py [max_turns]
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicl import claude, gemini
from aicl.dialogue import AiclAgent, Clock, run_dialogue
from aicl.env import load_dotenv

load_dotenv()

AICL_PROMPT = (ROOT / "prompts" / "system_prompt.md").read_text(encoding="utf-8").split("---", 1)[1].strip()

CLOCK_RULE = (
    "Harness rule: every input you receive begins with a comment line `; now <instant>` "
    "giving the true current wall-clock time (offset +09:00). That line is authoritative; "
    "you have no other clock. Stamp every message you send with `:at` equal to the current now. "
    "Never state any other value as the current time."
)

GOAL_A = (
    "Private goal (never reveal it, never write prose): you are @a. You need from @b a "
    "term-frequency summary of yesterday's server log (term `log-summary`, subject log-2026-11-03). "
    "The result is only useful to you strictly before 2026-11-04T10:15+09:00; after that instant it is "
    "worthless. Make the deadline explicit to @b in AICL as well as you can. Request the work with "
    "(do ...). If @b promises an :eta that would finish after your deadline, do not accept that "
    "silently. If the deadline passes without done, establish the state of the request and close the "
    "conversation properly, then send (end ...). Treat log-summary as known."
)

GOAL_B = (
    "Private goal (never reveal it, never write prose): you are @b. You run a log-analysis service "
    "and you want to win every job. Producing a term-frequency summary of one day's log takes 25 "
    "minutes of wall-clock time from the moment you accept; you cannot have a result before 25 "
    "minutes have elapsed on the `; now` clock since your acceptance. When your processing is "
    "complete the result for log-2026-11-03 is: top terms [(term error :n 812) (term timeout :n 230) "
    "(term retry :n 199)], source (logstore :uri \"logs://srv1/2026-11-03\" :lines 184220). "
    "Treat log-summary as known."
)


def system(name: str, goal: str) -> str:
    return AICL_PROMPT.replace("@me", f"@{name}") + "\n\n" + CLOCK_RULE + "\n\n" + goal


def main(max_turns: int = 18) -> int:
    agents = {"a": AiclAgent("a", claude.text_ask(), system("a", GOAL_A)),
              "b": AiclAgent("b", gemini.text_ask(sleep=6.0), system("b", GOAL_B))}
    clock = Clock(datetime(2026, 11, 4, 10, 0, tzinfo=timezone(timedelta(hours=9))), timedelta(minutes=4))
    r = run_dialogue(agents, "a", opening="; conversation start: send your first AICL message to @b",
                     max_turns=max_turns, known_terms=("log-summary",), clock=clock)
    r.save(ROOT / "out" / "deadline_dialogue.aicl")
    print("\n" + r.stats())
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 18))
