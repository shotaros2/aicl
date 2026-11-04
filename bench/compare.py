"""Compare natural-language agent dialogues with their Koine equivalents.

Each case in bench/cases/<name>/ has nl.txt (what two LLM agents typically
write to each other today) and koine.koine (the same information in Koine).
Prints characters, tokens, and the number of unresolved references that a
reader of the NL version has to guess.

Run:  python bench/compare.py
Install tiktoken (`pip install tiktoken`) for exact cl100k_base token counts;
otherwise a heuristic estimate is used and labelled as such.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import koine                      # noqa: E402
from koine import tokens          # noqa: E402


def main():
    cases = sorted(p for p in (ROOT / "bench" / "cases").iterdir() if p.is_dir())
    rows = []
    for c in cases:
        nl = (c / "nl.txt").read_text(encoding="utf-8").strip()
        src = (c / "koine.koine").read_text(encoding="utf-8")
        msgs = koine.parse_messages(src)
        canon = "\n".join(koine.to_text(m.to_form()) for m in msgs)
        errors = [i for i in koine.validate_conversation(msgs) if i.level == "error"]
        if errors:
            sys.exit(f"{c.name}: Koine side has errors: {errors}")
        rows.append((c.name, len(nl), tokens.count(nl), len(canon), tokens.count(canon),
                     len(msgs), koine.nl_ratio(msgs)))

    print(f"token counter: {tokens.METHOD}\n")
    hdr = f"{'case':<14}{'NL chars':>10}{'NL tok':>8}{'Koine chars':>13}{'Koine tok':>11}{'ratio':>8}{'msgs':>6}{'nl%':>6}"
    print(hdr)
    print("-" * len(hdr))
    tn = tk = 0
    for name, nc, nt, kc, kt, n, r in rows:
        tn += nt
        tk += kt
        print(f"{name:<14}{nc:>10}{nt:>8}{kc:>13}{kt:>11}{kt / nt:>8.2f}{n:>6}{r * 100:>5.0f}%")
    print("-" * len(hdr))
    print(f"{'total':<14}{'':>10}{tn:>8}{'':>13}{tk:>11}{tk / tn:>8.2f}")
    print("\nratio = Koine tokens / NL tokens (lower is better). nl% = share of Koine body text inside (nl …).")


if __name__ == "__main__":
    main()
