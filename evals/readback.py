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

Run:   python evals/readback.py --provider anthropic --model claude-opus-5-5 [--limit 10] [--out evals/results/x.json]
       python evals/readback.py --provider gemini --model gemini-3.8-flash
       python evals/readback.py --dry-run           # build cases, no API calls
Needs: pip install anthropic (ANTHROPIC_API_KEY or `ant auth login`) or
       pip install google-genai (GEMINI_API_KEY). Other providers: add a
       make_<name>_asker(model) returning ask(system, user) -> str to PROVIDERS.
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
    # Present the codebook in the direction the reader needs: surface form -> concept id.
    table = "\n".join(f"  {form} -> {cid}" for form, cid in sorted(cb.form_to_concept.items()))
    return f"""You convert one Koine message into its canonical readable form. Output only the message, nothing else.

Koine is an S-expression message language: (ACT #id @from>@to [^reply] body... [:key value]... [~conf]).
The input may use these abbreviations; expand every one of them:
- Speech-act codes in head position: {acts}
- Merged header "a.1>b" means "#a.1 @a>@b"; "a.1>*" means "#a.1 @a>*".
- Key codes: {keys}
- Instants in ISO basic form (20261106T1000+9, 20261104T090412Z) become ISO extended with the
  same offset (2026-11-06T10:00+09:00, 2026-11-04T09:04:12Z). Zero seconds are omitted; UTC is "Z".
- Codebook: every term in the input that appears on the LEFT of the table below is a surface
  form; write the concept id on the RIGHT instead. Forms often look like ordinary English words
  or abbreviations (deploy, roll, err, CI, Tokyo), so check EVERY symbol and keyword against the
  table. Forms apply in symbol, head and keyword positions (":pos" -> ":position").
  A term that is already a concept id (on the right) stays exactly as it is.
{table}
Everything else (numbers with units, $vars, strings, lists [...], maps {{...}}, ~conf) stays as is.
Keyword order does not matter. Do not add, drop or rename anything else.

Pitfalls that count as errors:
- Act names are lowercase words (ask, tell, do, ok, done, ...), never a code letter and never uppercase.
- The header is "#id" then "@from>@to"; a reply id is written "^a.1", never "^#a.1".
- Keep every parenthesis, bracket and brace exactly. {{$t 18.5C}} is a map whose key is the variable $t.
- Positional arguments stay positional; keyword arguments stay keywords. Do not convert between them.
- Never "correct" a term to a synonym (temp stays temp). Only codebook forms are rewritten, and only to their concept id.

Worked examples:
Input:  (Z b.4>a ^a.3 {{$x 2}} :a 20261104T090412Z :s log ~0.8)
Output: (done #b.4 @b>@a ^a.3 {{$x 2}} :at 2026-11-04T09:04:12Z :src log ~0.8)
Input:  (A a.1>* (status svc-9 $s :window PT5M) :c q1)
Output: (ask #a.1 @a>* (status svc-9 $s :window PT5M) :conv q1)
Input:  (T b.5>a ^a.4 (Temp Tokyo 18.5C :Window PT1H) :s JMA)      <- Temp, Tokyo, Window, JMA are codebook forms
Output: (tell #b.5 @b>@a ^a.4 (temp tokyo 18.5C :window PT1H) :src jma)
Input:  (N b.2>a ^a.2 :w (busy @b :from 20261106T0900+9 :to 20261106T1100+9))
Output: (no #b.2 @b>@a ^a.2 :why (busy @b :from 2026-11-06T09:00+09:00 :to 2026-11-06T11:00+09:00))"""


# ----------------------------------------------------------- diagnostics

def _shape(t) -> str:
    """Structure of a term with atom values erased, for telling vocabulary errors from structural ones."""
    if isinstance(t, koine.Form):
        return "(" + " ".join(_shape(a) for a in t.args) + "|" + " ".join(_shape(t.kw[k]) for k in sorted(t.kw)) + ")"
    if isinstance(t, koine.KList):
        return "[" + " ".join(_shape(a) for a in t.items) + "]"
    if isinstance(t, koine.KMap):
        return "{" + " ".join(_shape(k) + ":" + _shape(v) for k, v in t.items) + "}"
    return type(t).__name__


def classify_failure(got: str, expected: str) -> str:
    """unparseable | act | vocab | structure"""
    if got.startswith("unparseable") or got.startswith("<"):
        return "unparseable"
    try:
        g, e = koine.parse_one(got), koine.parse_one(expected)
    except koine.KoineError:
        return "unparseable"
    if isinstance(g, koine.Form) and isinstance(e, koine.Form) and g.head != e.head:
        return "act"
    return "vocab" if _shape(g) == _shape(e) else "structure"


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


def make_gemini_asker(model: str):
    from google import genai
    from google.genai import types
    client = genai.Client()  # reads GEMINI_API_KEY (or GOOGLE_API_KEY)
    config = types.GenerateContentConfig(temperature=0)

    def ask(system: str, user: str) -> str:
        config.system_instruction = system
        resp = client.models.generate_content(model=model, contents=user, config=config)
        try:
            return resp.text or ""
        except ValueError:          # blocked or empty candidate
            return "<blocked>"
    return ask


