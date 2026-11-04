# Contributing to Koine

Koine is an open specification. Changes to the *language* and changes to the
*reference implementation* follow different paths.

## Changing the language (SPEC.md)

1. Open an issue titled `RFC: <short title>` describing the problem a real
   agent-to-agent exchange has today that the current spec cannot express
   unambiguously, with a concrete example in Koine.
2. Proposals must say what happens to existing conforming messages (nothing
   that is valid in 0.x may silently change meaning).
3. A spec change is merged together with: the EBNF update, the reference
   implementation, at least one example under `examples/`, and tests.

## Changing the reference implementation

```bash
pip install -e ".[dev]"
python -m unittest discover -s tests -v
python examples/two_agents_demo.py
python bench/compare.py
```

- No runtime dependencies. The implementation must stay small enough to port
  to another language in an afternoon; that is the point of a reference.
- Canonical form is frozen within a minor version. If a change alters the
  canonical text of any existing example, the digest test will fail; say so
  in the PR and bump the version.

## Adding a benchmark case

Add `bench/cases/<name>/nl.txt` (a realistic natural-language exchange between
two LLM agents, with the pleasantries they really produce) and
`bench/cases/<name>/koine.koine` carrying the same information. Do not pad the
NL side to make Koine look better; the comparison is only useful if it is fair.

## Ports

Implementations in other languages are welcome in separate repositories.
They are conformant when they pass the criteria in SPEC.md §12; open an issue
to be listed in the README.
