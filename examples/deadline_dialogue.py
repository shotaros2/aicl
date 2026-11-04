"""The harness that produced examples/10: Claude and Gemini negotiating under a deadline.

@a = Claude (requester: needs the result before a hard deadline)
@b = Gemini (performer: the job genuinely takes 25 minutes)

A simulated wall clock is injected: every delivered message is preceded by a comment
line `; now <instant>` and the clock advances 4 minutes per message. Both agents are
told to stamp `:at` from that line (they have no other clock — an LLM cannot know the
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

import anthropic

import aicl
from aicl import tokens
from aicl.env import load_dotenv
from aicl.gemini import text_ask

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

CLAUDE_MODEL = "claude-opus-5-5"
START = datetime(2026, 11, 4, 10, 0, tzinfo=timezone(timedelta(hours=9)))
STEP = timedelta(minutes=4)


def fmt_now(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M+09:00")


class ClaudeAgent:
    def __init__(self, name: str, goal: str):
        self.client = anthropic.Anthropic()
        self.system = AICL_PROMPT.replace("@me", f"@{name}") + "\n\n" + CLOCK_RULE + "\n\n" + goal
        self.history: list[dict] = []

    def turn(self, incoming: str) -> str:
        self.history.append({"role": "user", "content": incoming})
        resp = self.client.beta.messages.create(
            model=CLAUDE_MODEL, max_tokens=2000, system=self.system, messages=self.history,
            output_config={"effort": "low"}, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        self.history.append({"role": "assistant", "content": text})
        return text


class GeminiAgent:
    def __init__(self, name: str, goal: str):
        self.ask = text_ask(sleep=6.0)
        self.system = AICL_PROMPT.replace("@me", f"@{name}") + "\n\n" + CLOCK_RULE + "\n\n" + goal
        self.history: list[dict] = []

    def turn(self, incoming: str) -> str:
        self.history.append({"role": "user", "content": incoming})
        text = self.ask(self.system, self.history).strip()
        if text.startswith("```"):
            text = text.strip("`").removeprefix("lisp").removeprefix("aicl").strip()
        self.history.append({"role": "assistant", "content": text})
        return text


def main(max_turns: int = 18) -> int:
    agents = {"a": ClaudeAgent("a", GOAL_A), "b": GeminiAgent("b", GOAL_B)}
    log: list[aicl.Message] = []
    now = START
    speaker = "a"
    incoming = f"; now {fmt_now(now)}\n; conversation start: send your first AICL message to @b"

    for _ in range(max_turns):
        m = None
        for attempt in range(2):
            raw = agents[speaker].turn(incoming)
            try:
                m = aicl.Message.from_form(aicl.parse_one(raw))
                break
            except aicl.AICLError as e:
                print(f"!! @{speaker} invalid (attempt {attempt + 1}): {e}\n   {raw[:200]}")
                incoming = f"; harness: your message was not valid AICL ({e}); resend one valid AICL message"
        if m is None:
            print(f"!! @{speaker} failed twice; aborting")
            break
        line = aicl.to_text(m.to_form())
        print(line)
        for i in aicl.validate_message(m.to_form()):
            print("   ", i)
        log.append(m)
        if m.act == "end":
            break
        now += STEP
        incoming = f"; now {fmt_now(now)}\n{line}"
        speaker = m.receiver if m.receiver in agents else ("b" if speaker == "a" else "a")

    print("\n--- protocol check ---")
    for i in aicl.validate_conversation(log, ["log-summary"]):
        print(" ", i)
    canon = "\n".join(aicl.to_text(m.to_form()) for m in log)
    out = ROOT / "out" / "deadline_dialogue.aicl"
    out.parent.mkdir(exist_ok=True)
    out.write_text(canon + "\n", encoding="utf-8")
    print(f"\n{len(log)} messages, {tokens.count(canon)} tokens ({tokens.METHOD}), "
          f"nl ratio {aicl.nl_ratio(log):.0%}; saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 18))
