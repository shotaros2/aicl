"""Read-back evaluation: can an LLM map each Koine encoding back to canonical form?

The protocol guarantees that packed messages are unambiguous *to the library*.
This script measures the other half: whether a language model, given the
codebook, reads a dense or packed (possibly mixed-script) message correctly.
For every message in examples/ and bench/cases/ it asks the model to write the
canonical readable form, then parses and canonicalises the answer and compares
it with the expected canonical text. A token saving that costs accuracy is a loss.

Encodings compared:
  readable      canonical text                      (ask #a.1 @a>@b (temp tokyo $t))
  dense         SPEC §8                             (A a.1>b (temp tokyo $t))
  packed        dense + cheapest codebook forms for --tokenizer
  packed-chars  dense + fewest-*characters* forms: the stress case, mostly non-Latin

Run:   python evals/readback.py --model claude-opus-5-5 [--limit 10] [--out evals/results/x.json]
       python evals/readback.py --dry-run           # build cases, no API calls
Needs: pip install anthropic, and ANTHROPIC_API_KEY or `ant auth login`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import koine                                   # noqa: E402
from koine import tokens                       # noqa: E402
from koine.codebook import Codebook            # noqa: E402
from koine.dense import ACT_CODE, KEY_CODE     # noqa: E402

ENCODINGS = ("readable", "dense", "packed", "packed-chars")


# ------------------------------------------------------------------ cases

def build_cases(cb: Codebook, counter) -> list[dict]:
    files = sorted((ROOT / "examples").glob("*.koine")) + sorted((ROOT / "bench" / "cases").glob("*/koine.koine"))
    best_tok = cb.choose(counter)
    best_chr = cb.choose(len)
    cases = []
    for p in files:
        for i, form in enumerate(koine.parse(p.read_text(encoding="utf-8"))):
            if not koine.is_message(form):
                continue
            expected = koine.to_text(form)
            cases.append({
                "file": str(p.relative_to(ROOT)), "index": i, "expected": expected,
                "inputs": {
                    "readable": expected,
                    "dense": koine.to_dense(form),
                    "packed": koine.to_dense(cb.pack(form, best=best_tok)),
                    "packed-chars": koine.to_dense(cb.pack(form, best=best_chr)),
                },
            })
    return cases


def system_prompt(cb: Codebook) -> str:
    acts = " ".join(f"{v}={k}" for k, v in ACT_CODE.items())
    keys = " ".join(f":{v}=:{k}" for k, v in KEY_CODE.items())
    table = "\n".join(f"  {cid}: {' '.join(forms)}" for cid, forms in sorted(cb.concepts.items()) if forms)
    return f"""You convert one Koine message into its canonical readable form. Output only the message, nothing else.

Koine is an S-expression message language: (ACT #id @from>@to [^reply] body... [:key value]... [~conf]).
The input may use these abbreviations; expand every one of them:
- Speech-act codes in head position: {acts}
- Merged header "a.1>b" means "#a.1 @a>@b"; "a.1>*" means "#a.1 @a>*".
- Key codes: {keys}
- Instants in ISO basic form (20261106T1000+9, 20261104T090412Z) become ISO extended with the
  same offset (2026-11-06T10:00+09:00, 2026-11-04T09:04:12Z). Zero seconds are omitted; UTC is "Z".
- Codebook: a term may appear as one of the surface forms below; write the concept id instead.
  Forms apply in symbol, head and keyword positions (":pos" -> ":position").
{table}
Everything else (numbers with units, $vars, strings, lists [...], maps {{...}}, ~conf) stays as is.
Keyword order does not matter. Do not add, drop or rename anything else."""


# ----------------------------------------------------------------- scoring

def score(output: str, expected: str) -> tuple[bool, str]:
    """Parse the model's answer, canonicalise it, compare. Returns (ok, canonical-or-error)."""
    text = output.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("koine"):
            text = text[5:]
    try:
        got = koine.to_text(koine.parse_one(text.strip()))
    except koine.KoineError as e:
        return False, f"unparseable: {e}"
    return got == expected, got


# ------------------------------------------------------------------- model

def make_anthropic_asker(model: str):
    import anthropic
    client = anthropic.Anthropic()

    def ask(system: str, user: str) -> str:
        resp = client.beta.messages.create(
            model=model, max_tokens=1000, system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            return "<refused>"
        return "".join(b.text for b in resp.content if b.type == "text")
    return ask


def run(cases, ask, encodings=ENCODINGS, system="", counter=tokens.count, verbose=False) -> dict:
    results = {enc: {"n": 0, "ok": 0, "tokens": 0, "failures": []} for enc in encodings}
    for c in cases:
        for enc in encodings:
            inp = c["inputs"][enc]
            out = ask(system, inp)
            ok, got = score(out, c["expected"])
            r = results[enc]
            r["n"] += 1
            r["ok"] += ok
            r["tokens"] += counter(inp)
            if not ok:
                r["failures"].append({"file": c["file"], "index": c["index"], "input": inp,
                                      "expected": c["expected"], "got": got})
            if verbose:
                print(f"{'ok ' if ok else 'ERR'} {enc:<13} {inp[:70]}")
    return results


def report(results: dict) -> str:
    lines = [f"{'encoding':<14}{'n':>5}{'accuracy':>10}{'tokens/msg':>12}"]
    for enc, r in results.items():
        if r["n"]:
            lines.append(f"{enc:<14}{r['n']:>5}{r['ok'] / r['n']:>10.1%}{r['tokens'] / r['n']:>12.1f}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--codebook", default=str(ROOT / "codebooks" / "bench.json"))
    ap.add_argument("--tokenizer", default=None, help="auto | chars | heuristic | cl100k_base | o200k_base")
    ap.add_argument("--encodings", default=",".join(ENCODINGS))
    ap.add_argument("--limit", type=int, default=0, help="first N messages only")
    ap.add_argument("--out", default=None, help="write JSON results here")
    ap.add_argument("--dry-run", action="store_true", help="build cases and prompt, no API calls")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    cb = Codebook.load(a.codebook)
    counter = tokens.get_counter(a.tokenizer)
    cases = build_cases(cb, counter)
    if a.limit:
        cases = cases[:a.limit]
    encodings = tuple(e.strip() for e in a.encodings.split(","))
    system = system_prompt(cb)
    print(f"{len(cases)} messages x {len(encodings)} encodings; codebook {cb.name} {cb.id}; "
          f"tokenizer {a.tokenizer or tokens.METHOD}; system prompt {counter(system)} tokens")
    if a.dry_run:
        for enc in encodings:
            print(f"  {enc:<13} {cases[0]['inputs'][enc]}")
        return 0

    ask = make_anthropic_asker(a.model)
    t0 = time.time()
    results = run(cases, ask, encodings, system, counter, a.verbose)
    print(report(results))
    print(f"model {a.model}, {time.time() - t0:.0f}s")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"model": a.model, "codebook": cb.id, "tokenizer": a.tokenizer or tokens.METHOD,
                                           "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
