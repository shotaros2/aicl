"""Compare natural-language agent dialogues with their Koine equivalents.

Each case in bench/cases/<name>/ has nl.txt (what two LLM agents typically
write to each other today) and koine.koine (the same information in Koine).
Both Koine encodings are measured: readable canonical text and the dense
text encoding (SPEC §8.1), which is what agents should actually exchange.

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
        forms = [m.to_form() for m in msgs]
        canon = "\n".join(koine.to_text(f) for f in forms)
        dn = "\n".join(koine.to_dense(f) for f in forms)
        assert [koine.to_text(t) for t in koine.from_dense(dn)] == [koine.to_text(f) for f in forms]
        errors = [i for i in koine.validate_conversation(msgs) if i.level == "error"]
        if errors:
            sys.exit(f"{c.name}: Koine side has errors: {errors}")
        rows.append((c.name, len(nl), tokens.count(nl), len(canon), tokens.count(canon),
                     len(dn), tokens.count(dn), len(msgs), koine.nl_ratio(msgs)))

    print(f"token counter: {tokens.METHOD}\n")
    hdr = (f"{'case':<12}{'NL ch':>7}{'NL tok':>8}{'Koine ch':>10}{'Koine tok':>11}{'ratio':>7}"
           f"{'dense ch':>10}{'dense tok':>11}{'ratio':>7}{'msgs':>6}{'nl%':>5}")
    print(hdr)
    print("-" * len(hdr))
    tn = tk = td = 0
    for name, nc, nt, kc, kt, dc, dt, n, r in rows:
        tn, tk, td = tn + nt, tk + kt, td + dt
        print(f"{name:<12}{nc:>7}{nt:>8}{kc:>10}{kt:>11}{kt / nt:>7.2f}{dc:>10}{dt:>11}{dt / nt:>7.2f}{n:>6}{r * 100:>4.0f}%")
    print("-" * len(hdr))
    print(f"{'total':<12}{'':>7}{tn:>8}{'':>10}{tk:>11}{tk / tn:>7.2f}{'':>10}{td:>11}{td / tn:>7.2f}")
    print("\nratio = tokens / NL tokens (lower is better). nl% = share of Koine body text inside (nl ...).")


if __name__ == "__main__":
    main()
