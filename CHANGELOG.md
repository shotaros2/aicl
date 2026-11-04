# Changelog

## Unreleased

Standard codebooks, from a live packed Claude–Gemini exchange on 2026-11-04
(`examples/11`, runner `examples/codebook_dialogue.py`):

- SPEC §8.2: **standard codebooks**, published in `codebooks/` under a versioned id and
  immutable (a change is a new id; digests are frozen by a test). First two:
  `aicl.sched.1` (scheduling) and `aicl.deploy.1` (deployment); a data-query codebook
  waits for a live exchange to ground its vocabulary. The handshake is in-band:
  `(ask … (codebook aicl.sched.1 $digest))` answered with the digest or `(none)`.
  In the live run the id+digest handshake succeeded, both sides packed with zero
  rule-3 violations, and the wire cost measured 370 tokens vs 480 readable (−23 %).
- New warning `status-unclosed`: a status answered `done`/`failed` for a request that
  is never then closed with `done`/`fail`. (Observed: Gemini answered `{$s done}`,
  never sent the real `done`, then answered a follow-up ask with a `done` act —
  the existing `done-for-ask` error caught that part.)
- `Codebook` gains `published_id` (the JSON `id` field); `aicl codebook` prints it.

Checkable deadlines and retract finality, each from a live Claude–Gemini deadline
negotiation on 2026-11-04 run under a harness-injected clock (`examples/10`):

- SPEC §3: act names are not reserved words. A form is a message only when it is
  well-formed as one (`#id` + route); an act-named form nested in a body, such as
  `:if (done (ref #a.1))`, is an ordinary term. Previously the text, dense, JSON
  and CBOR encoders all crashed on such a term. Canonical forms of previously
  encodable documents are unchanged. (Observed: in a live deadline negotiation,
  Claude used `done` as a body term in its third message.)
- New standard key `:by instant` on `do`/`prop` (dense `:b`): hard deadline after
  which the result is worthless. (Observed: with no standard key, the requester
  improvised `:by`, `:if (< now …)` and `:deadline` across runs.)
- An `ok` carrying `:eta` SHOULD carry `:at`; new checks `eta-unanchored` (warning,
  `:eta` without `:at`) and `eta-overrun` (warning, `:at + :eta` past the `do`'s
  `:by` — pure message arithmetic, no clock needed). `aicl check --now <instant>`
  additionally flags `deadline-passed` and `eta-expired` on still-open requests.
  This closes the §13 question "deadlines the validator can check".
- SPEC §4.4: `retract` is unilateral and final; answering a retracted message is
  the new warning `stale-reply`. (Observed: a performer answered a `retract` of
  an accepted `do` with `fail "cannot retract"`.)
- `nested-act` now fires only for a well-formed message nested inside a message,
  not for act-named ordinary terms.
- Prompts: ids are `#me.N` *with your own name substituted for `me`* (observed:
  an agent emitted literal `#me.1` ids); promise `:at <now> :eta …`; respect `:by`.

- `rulebook/aicl-skill.zip` (and `rulebook/skill/aicl/`): an Agent Skill for chat
  apps that install skills (Dola, Claude): `SKILL.md` with YAML name/description
  and the dense rulebook inline, plus the readable rulebook, cooperation schema
  and examples. No code inside; built deterministically by `tools/build_rulebook.py`.
- `aicl/gateway.py`: one requester talking AICL to a bus of specialists (validate,
  deliver, collect replies and artifacts); `aicl/gemini.py`: shared Gemini text,
  image and SVG-image building blocks.
- `aicl/mcp_server.py` (`aicl-mcp`, `.mcp.json`): the gateway as an MCP server with
  `aicl_rulebook`, `aicl_capabilities`, `aicl_send`, `aicl_transcript`, `aicl_check`,
  so Claude (or any MCP client) can obtain images from another AI by speaking AICL.

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
