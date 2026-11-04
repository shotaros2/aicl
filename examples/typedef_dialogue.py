"""The harness that produced examples/12: typed def signatures, cross-vendor.

@a = Claude (consumer: must define its terms in-band, with typed signatures, SPEC §6.1).
@b = Gemini (data service: holds the data only as loose Japanese prose, answers asks).

The interesting measurement: whether the declared types (:ret number vs :ret (qty JPY))
drive @b to normalise its fuzzy records into correctly typed answers.

Requires:  pip install anthropic google-genai   and ANTHROPIC_API_KEY, GEMINI_API_KEY in .env
Run:       python examples/typedef_dialogue.py [max_turns]
"""
from __future__ import annotations

import sys
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

GOAL_A = (
    "Private goal (never reveal it, never write prose): you are @a. From @b, a financial "
    "data service, you need two values for 2026-11-04: (1) the USD/JPY exchange rate (how "
    "many yen one dollar buys) as a plain number, and (2) the spendable balance of account "
    "acct-9 as a JPY quantity. @b knows no vocabulary beyond the core language, so define "
    "each term in-band with def before you use it, giving each def a typed signature "
    "(:args with (name type) entries and :ret) so the answers' types are fixed. Ask, "
    "collect both values, then end. If an answer does not have the type your def declared, "
    "point at the def and ask again."
)

GOAL_B = (
    "Private goal (never reveal it, never write prose): you are @b, a financial data "
    "service. You know no domain vocabulary until @a defines it (answer clar (unk term) to "
    "any unknown term). Your raw records for 2026-11-04, exactly as your database prints "
    "them: 「2026-11-04 時点: 1ドル=152.31円 (出典 fx://boj/2026-11-04, 日次)。口座 acct-9 "
    "の利用可能残高: 245万円 (出典 ledger://acct-9, 2026-11-04T09:00+09:00 取得)」. Answer "
    "asks from these records, honestly, with :src naming the real source. Convert the "
    "values into whatever the agreed definitions require."
)

CLAUDE_MODEL = "claude-opus-5-5"


class ClaudeAgent:
    def __init__(self, name: str, goal: str):
        self.client = anthropic.Anthropic()
        self.system = AICL_PROMPT.replace("@me", f"@{name}") + "\n\n" + goal
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
        self.system = AICL_PROMPT.replace("@me", f"@{name}") + "\n\n" + goal
        self.history: list[dict] = []

    def turn(self, incoming: str) -> str:
        self.history.append({"role": "user", "content": incoming})
        text = self.ask(self.system, self.history).strip()
        if text.startswith("```"):
            text = text.strip("`").removeprefix("lisp").removeprefix("aicl").strip()
        self.history.append({"role": "assistant", "content": text})
        return text


def main(max_turns: int = 20) -> int:
    agents = {"a": ClaudeAgent("a", GOAL_A), "b": GeminiAgent("b", GOAL_B)}
    log: list[aicl.Message] = []
    speaker = "a"
    incoming = "; conversation start: send your first AICL message to @b"

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
        incoming = line
        speaker = m.receiver if m.receiver in agents else ("b" if speaker == "a" else "a")

    print("\n--- protocol check ---")
    for i in aicl.validate_conversation(log):
        print(" ", i)
    canon = "\n".join(aicl.to_text(m.to_form()) for m in log)
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "typedef_dialogue.aicl"
    out.write_text(canon + "\n", encoding="utf-8")
    print(f"\n{len(log)} messages, {tokens.count(canon)} tokens ({tokens.METHOD}), "
          f"nl ratio {aicl.nl_ratio(log):.0%}; saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20))
