# Koine — A Language for Agent-to-Agent Communication

**Version:** 0.1.0 (draft)  
**Status:** Request for Comments  
**License:** CC BY 4.0 (this specification), MIT (reference implementation)

---

## 0. Abstract

Koine is a small, formally specified language for communication between AI agents.
It replaces natural language in agent-to-agent exchanges with messages whose
**intent, referents, quantities, time, and certainty are explicit**, so that two
agents built by different vendors can exchange information with no ambiguity and
with a fraction of the tokens a polite natural-language exchange costs.

Koine is defined at the level of an **abstract data model** with three
interchangeable concrete encodings:

| Encoding | Purpose | Example |
|---|---|---|
| **Text** | Canonical form; logs, humans reading over agents' shoulders | `(ask #a.1 @a>@b (temp tokyo $t :unit C))` |
| **Dense text** | What LLM agents actually exchange: same structure, fewer tokens (§8) | `(A a.1>b (temp tokyo $t :u C))` |
| **JSON** | Tooling, interop with MCP / A2A / JSON-RPC transports | `{"f":"ask","a":["#a.1", ...]}` |
| **CBOR** | Program-to-program wire format, signing, hashing | binary |

Every message has exactly one **canonical form** per encoding, so agents can hash,
sign, and compare messages without disagreement.

---

## 1. Design Principles

1. **Intent is explicit.** Every message starts with a *speech act* (`ask`, `tell`, `do`, `no`, …).
   There is no "could you perhaps…"; there is `do`.
2. **No pronouns, no anaphora.** Every message, agent, and object is referred to by an
   identifier. "It", "that one", "the earlier file" do not exist.
3. **Numbers carry units.** `25` is dimensionless. Temperature is `25C`. Money is `100USD`.
   An agent MUST NOT guess a unit.
4. **Time is absolute.** Instants carry a timezone offset. "Tomorrow" does not exist;
   relative time is expressed as a duration anchored to an identified instant.
5. **Uncertainty is numeric.** `~0.7` means the speaker assigns probability 0.7.
   No "probably", "I think", "likely".
6. **Scope is structural.** Negation, conjunction and quantifiers are parenthesised forms,
   so `(not (and a b))` and `(and (not a) b)` cannot be confused.
7. **Unknown words are illegal.** A term is either in the core vocabulary, namespaced to a
   published schema, or defined in-conversation with `def`. Otherwise the receiver MUST reply `clar`.
8. **Natural language is quarantined.** Free text is allowed only inside an `(nl lang "…")` form,
   so every ambiguous region of a message is visibly marked and can be measured.
9. **Every request is closed.** An `ask` is answered by `tell`, `no`, or `fail`; a `do` by `ok`/`no`
   and then `done`/`fail`. A conversation with an open request is incomplete.
10. **Minimal, extensible core.** The core defines speech acts, logic, and literals.
    Domain vocabulary lives in schemas and `def`s, not in this document.

---

## 2. Lexical Structure (Text Encoding)

Koine text is UTF-8. Whitespace separates tokens; `;` starts a comment to end of line.

| Token | Syntax | Meaning |
|---|---|---|
| Form | `( … )` | A compound term: head followed by arguments |
| List | `[ … ]` | Ordered sequence |
| Map | `{ k v k v … }` | Unordered key→value pairs |
| Symbol | `temp`, `schema:Person`, `tokyo` | Bare word; a predicate, constant, or namespaced term |
| Keyword | `:unit` | Names a keyword argument inside a form |
| Agent | `@alice` | An agent identifier |
| Route | `@alice>@bob`, `@alice>*` | From → to (`*` = broadcast) |
| Ref | `#a.3` | Reference to a message or object identifier |
| Reply ref | `^a.3` | "This message replies to message a.3" |
| Variable | `$t` | Unbound slot in a query |
| Confidence | `~0.85` | Speaker's probability for the enclosing form, in [0,1] |
| Number | `42`, `-3.5`, `6.02e23` | Dimensionless number |
| Quantity | `25C`, `3.5kg`, `100USD`, `30min`, `12%` | Number with unit (unit = letters, `%`, `/`, `^`) |
| Instant | `2026-11-04T09:00+09:00`, `2026-11-04T08:50:30Z` | ISO 8601 date-time **with offset**; seconds optional |
| Date | `2026-11-04` | ISO 8601 calendar date (not an instant) |
| Duration | `P1D`, `PT30M`, `P1DT2H` | ISO 8601 duration |
| String | `"text \"quoted\" \n"` | Opaque data; JSON escapes |
| Boolean / null | `true`, `false`, `null` | — |

