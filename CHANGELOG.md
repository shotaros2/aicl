# Changelog

## 0.2.0 — 2026-11-04

Every change comes from a live observation (a Gemini Gem given the rulebook, and a
Claude–Gemini negotiation relayed by hand; see `examples/07` and `examples/08`).
Canonical forms of 0.1 messages are unchanged.

- New act `retract` (dense `B`): withdraw your own earlier message with `:why`;
  reopens what it closed. A second `acc`/`rej` on a closed proposal is now the
  error `prop-closed`. (Observed: `acc` then `rej` on the same proposal.)
- Evidence: an answer to `why` must carry `:src`, either structured
  `(source :uri … :at … :kind … :value …)` or `(none)`; terms under `:src` are
  exempt from vocabulary resolution. (Observed: a source name invented after the fact.)
- New core query `(status (ref #id) $s)` with answers `pending done failed unknown`;
  `:eta` on `ok` lets the requester expire an open request. (Observed: an accepted `do`
  never closed.)
- Time intervals are half-open; `:after`/`:before` are strict. (Observed: 06:00
  proposed as free after "busy until 06:00".)
- `def` scope: a `def` to one agent binds that pair; a `def` to `*` is shared. The
  validator resolves terms per pair. (Observed: a pair-scoped term honoured for a
  third party.)
- Parsers accept redundant-sigil slips (`a.1>@b`, `^#a.1`); LLM agents in the
  cooperation layer get their next id and reply header as an AICL comment, one
  correction turn, and renumbering.
- Prompts, rulebook, examples (07 live, 08 v0.2 features) and 92 tests updated.

## 0.1.0 — 2026-11-04

First public draft.

- Specification: abstract model, text / dense text / JSON / CBOR encodings, 16 speech acts,
  core logical vocabulary, vocabulary resolution via `def` and namespaces,
  canonical form and hashing, conformance criteria.
- Reference implementation (Python, no dependencies): lexer, parser, canonical
  and pretty printers, dense text codec (22 % fewer cl100k tokens than the
  readable form), tokenizer-aware codebooks (`aicl pack` / `unpack`, with the
  injectivity and unknown-form rules that keep packing ambiguity-free), JSON
  and deterministic CBOR codecs, message and conversation validator, `aicl` CLI.
- Six worked examples, a two-agent in-process demo, an LLM-to-LLM demo, a
  system prompt that teaches any LLM to speak AICL, and a token benchmark.
- `evals/readback.py`: read-back accuracy evaluation per encoding (readable,
  dense, packed, packed-chars); first results on gemini-3.5-flash-lite in
  `evals/results/` and the README.
- `rulebook/`: generated hand-off folder with both language references, the
  spec, grammar, example codebooks and conversations, plus a bilingual index.
- Cooperation layer (`aicl/coop.py`, `schemas/cooperation.md`): bus with
  validation, specialist agents, hub with registry and dependency-ordered
  delegation, recipe and LLM planners, artifact passing; offline demo and a
  live Gemini demo (planner, SVG image specialist, AICL-speaking code agent).
- Parsers accept two redundant-sigil slips on input (`a.1>@b`, `^#a.1`);
  canonical output is unchanged.
