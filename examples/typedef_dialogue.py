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

from aicl import claude, gemini
from aicl.dialogue import AiclAgent, run_dialogue
from aicl.env import load_dotenv

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


def system(name: str, goal: str) -> str:
    return AICL_PROMPT.replace("@me", f"@{name}") + "\n\n" + goal


def main(max_turns: int = 20) -> int:
    agents = {"a": AiclAgent("a", claude.text_ask(), system("a", GOAL_A)),
              "b": AiclAgent("b", gemini.text_ask(sleep=6.0), system("b", GOAL_B))}
    r = run_dialogue(agents, "a", opening="; conversation start: send your first AICL message to @b",
                     max_turns=max_turns)
    r.save(ROOT / "out" / "typedef_dialogue.aicl")
    print("\n" + r.stats())
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20))