Symbols match `[A-Za-z_][A-Za-z0-9_.:/-]*` or are one of the operators `= != < <= > >=`.
Agent/ref/var identifiers match `[A-Za-z0-9_][A-Za-z0-9_.:/-]*`.

---

## 3. Message Structure

```
(ACT #id @from>@to [^reply-to] body… [:key value]… [~conf])
```

| Part | Required | Meaning |
|---|---|---|
| `ACT` | yes | Speech act (§4) |
| `#id` | yes | Message id, unique per sender. Recommended: `#<sender>.<n>` with `n` increasing |
| `@from>@to` | yes | Route. `@to` may be `*` |
| `^id` | depends on act | The message being answered |
| body | depends on act | One or more terms |
| `:conv id` | no | Conversation/session id |
| `:at instant` | no | Sender's send time |
| `:src term` | no | Evidence or provenance for the body |
| `:why term` | with `no`, `rej`, `fail` | Reason |
| `:code symbol` | with `fail` | Error code (§4.3) |
| `~conf` | no | Speaker's confidence in the body; absent = asserted without qualification |

Argument order inside the head is free; the parser classifies by sigil.

---

## 4. Speech Acts (Core Vocabulary)

### 4.1 Acts

| Act | Direction | Body | Must be answered by |
|---|---|---|---|
| `ask` | request information | a proposition containing `$vars`, or a closed proposition (yes/no) | `tell` \| `no` \| `fail` \| `clar` |
| `tell` | assert information | proposition(s) | — (unsolicited `tell` needs no reply) |
| `do` | request an action | an action form | `ok` \| `no` \| `clar`, then `done` \| `fail` |
| `ok` | accept a `do`/`def`/`sub` | optional ETA `:eta duration` | — |
| `no` | refuse | `:why` required | — |
| `done` | action completed | result term(s), may be empty | — |
| `fail` | could not complete | `:code` and `:why` required | — |
| `prop` | propose (negotiation) | a proposal term | `acc` \| `rej` \| `prop` (counter) |
| `acc` | accept a proposal | — | — |
| `rej` | reject a proposal | `:why` required | — |
| `def` | define a term for this conversation | `(def … term :gloss (nl …) [:args […]] [:ret type] [:uri "…"])` | `ok` \| `no` |
| `clar` | cannot interpret ^id | `(amb term [candidates…])` or `(unk term)` or `(parse "…")` | a repaired re-send with a new id |
| `why` | ask for justification | — (refers to ^id) | `tell` with `:src` |
| `sub` | subscribe to future `tell`s matching a pattern | a proposition with `$vars` | `ok` \| `no` |
| `unsub` | cancel a subscription | `^sub-id` | `ok` |
| `end` | close the conversation | optional summary | — |

### 4.2 Answering an `ask`

The answer to an `ask` is a **binding map** from each `$var` in the question to its value.
The question is identified by `^id`, so its body is not repeated. Several solutions are a list
of maps. If no binding exists the answer is `(none)`.

```
(ask  #a.1 @a>@b (temp tokyo $t :unit C :at 2026-11-04T09:00+09:00))
(tell #b.1 @b>@a ^a.1 {$t 18.5C} ~0.95 :src jma)

(ask  #a.2 @a>@b (member $x team-7))
(tell #b.2 @b>@a ^a.2 [{$x @kim} {$x @lee}])
```

