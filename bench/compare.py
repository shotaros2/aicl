"""Compare natural-language agent dialogues with their AICL equivalents.

Each case in bench/cases/<name>/ has nl.txt (what two LLM agents typically
write to each other today) and aicl.aicl (the same information in AICL).
Three AICL encodings are measured: readable canonical text, the dense text
encoding (SPEC §8) and the dense text packed with codebooks/bench.json
(SPEC §8.1), which is what two agents sharing that codebook would exchange.

Run:  python bench/compare.py
Install tiktoken (`pip install tiktoken`) for exact cl100k_base token counts;
otherwise a heuristic estimate is used and labelled as such.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aicl                      # noqa: E402
from aicl import tokens          # noqa: E402
from aicl.codebook import Codebook  # noqa: E402


def main():
    cb = Codebook.load(str(ROOT / "codebooks" / "bench.json"))
    best = cb.choose(tokens.count)
    cases = sorted(p for p in (ROOT / "bench" / "cases").iterdir() if p.is_dir())
    rows = []
    for c in cases:
        nl = (c / "nl.txt").read_text(encoding="utf-8").strip()
        src = (c / "aicl.aicl").read_text(encoding="utf-8")
        msgs = aicl.parse_messages(src)
        forms = [m.to_form() for m in msgs]
        canon = [aicl.to_text(f) for f in forms]
        dn = "\n".join(aicl.to_dense(f) for f in forms)
        pk = "\n".join(aicl.to_dense(cb.pack(f, best=best)) for f in forms)
        assert [aicl.to_text(t) for t in aicl.from_dense(dn)] == canon
        assert [aicl.to_text(t) for t in cb.unpack(pk)] == canon
        errors = [i for i in aicl.validate_conversation(msgs) if i.level == "error"]
        if errors:
            sys.exit(f"{c.name}: AICL side has errors: {errors}")
        rows.append((c.name, tokens.count(nl), tokens.count("\n".join(canon)), tokens.count(dn),
                     tokens.count(pk), len(msgs), aicl.nl_ratio(msgs)))

    print(f"token counter: {tokens.METHOD}   codebook: {cb.name} ({cb.id})\n")
    hdr = (f"{'case':<12}{'NL':>6}{'readable':>10}{'ratio':>7}{'dense':>8}{'ratio':>7}"
           f"{'packed':>8}{'ratio':>7}{'msgs':>6}{'nl%':>5}")
    print(hdr)
    print("-" * len(hdr))
    tn = tk = td = tp = 0
    for name, nt, kt, dt, pt, n, r in rows:
        tn, tk, td, tp = tn + nt, tk + kt, td + dt, tp + pt
        print(f"{name:<12}{nt:>6}{kt:>10}{kt / nt:>7.2f}{dt:>8}{dt / nt:>7.2f}{pt:>8}{pt / nt:>7.2f}{n:>6}{r * 100:>4.0f}%")
    print("-" * len(hdr))
    print(f"{'total':<12}{tn:>6}{tk:>10}{tk / tn:>7.2f}{td:>8}{td / tn:>7.2f}{tp:>8}{tp / tn:>7.2f}")
    print("\nAll columns are tokens; ratio = tokens / NL tokens (lower is better). nl% = share of body text inside (nl ...).")


if __name__ == "__main__":
    main()
