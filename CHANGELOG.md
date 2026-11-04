# Changelog

## 0.1.0 — 2026-11-04

First public draft.

- Specification: abstract model, text / dense text / JSON / CBOR encodings, 16 speech acts,
  core logical vocabulary, vocabulary resolution via `def` and namespaces,
  canonical form and hashing, conformance criteria.
- Reference implementation (Python, no dependencies): lexer, parser, canonical
  and pretty printers, dense text codec (22 % fewer cl100k tokens than the
  readable form), tokenizer-aware codebooks (`koine pack` / `unpack`, with the
  injectivity and unknown-form rules that keep packing ambiguity-free), JSON
  and deterministic CBOR codecs, message and conversation validator, `koine` CLI.
- Six worked examples, a two-agent in-process demo, an LLM-to-LLM demo, a
  system prompt that teaches any LLM to speak Koine, and a token benchmark.
- `evals/readback.py`: read-back accuracy evaluation per encoding (readable,
  dense, packed, packed-chars); first results on gemini-3.5-flash-lite in
  `evals/results/` and the README.
- `rulebook/`: generated hand-off folder with both language references, the
  spec, grammar, example codebooks and conversations, plus a bilingual index.