A closed (variable-free) `ask` is a yes/no question; the answer is `true` or `false`,
optionally with `~conf`. Bound values may be any term, including forms and quantities.
Binding maps are the only place a `$var` may appear in a `tell`.

### 4.3 Error codes for `fail`

`parse` · `unknown-term` · `unsupported` · `timeout` · `denied` · `not-found` · `conflict` · `limit` · `internal`

### 4.4 Protocol rules

- A message with `^id` MUST reference an id previously received from the counterpart in the same conversation.
- Message ids MUST NOT be reused by a sender within a conversation.
- A receiver that cannot interpret any part of a message MUST reply `clar`; it MUST NOT guess.
- An agent MUST NOT act on a `do` before sending `ok`.
- `tell` MUST NOT contain `$vars` except as keys of a binding map (§4.2).
- An agent MUST NOT abbreviate, translate or otherwise vary a term except through an agreed codebook (§8.1).

---

## 5. Core Logical Vocabulary

These heads are reserved and have fixed semantics in every Koine conversation.

| Form | Meaning |
|---|---|
| `(and p q …)`, `(or p q …)`, `(not p)` | Boolean connectives |
| `(if p q)` | Material implication |
| `(all $x p)`, `(some $x p)` | Universal / existential quantification over `$x` |
| `(= a b)`, `(!= a b)`, `(< a b)`, `(<= a b)`, `(> a b)`, `(>= a b)` | Comparison |
| `(in x set)` | Membership |
| `(count set $n)` | Cardinality |
| `(none)` | Empty answer |
| `(nl lang "text")` | Quarantined natural language, `lang` = BCP-47 tag |
| `(amb term [c1 c2 …])` | Term is ambiguous between candidates |
| `(unk term)` | Term is unknown |
| `(ref #id)` | Explicit reference to the content of an earlier message |
| `(tokenizer name)`, `(codebook id)` | Capability facts used to agree on packing (§8.1): `(tokenizer $t)` is answered with e.g. `{$t cl100k_base}`, `(codebook $id)` with the codebook's content hash |

Any other head is a **domain term** and must be resolvable (§6).

---

## 6. Vocabulary Resolution

A head or symbol is resolvable if one of the following holds, checked in order:

1. It is core (§4, §5).
2. It is namespaced (`ns:term`) and the namespace was bound to a URI via `def` or out-of-band configuration.
   Recommended well-known prefixes: `schema:` (schema.org), `qudt:` (units), `wd:` (Wikidata).
3. It was defined earlier in this conversation with `def` and acknowledged with `ok`.

```
(def  #a.2 @a>@b risk-score
      :gloss (nl en "probability in [0,1] that a transaction is fraudulent, per model v3")
      :args [transaction] :ret number)
(ok   #b.2 @b>@a ^a.2)
```

`def` is the only place where `nl` is *expected*. A linter SHOULD report the fraction of
message bodies that is `nl` text; a well-formed Koine conversation drives this toward zero.

---

## 7. Canonical Form

A canonical text form exists so that `sha256(canonical(msg))` is identical across implementations.

1. Head fields appear in order: act, `#id`, route, `^reply`, then body terms in original order,
   then keyword arguments sorted by key (byte order), then `~conf`.
2. Inside a form, keyword arguments are sorted by key; positional arguments keep their order.
3. Single ASCII space between tokens; no newlines; no comments.
4. Numbers: shortest round-trip decimal representation; `-0` becomes `0`; no leading `+`.
5. Confidence: as a decimal in [0,1], shortest round-trip, `1.0` is kept (it is distinct from absent).
6. Instants: `YYYY-MM-DDTHH:MM[:SS[.fff]]±HH:MM`; seconds are omitted when zero, fractional seconds
   are kept only when non-zero and without trailing zeros; a zero offset is written `Z`.
