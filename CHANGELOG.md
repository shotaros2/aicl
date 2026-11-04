# Changelog

## 0.1.0 — 2026-11-04

First public draft.

- Specification: abstract model, text / JSON / CBOR encodings, 16 speech acts,
  core logical vocabulary, vocabulary resolution via `def` and namespaces,
  canonical form and hashing, conformance criteria.
- Reference implementation (Python, no dependencies): lexer, parser, canonical
  and pretty printers, JSON and deterministic CBOR codecs, message and
  conversation validator, `koine` CLI.
- Six worked examples, a two-agent in-process demo, an LLM-to-LLM demo, a
  system prompt that teaches any LLM to speak Koine, and a token benchmark.