def list_models(provider: str) -> list[str]:
    if provider == "gemini":
        from google import genai
        client = genai.Client()
        return sorted(m.name.removeprefix("models/") for m in client.models.list()
                      if "generateContent" in (m.supported_actions or []))
    if provider == "anthropic":
        import anthropic
        return sorted(m.id for m in anthropic.Anthropic().models.list())
    raise ValueError(provider)


PROVIDERS = {
    "anthropic": (make_anthropic_asker, "claude-opus-5-5"),
    "gemini": (make_gemini_asker, "gemini-3.8-flash"),
}


def ask_with_retry(ask, system: str, user: str, attempts: int = 6, first_wait: float = 5.0) -> str:
    """Retry on transient provider errors (503 overload, 429 rate limit, network) with backoff."""
    wait = first_wait
    for i in range(attempts):
        try:
            return ask(system, user)
        except Exception as e:  # provider-specific error classes; message text is enough here
            msg = str(e)
            if "PerDay" in msg or "per day" in msg:
                sys.exit("daily free-tier quota exhausted for this model; it resets at midnight Pacific time. "
                         "Try another model (--list-models) or re-run tomorrow.")
            transient = any(k in msg for k in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded", "timeout", "Timeout"))
            if not transient or i == attempts - 1:
                return f"<error: {msg[:200]}>"
            detail = msg
            for key in ("quotaMetric", "quota_metric", "retryDelay", "per day", "per minute"):
                if key in msg:
                    j = msg.find(key)
                    detail = msg[max(0, j - 40): j + 120]
                    break
            print(f"  transient error, retrying in {wait:.0f}s ({i + 1}/{attempts - 1}): {detail[:200]}", file=sys.stderr)
            time.sleep(wait)
            wait = min(wait * 2, 60)
    return "<error>"


def run(cases, ask, encodings=ENCODINGS, system="", counter=tokens.count, verbose=False, sleep: float = 0.0) -> dict:
    results = {enc: {"n": 0, "ok": 0, "tokens": 0, "failures": []} for enc in encodings}
    for c in cases:
        for enc in encodings:
            inp = c["inputs"][enc]
            out = ask_with_retry(ask, system, inp)
            if sleep:
                time.sleep(sleep)   # stay under per-minute rate limits (free tiers)
            ok, got = score(out, c["expected"])
            r = results[enc]
            r["n"] += 1
            r["ok"] += ok
            r["tokens"] += counter(inp)
            if not ok:
                r["failures"].append({"file": c["file"], "index": c["index"], "input": inp,
                                      "expected": c["expected"], "got": got,
                                      "kind": classify_failure(got, c["expected"])})
            if verbose:
                print(f"{'ok ' if ok else 'ERR'} {enc:<13} {inp[:70]}")
    return results


def report(results: dict) -> str:
    kinds = ("unparseable", "act", "vocab", "structure")
    lines = [f"{'encoding':<14}{'n':>5}{'accuracy':>10}{'tokens/msg':>12}  failures by kind: " + " ".join(f"{k:>11}" for k in kinds)]
    for enc, r in results.items():
        if r["n"]:
            counts = {k: sum(1 for f in r["failures"] if f.get("kind") == k) for k in kinds}
            lines.append(f"{enc:<14}{r['n']:>5}{r['ok'] / r['n']:>10.1%}{r['tokens'] / r['n']:>12.1f}"
                         + " " * 20 + " ".join(f"{counts[k]:>11}" for k in kinds))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provider", choices=sorted(PROVIDERS), default="anthropic")
    ap.add_argument("--model", default=None, help="provider default: " + ", ".join(f"{p}={m}" for p, (_, m) in PROVIDERS.items()))
    ap.add_argument("--codebook", default=str(ROOT / "codebooks" / "bench.json"))
    ap.add_argument("--tokenizer", default=None, help="auto | chars | heuristic | cl100k_base | o200k_base")
    ap.add_argument("--encodings", default=",".join(ENCODINGS))
    ap.add_argument("--limit", type=int, default=0, help="first N messages only")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds to wait between calls (rate limits)")
    ap.add_argument("--out", default=None, help="write JSON results here")
    ap.add_argument("--dry-run", action="store_true", help="build cases and prompt, no API calls")
    ap.add_argument("--list-models", action="store_true", help="print the provider's available model names and exit")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.list_models:
        print("\n".join(list_models(a.provider)))
        return 0

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

    make_asker, default_model = PROVIDERS[a.provider]
    model = a.model or default_model
    ask = make_asker(model)
    t0 = time.time()
    results = run(cases, ask, encodings, system, counter, a.verbose, a.sleep)
    print(report(results))
    print(f"{a.provider} {model}, {time.time() - t0:.0f}s")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"provider": a.provider, "model": model, "codebook": cb.id,
                                           "tokenizer": a.tokenizer or tokens.METHOD, "results": results},
                                          ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
