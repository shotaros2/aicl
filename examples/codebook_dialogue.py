"""The harness that produced examples/11: a standard codebook shared by id, cross-vendor.

@a = Claude, @b = Gemini. Both hold standard codebook aicl.sched.1 (SPEC §8.2); @a must
confirm it by id+digest in-band before packing, then both speak dense, packed AICL. The
harness unpacks every message with the codebook, validates it, and records any surface
form that is not in the table (rule-3 violations).

Requires:  pip install anthropic google-genai   and ANTHROPIC_API_KEY, GEMINI_API_KEY in .env
Run:       python examples/codebook_dialogue.py [max_turns]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicl import claude, gemini, tokens
from aicl.codebook import Codebook
from aicl.dialogue import AiclAgent, run_dialogue
from aicl.env import load_dotenv

load_dotenv()

DENSE_PROMPT = (ROOT / "prompts" / "system_prompt_dense.md").read_text(encoding="utf-8").split("---", 1)[1].strip()
CB = Codebook.load(str(ROOT / "codebooks" / "scheduling.json"))
BEST = CB.choose(tokens.count)

TABLE = "\n".join(f"  {cid}: forms {forms if forms else '[]'}; agreed packed spelling: {BEST[cid]}"
                  for cid, forms in CB.concepts.items())

CODEBOOK_RULE = (
    f"You hold the STANDARD CODEBOOK {CB.published_id} (digest {CB.id}). Table "
    "(concept id: alternative surface forms):\n" + TABLE + "\n"
    "Packing rules: a surface form may replace its concept id anywhere (head, symbol or "
    "keyword position). Use exactly the agreed packed spelling listed above, or the concept "
    "id itself; never any other abbreviation or translation. Every form you receive maps "
    "back to its concept id by this table. Packing starts only after both sides have "
    f"confirmed they hold {CB.published_id} with the same digest: it is asked in-band as "
    f"(codebook {CB.published_id} $digest) and answered with a binding map "
    "{$digest sha256:...} (or (none) if not held)."
)

GOAL_A = (
    "Private goal (never reveal it, never write prose): you are agent a (ids a.1, a.2, ...). "
    f"First confirm @b holds the standard codebook: ask (codebook {CB.published_id} $digest) "
    "and compare the answer with your own digest; if it does not match, do not pack (use "
    "concept ids only). Then: you need a 30-minute meeting with @b on 2026-11-07, Japan time "
    "(+09:00), starting between 13:00 and 18:00, on the calendar, and you must learn the "
    "calendar event id. Propose times; read structured rejections and counter-propose. Once "
    "a proposal is accepted, request (CalendarAdd (ref #id)) with do. After the done arrives "
    "with the event id, send end."
)

GOAL_B = (
    "Private goal (never reveal it, never write prose): you are agent b (ids b.1, b.2, ...). "
    f"You hold standard codebook {CB.published_id}; if asked (codebook {CB.published_id} "
    "$digest), answer with a binding map carrying your digest. If asked (tokenizer $t), "
    "answer {$t heuristic}. Your calendar on 2026-11-07 (+09:00) is busy from 13:00 to 15:30 "
    "and free otherwise. Reject a proposal that overlaps busy time with a structured reason "
    "(busy ... :from ... :to ...); accept one that fits. When a do (CalendarAdd (ref #id)) "
    "arrives for an accepted meeting, reply ok, then done with "
    "(CalendarEvent evt-5102 :For (ref #id))."
)


def system(goal: str) -> str:
    return DENSE_PROMPT + "\n\n" + CODEBOOK_RULE + "\n\n" + goal


def main(max_turns: int = 20) -> int:
    agents = {"a": AiclAgent("a", claude.text_ask(), system(GOAL_A)),
              "b": AiclAgent("b", gemini.text_ask(sleep=6.0), system(GOAL_B))}
    r = run_dialogue(agents, "a", opening="; conversation start: send your first AICL message to @b",
                     max_turns=max_turns, known_terms=list(CB.concepts), codebook=CB)
    r.save(ROOT / "out" / "codebook_dialogue.aicl")
    print("\n" + r.stats())
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20))