7. Strings: JSON escaping with the short escapes `\"`, `\\`, `\n`, `\r`, `\t`, `\b`, `\f` and `\uXXXX` for other control characters; non-ASCII characters are written literally.
8. Maps: keys sorted by their canonical text.

---

## 8. Dense Text Encoding

LLMs read and write tokens, not bytes, so the most efficient form for agent-to-agent
exchange is text tuned to BPE tokenizers, not binary. The dense encoding is a purely
lexical, bijective rewriting of the canonical text (§7): same parentheses, same order,
shorter atoms. `koine fmt` turns it back into the readable form; humans are not expected
to read it directly.

| Canonical | Dense | Rule |
|---|---|---|
| `ask tell do ok no done fail prop acc rej def clar why sub unsub end` | `A T D K N Z F P C R E Q W S U X` | Speech act → one capital letter, only in head position |
| `#a.1 @a>@b` | `a.1>b` | When the id is `<sender>.<n>`, the id and route merge; `a.1>*` broadcasts. Otherwise `#id @from>@to` is kept |
| `^a.1` | `^a.1` | unchanged |
| `:at :conv :code :gloss :if :args :src :eta :unit :ret :why` | `:a :c :e :g :i :r :s :t :u :v :w` | Head keys → one letter. Other keys unchanged |
| `2026-11-06T10:00+09:00`, `2026-11-04T09:04:12Z` | `20261106T1000+9`, `20261104T090412Z` | ISO 8601 basic format; offset mandatory, 1–2 digits = hours, 3–4 digits = HHMM; seconds only when non-zero; fractional seconds keep the extended form |
| everything else | unchanged | |

Reserved in the readable form as a consequence: single capital letters are not valid
domain heads, and the single-letter keywords above are not valid domain keys.

```
(P a.1>b (meeting :a 20261106T1000+9 :dur PT30M :with [@a @b]))
(R b.1>a ^a.1 :w (busy @b :from 20261106T0900+9 :to 20261106T1100+9))
(P b.2>a (meeting :a 20261106T1400+9 :dur PT30M :with [@a @b]))
(C a.2>b ^b.2)
```

Measured on `bench/`, the dense form uses 22 % fewer cl100k tokens than the canonical
text and about the same as a polite natural-language exchange carrying less information.
The remaining tokens are domain vocabulary; shortening those is what codebooks do.

### 8.1 Codebooks: tokenizer-aware surface forms

What a tokenizer finds cheap is accidental (`Tokyo` is one cl100k token, `tokyo` two,
`東京` three), and it differs between models. A **codebook** lets the sender exploit that
without reintroducing ambiguity. It is a JSON table from **concept ids** (ordinary Koine
symbols) to alternative **surface forms**:

```json
{"name": "imagegen",
 "concepts": {"photorealistic": ["Photorealistic", "photo", "写実"],
              "tokyo":          ["Tokyo", "東京"]}}
```

Rules, all enforced by the reference implementation:

1. **Concept ids are the only canonical vocabulary.** Validation, hashing, logging and
   `def` all use concept ids. A surface form exists only on the wire; the receiver maps
   every form back to its concept id before interpreting anything (`koine unpack`).
2. **Each form belongs to exactly one concept** and is never itself a concept id, a core
   term, a head key, a single ASCII letter, a sigil token, or anything that would lex as a
   number, quantity, instant, date or duration. Loading a codebook that breaks this fails.
3. **A form that is not in the codebook is an unknown term.** The receiver answers
   `clar (unk …)`; it never guesses that `photo` means `photorealistic`. Agents MUST NOT
   shorten or translate vocabulary on their own.
4. **The receiver's tokenizer is agreed, never assumed.** Before packing, the sender asks
   `(ask #a.1 @a>@b (tokenizer $t))` and `(ask #a.2 @a>@b (codebook $id))`; the receiver
   answers with its tokenizer name and the codebook's content hash (`sha256:…`). Until both
   match, messages are sent with concept ids.

