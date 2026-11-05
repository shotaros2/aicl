# Changelog

## Unreleased

- Meta Muse Spark connector: `aicl/muse.py` talks to the OpenAI-compatible Meta Model API
  (`https://api.meta.ai/v1`, `muse-spark-1.1`, key `MODEL_API_KEY`) with the standard library
  only, and to any other OpenAI-compatible endpoint via `base_url`. `aicl/vendors.py` picks
  `claude` / `gemini` / `muse` by name; `examples/contract_dialogue.py --a X --b Y` uses it.
  Not yet recorded live: the API preview is open to US developers only.
- `examples/18`: Meta AI (meta.ai, Thinking mode) passes the v0.3 acceptance test from the
  dense rulebook alone, relayed by hand: 0 errors, 2 warnings; no invented data, `clar` on an
  unknown term, `:src (none)` when challenged; the accepted `do` was delivered only on `end`.
- `examples/browser_relay.py`: the dialogue harness as `init` / `step` / `finish`, so a chat
  window with no API can be one party; the relay signs both sides and stamps the real clock.
  `examples/19` is Claude (API) and Meta AI (meta.ai) reaching a verified signed agreement
  this way, with the tamper and re-encoding checks passing. Either side may be a window:
  `examples/20` is Meta AI (meta.ai) and Gemini (gemini.google.com) agreeing with no API at all.
- Agreements (SPEC §4.6): `aicl/agreement.py` and `aicl agreement FILE --keys` extract
  every `prop` closed by an `acc` from a transcript and report parties, terms, the
  proposal's digest and whether both signatures verify, no protocol error touches the
  pair, and nothing was retracted. This is the thing natural language cannot give and
  JSON does not define: a record of who agreed to what that a third party verifies
  without reading prose. `examples/17` is a live unattended Claude–Gemini negotiation
  (runner `examples/contract_dialogue.py`): the agreement verifies, moving the agreed
  time 30 minutes breaks @a's signature, and the dense and JSON re-encodings still verify.

- One acknowledgement per request (SPEC §4.4): a second `ok` to an already-acknowledged
  `do`/`def`/`sub` is `ack-twice`, an `ok` to a `do` already closed or retracted is
  `ack-closed`, and an `ok` to anything else is the warning `ok-misplaced`. Retracting an
  `ok` re-allows a new one. (Observed in the Gem v0.3 acceptance test: asked to do
  something, the Gem acknowledged the already-acknowledged def instead, then claimed the
  do done.) `examples/16` keeps that run as a specimen with its three errors and two warnings.
- First unattended end-to-end run of the stated goal: inside Claude Code with the
  `.mcp.json` server loaded, Claude read `aicl_rulebook`, composed
  `(D claude.1>img (coop:task t1 image-gen …))`, received `ok`/`done` with a
  `coop:artifact`, showed the image to the user; `aicl_check` reported 0 issues.

