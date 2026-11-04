"""Two Claude instances talking to each other in AICL.

Each side is an ordinary LLM call whose system prompt is prompts/system_prompt.md
plus a private goal. Every message is parsed and validated with the aicl library
before it is delivered, so a malformed message is caught at the boundary instead
of being silently "understood".

Requires:  pip install anthropic   and   ANTHROPIC_API_KEY (or `ant auth login`)
Run:       python examples/llm_dialogue.py [max_turns]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic

import aicl
from aicl import tokens
from aicl.env import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
MODEL = "claude-opus-5-5"

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


class LLMAgent:
    def __init__(self, client: anthropic.Anthropic, name: str):
        self.client = client
        self.name = name
        self.system = AICL_PROMPT.replace("@me", f"@{name}") + "\n\n" + GOALS[name]
        self.history: list[dict] = []

    def turn(self, incoming: str) -> str:
        self.history.append({"role": "user", "content": incoming})
        resp = self.client.beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=self.system,
            messages=self.history,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"@{self.name}: request refused ({resp.stop_details and resp.stop_details.category})")
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        self.history.append({"role": "assistant", "content": text})
        return text


def main(max_turns: int = 14):
    client = anthropic.Anthropic()
    agents = {"a": LLMAgent(client, "a"), "b": LLMAgent(client, "b")}
    log: list[aicl.Message] = []
    speaker, incoming = "a", "; conversation start: send your first AICL message to @b"
    for _ in range(max_turns):
        raw = agents[speaker].turn(incoming)
        try:
            m = aicl.Message.from_form(aicl.parse_one(raw))
        except aicl.AICLError as e:
            print(f"!! @{speaker} produced an invalid message: {e}\n   {raw}")
            return 1
        issues = aicl.validate_message(m.to_form())
        bad = [i for i in issues if i.level == "error"]
        print(aicl.to_text(m.to_form()) + ("" if not bad else f"   !! {bad}"))
        log.append(m)
        if m.act == "end":
            break
        incoming = aicl.to_text(m.to_form())
        speaker = m.receiver if m.receiver in agents else ("b" if speaker == "a" else "a")

    print("\n--- protocol check ---")
    issues = aicl.validate_conversation(log, ["meeting", "busy", "calendar-add", "calendar-event"])
    for i in issues:
        print(" ", i)
    canon = "\n".join(aicl.to_text(m.to_form()) for m in log)
    print(f"{len(log)} messages, {tokens.count(canon)} tokens ({tokens.METHOD}), nl ratio {aicl.nl_ratio(log):.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 14))