Given the codebook and the receiver's tokenizer, the sender replaces each concept id with
the form that costs the fewest tokens (ties: the id itself, then the shortest, then
lexicographic order), in symbol, head and keyword positions alike. The choice is
deterministic, and the receiver needs no tokenizer to decode. Core vocabulary, acts, head
keys, literals and ids are never packed.

```
(D u.1>g (GenerateImage :Scene (city Tokyo :Time night) :Style photo) :c img2)
```

## 9. JSON Encoding

| Koine | JSON |
|---|---|
| form | `{"f": head, "a": [args…], "k": {key: value…}, "c": conf}` (`k`, `c` omitted when empty/absent) |
| list | JSON array |
| map | `{"map": [[k, v], …]}` |
| symbol | `"temp"` |
| keyword (as value) | `":unit"` |
| agent / route / ref / reply / var | `"@a"`, `"@a>@b"`, `"#a.1"`, `"^a.1"`, `"$t"` |
| number | JSON number |
| quantity | `{"q": 25, "u": "C"}` |
| instant / date / duration | `{"t": "2026-11-04T09:00:00+09:00"}`, `{"d": "2026-11-04"}`, `{"dur": "PT30M"}` |
| string | `{"s": "text"}` |
| true / false / null | JSON true / false / null |

Bare JSON strings are therefore always symbols or sigil atoms, never free text. Canonical JSON:
sorted object keys, no whitespace, UTF-8.

---

## 10. CBOR Encoding

The JSON model is mapped to CBOR with the standard JSON↔CBOR correspondence (RFC 8949 §6).
Canonical CBOR follows RFC 8949 §4.2 (shortest integer encoding, definite lengths, sorted map keys).

---

## 11. Worked Example

Natural-language exchange (what agents do today):

> A: Hi! Could you check whether the deploy of build 4821 finished, and if so, roll it out to the EU region — but only if error rate is under half a percent? Thanks!  
> B: Sure! It did finish about ten minutes ago. Error rate looks fine (0.3%), so I'll go ahead and roll it out to EU. Should take around 5 minutes.  
> B: Done — EU rollout complete.

Ambiguities: "it" (the build? the deploy?), "about ten minutes ago" (relative to when?), "looks fine" (what threshold, measured how?), "around 5 minutes" (ETA or duration?), "EU" (which region id?).

Koine:

```
(ask  #a.1 @a>@b (deploy-status build-4821 $s :finished-at $at))
(tell #b.1 @b>@a ^a.1 {$s finished $at 2026-11-04T08:50Z} :src ci-api)
(do   #a.2 @a>@b (rollout build-4821 :region eu-west-1)
      :if (< (error-rate build-4821 :window PT10M) 0.5%))
(ok   #b.2 @b>@a ^a.2 :eta PT5M)
(tell #b.3 @b>@a (error-rate build-4821 0.3% :window PT10M) :src metrics)
(done #b.4 @b>@a ^a.2 (rollout build-4821 :region eu-west-1 :at 2026-11-04T09:04:12Z))
```

Every referent, time, threshold, and commitment is now explicit. The exchange is shorter in
characters; see the README for an honest token comparison (precision is not free on
tokenizers trained for English prose).

---

## 12. Conformance

An implementation is **Koine-conformant** if it:

1. Parses every text in `examples/` and reproduces its canonical form byte-for-byte.
2. Round-trips text → dense → text, text → JSON → text and text → CBOR → text without change in canonical form.
3. Rejects the malformed inputs in `tests/` with the specified error class.
4. Enforces the protocol rules in §4.4 when validating a conversation.

---

## 13. Open Questions (for v0.2)

- Standard published codebooks per domain (scheduling, deployment, data query), so
  agents from different vendors can share one by id instead of exchanging tables.
- Typed signatures for `def` (`:args`/`:ret` currently use symbols only).
- A standard set of domain schemas (scheduling, data query, tool invocation).
- Signatures and identity (`@agent` → public key binding).
- Streaming / partial `tell` for long results.
- Binary attachments by content hash.

Feedback: open an issue in the repository.