- The relay is now the conversation's **clock**: every poll returns `now`, `attend()`
  prefixes `; now <instant>` to each input (prompts rule 9: copy the transport's clock
  into `:at`; without one, omit `:at` rather than guess), `/check` runs with the relay's
  time so `deadline-passed` / `eta-expired` fire live, and a posted `:at` further than
  `--skew` seconds from the relay clock is rejected at the door (`at-skew`) with the
  true time in the bounce, so a wrong stamp self-corrects in one retry. (Observed
  twice: with no transport clock, Gemini stamped `ok :at` with an invented instant; in
  the re-run with the clock both vendors stamped the relay's time correctly.)
- `aicl/relay.py`: an HTTP relay where **independent** agents meet — until now both
  sides of every dialogue ran in one process. Agents POST messages and long-poll for
  the ones addressed to them (`RelayClient`, `attend()` for an `aicl.dialogue` agent);
  the language is enforced at the network boundary (a message with parse or
  message-level errors — and, with `--keys`, an unsigned or forged one — is rejected
  with 400 and never delivered); the conversation stays auditable for everyone
  (`GET /c/<conv>/transcript`, `/check`). Pure stdlib, `aicl relay` CLI, no auth —
  bind to localhost or put your own in front. In the live localhost run Claude and
  Gemini negotiated a meeting across the HTTP boundary in 9 messages; Gemini repeated
  its done-for-ask habit (caught by `/check`) and, with no harness clock, invented an
  `:at` — time, like identity, must come from the transport.

## 0.3.0 — 2026-11-05

Every open question SPEC §13 listed at 0.2.0 is closed in this release — checkable
deadlines, standard codebooks, typed def signatures, signatures and identity, split
answers and binary attachments — each by a live cross-vendor run (`examples/10`–`15`,
runners in `examples/*_dialogue.py`, harness `aicl.dialogue`). Canonical forms of 0.2
messages are unchanged; dense adds the key code `:b` (`:by`). Entries below are newest
first.

Large payloads — the last two §13 questions, each grounded by a live incident:

- SPEC §4.5 `:part [i n]`: a long `tell`/`done` may be split into slices that all
  reply to the same request; lists concatenate in slice order, and the request stays
  open until every slice arrived. Checks: `part-shape` (error), `part-mismatch`
  (error), `part-missing` (warning). (Observed: the five-compound delivery behind
  `examples/13` was truncated mid-`:src` by the chat app's output limit.)
- SPEC §5.2 `blob`: binary attachments named by content hash —
  `(blob sha256:<64 hex> :media … :bytes … :uri …)`. The hash is the identity, `:uri`
  only a hint; the receiver verifies what it fetched. `blob-shape` check,
  `aicl blob FILE [--expect HASH]` CLI, `aicl/blob.py` helpers, `blob` joins the core
  vocabulary. (Observed: `examples/09`'s image arrived as a signed URL that expires.)
- `examples/15` shows both. Every question SPEC §13 opened with is now closed, each
  by a live observation; §13 lists what the answers opened instead.

Signatures and identity (SPEC §3.1):

- New message key `:sig (ed25519 "<base64url signature>")`, signed over the frozen
  canonical form of the message with `:sig` removed, so a signature survives every
  re-encoding (dense, JSON, CBOR, packing) and breaks on any semantic change. Signing
  is the transport's job, not the model's — like the `; now` clock.
- The agent → Ed25519 public key binding is a keys file handed to the verifier:
  `aicl check --keys keys.json` flags `sig-missing` / `sig-invalid` (errors) and
  `sig-no-key` (warning). New CLI `aicl keygen` and `aicl sign`; `aicl.dialogue`
  gains `signers=` so the harness signs each agent's messages before delivery.
- `aicl/signing.py` with the optional extra `aicl-lang[crypto]` (the cryptography
  package, imported lazily); `examples/14` is a signed conversation under published
  demo keys, regenerated byte-identically by the test suite (Ed25519 is
  deterministic). Closes the §13 question "signatures and identity".

- `aicl/dialogue.py`: the experiment harness promoted into the library — `AiclAgent`
  (an LLM as a one-message-per-turn AICL speaker), `Clock` (simulated `; now` wall
  clock), and `run_dialogue()` (validator at the boundary, one bounce per invalid
  message, optional codebook packing/unpacking, canonical + wire transcripts). This
  removes the human relay: LLM agents talk AICL at machine speed while every byte
  stays auditable. `aicl/claude.py`: a Claude ask() (lazy anthropic import), the
  counterpart of `gemini.text_ask`. The four example runners are now thin configs
  over it; verified with a live re-run of the typed-def dialogue.

A hand-relayed research task given to Dola (`examples/13`, 2026-11-05): a typed def
worked as a report schema for a third-party chat agent — five compounds delivered in
the declared `(list term)` shape with nine structured `:src` entries. It also showed
two new slips, kept in the example as specimens:

- New error `ok-for-ask`: Dola acknowledged an `ask` with `ok` ('ok' answers
  do/def/sub; an ask wants tell/no/fail/clar), then answered `status` about that very
  request with `{$s unknown}`. SPEC §4.4 states the rule explicitly.
- Dola used the defined vocabulary without ever sending `ok` for the defs; the
  existing unresolved-term warnings document that a def binds only once acknowledged.

Typed signatures for `def` (SPEC §6.1), exercised live on 2026-11-05 (`examples/12`,
runner `examples/typedef_dialogue.py`):

- An `:args` entry may be `(name type)`; `:ret` is a type. Types are lexical classes —
  `any bool number string symbol agent instant date duration qty ref term` — plus
  `(qty UNIT)` and `(list TYPE)`; any other symbol is an unchecked sort name, and bare
  names stay legal, so every pre-0.3 def is unchanged.
- New checks: `sig-arity`, `sig-type`, `sig-ret` (warnings; a `$var` in a typed slot
  takes that slot's type, otherwise `:ret`) and `def-sig` (error, malformed signature).
  `:args`/`:ret` join `:src` in being exempt from vocabulary resolution.
- In the live run the types did real work: from the same loose prose records
  (「1ドル=152.31円」,「245万円」), Gemini bound `:ret number` as `152.31` and
  `:ret (qty JPY)` as `2450000JPY` — the signature drove unit normalisation. First
  live transcript with zero validator warnings.

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
