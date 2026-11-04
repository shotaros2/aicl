# AICL — A Language for Agent-to-Agent Communication

**Version:** 0.2.0 (draft)  
**Status:** Request for Comments  
**License:** CC BY 4.0 (this specification), MIT (reference implementation)

---

## 0. Abstract

AICL is a small, formally specified language for communication between AI agents.
It replaces natural language in agent-to-agent exchanges with messages whose
**intent, referents, quantities, time, and certainty are explicit**, so that two
agents built by different vendors can exchange information with no ambiguity and
with a fraction of the tokens a polite natural-language exchange costs.

AICL is defined at the level of an **abstract data model** with three
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

AICL text is UTF-8. Whitespace separates tokens; `;` starts a comment to end of line.

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
| Reply ref | `^a.3` | "This message replies to message a.3". Parsers MUST also accept `^#a.3` (redundant sigil, unambiguous); the canonical form is `^a.3` |
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
| `:by instant` | no; meaningful on `do` and `prop` | Hard deadline: after this instant the result is worthless to the requester. Together with `:at` and `:eta` on the `ok` (§4.2) it makes overrun and expiry mechanically checkable |
| `:src term` | no; required on an answer to `why` | Evidence for the body: `(none)`, or a form naming the source with what was read from it, e.g. `(weathernews :uri "…" :at 2026-11-05T09:00+09:00 :kind hourly :value 14C :fetched-at 2026-11-04T10:00+09:00)`. A bare name (`:src jma`) is allowed but weak: it can be invented after the fact. Terms under `:src` are not subject to vocabulary resolution (§6) |
| `:why term` | with `no`, `rej`, `fail`, `retract` | Reason |
| `:code symbol` | with `fail` | Error code (§4.3) |
| `:sig term` | no; required when the sender's key is known to the verifier | `(ed25519 "<base64url signature>")` over the canonical form of the message with `:sig` removed (§3.1). Transport metadata, exempt from vocabulary resolution |
| `~conf` | no | Speaker's confidence in the body; absent = asserted without qualification |

Argument order inside the head is free; the parser classifies by sigil.

Act names are not reserved words. A form is a message only when it is well-formed as
one — it has a `#id` and a route. An act-named form without them, in particular one
nested inside a body such as `(done (ref #a.1))` in `:if (done (ref #a.1))`, is an
ordinary term, subject to vocabulary resolution (§6) like any other. At the top level
of a document or transmission every act-named form MUST be a well-formed message.
(Motivated by a live run on 2026-11-04: an agent naturally used `done` as a body
term in its third message; reserving 18 everyday words everywhere is a trap.)

### 3.1 Signatures and identity

`@agent` is a claim; a signature makes it checkable. The binding of an agent name to
an **Ed25519 public key** is exchanged out of band (a keys file `{"a": "<base64url
public key>", …}`, handed to the validator like pre-agreed terms), and every message
from a bound agent carries

```
:sig (ed25519 "<base64url signature>")
```

- **The payload is the canonical form** (§7) of the message with the `:sig` key
  removed. Canonical form is frozen, so a signature survives re-encoding — dense,
  JSON, CBOR, packing through a codebook, pretty-printing — and breaks on any
  semantic change: one argument, one keyword, one digit.
- **Signing is the transport's job, not the model's.** An LLM can no more compute
  Ed25519 than it can know the time; like `; now`, identity is supplied by the layer
  that delivers messages (`aicl sign`, or a harness such as `aicl.dialogue`).
- A verifier given keys flags: a message from a bound agent without a well-formed
  `:sig` (`sig-missing`, error), one whose signature does not verify (`sig-invalid`,
  error: forged, altered, or signed with another key), and one from an agent it has
  no key for (`sig-no-key`, warning).
- Terms under `:sig` are transport metadata, exempt from vocabulary resolution (§6).
- Key distribution, rotation and revocation are out of scope of the language;
  `aicl keygen` makes a keypair, and the keys file is the trust anchor.

---

## 4. Speech Acts (Core Vocabulary)

### 4.1 Acts

| Act | Direction | Body | Must be answered by |
|---|---|---|---|
| `ask` | request information | a proposition containing `$vars`, or a closed proposition (yes/no) | `tell` \| `no` \| `fail` \| `clar` |
| `tell` | assert information | proposition(s) | — (unsolicited `tell` needs no reply) |
| `do` | request an action | an action form | `ok` \| `no` \| `clar`, then `done` \| `fail` |
| `ok` | accept a `do`/`def`/`sub` | optional `:eta duration`; once it has elapsed without `done`/`fail`, the requester MAY treat the request as failed. An `ok` that carries `:eta` SHOULD also carry `:at` (`eta-unanchored` otherwise): `:at + :eta` is the promised finish, which a validator compares against the `do`'s `:by` (`eta-overrun`) and, given the current time, against the clock (`eta-expired`, `deadline-passed`) | — |
| `no` | refuse | `:why` required | — |
| `done` | action completed | result term(s), may be empty | — |
| `fail` | could not complete | `:code` and `:why` required | — |
| `prop` | propose (negotiation) | a proposal term | `acc` \| `rej` \| `prop` (counter) |
| `acc` | accept a proposal | — | — |
| `rej` | reject a proposal | `:why` required | — |
| `def` | define a term for this conversation | `(def … term :gloss (nl …) [:args […]] [:ret type] [:uri "…"])`; `:args` entries are `name` or `(name type)` and `:ret` is a type (§6.1) | `ok` \| `no` |
| `clar` | cannot interpret ^id | `(amb term [candidates…])` or `(unk term)` or `(parse "…")` | a repaired re-send with a new id |
| `why` | ask for justification | — (refers to ^id) | `tell` with `:src` carrying structured evidence, or `:src (none)` if there is none. Repeating the claim with a bare source name is not an answer |
| `sub` | subscribe to future `tell`s matching a pattern | a proposition with `$vars` | `ok` \| `no` |
| `unsub` | cancel a subscription | `^sub-id` | `ok` |
| `retract` | withdraw one of your own earlier messages | `^own-id`, `:why` required. Reopens whatever that message closed: retracting an `acc`/`rej` reopens the proposal, retracting `done`/`fail` reopens the `do`, retracting a `tell` reopens the `ask` it answered. Unilateral: it takes effect on receipt and cannot be refused (§4.4) | — |
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
- `ok` acknowledges a `do`/`def`/`sub`; it does not answer an `ask` (`ok-for-ask`).
  An `ask` is answered with `tell`/`no`/`fail`/`clar`, never acknowledged.
- `tell` MUST NOT contain `$vars` except as keys of a binding map (§4.2).
- An agent MUST NOT abbreviate, translate or otherwise vary a term except through an agreed codebook (§8.1).
- A decision is final until retracted: a second `acc`/`rej` on a proposal already closed is an error.
  To change your mind, send `retract` for your own decision, then the new one.
- A `retract` is unilateral and final: the counterpart MUST NOT answer it with `no` or `fail`,
  and a later reply to the retracted message is stale (`stale-reply`). Retracting an open `do`
  withdraws the request; whether started work is compensated is outside the language.
- Deadlines are message arithmetic, not trust: a `do` carrying `:by` plus an `ok` carrying
  `:at` and `:eta` lets any party (or a validator) flag a promise that overruns the deadline
  (`eta-overrun`) at the moment it is made, and an expired one (`deadline-passed`,
  `eta-expired`) given only the current time.
- An answer to `why` MUST carry `:src`. An agent that has no evidence says `:src (none)`;
  it MUST NOT name a source it did not consult.
- `(status (ref #id) $s)` MAY be asked about any open request; the answer binds `$s` to
  one of `pending done failed unknown`. An agent asked for status SHOULD then close the
  request with `done`/`fail` if it can; answering `done`/`failed` without ever closing
  the request is flagged (`status-unclosed`).
- A `def` sent to one agent binds only that pair; a `def` sent to `*` binds every agent in
  the conversation. A third party using a pair-scoped term gets `clar`.

### 4.5 Long answers: `:part`

A transport has a message-size limit the language does not see (observed: a five-compound
`tell` was truncated mid-`:src` by a chat app's output limit, `examples/13`'s run). A
`tell` or `done` MAY therefore be split:

```
(tell #b.1 @b>@a ^a.1 {$c [(compound g1 …) (compound g2 …)]} :part [1 2])
(tell #b.2 @b>@a ^a.1 {$c [(compound g3 …)]}                 :part [2 2])
```

- `:part [i n]` marks the i-th of n slices of one answer, all replying to the same
  request. Lists — a body list, or a list bound to a `$var` — concatenate in slice
  order; everything else must be identical across slices.
- The request stays open until all n slices have arrived: the answer MUST NOT be acted
  on incomplete. A validator flags a malformed `:part` (`part-shape`), conflicting
  slices — a different n, a repeated i (`part-mismatch`) — and, at the end of a
  conversation, slices that never arrived (`part-missing`).
- For a result too large even in slices, hand over a `blob` (§5.2) instead.

---

## 5. Core Logical Vocabulary

These heads are reserved and have fixed semantics in every AICL conversation.

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
| `(tokenizer name)`, `(codebook id)`, `(codebook id digest)` | Capability facts used to agree on packing (§8.1): `(tokenizer $t)` is answered with e.g. `{$t cl100k_base}`, `(codebook $id)` with the codebook's content hash. `(codebook aicl.sched.1 $digest)` asks whether the counterpart holds the **standard codebook** of that name (§8.2); the answer binds `$digest` to its content hash, or is `(none)` |
| `(status (ref #id) $s)` | Query the state of an open request; `$s` ∈ `pending done failed unknown` |
| `(blob sha256:<64 hex> [:media "…"] [:bytes n] [:uri "…"])` | A binary attachment named by its content hash (§5.2) |

### 5.1 Time intervals

Intervals written with `:from`/`:to` are half-open: `:from` is included, `:to` is not, so
`(busy @b :from 00:00 :to 06:00)` leaves 06:00 free. `:after`/`:before` are strict. A schema
that needs inclusive bounds says so explicitly (`:until`, or `(>= …)` in a condition).

### 5.2 Binary attachments: `blob`

Bytes do not travel in messages; their **name** does. A blob is identified by the SHA-256
of its content:

```
(done #b.3 @b>@a ^a.2 (coop:artifact a1 :type image :data
      (blob sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
            :media "image/png" :bytes 48213 :uri "https://cdn.example/x.png?sig=…")))
```

- **The hash is the identity.** `:uri` is only a hint about where a copy can currently
  be fetched; it may expire or lie (observed: a delivery arrived as a signed URL that
  expires, `examples/09`). A receiver MUST verify the hash of whatever it fetched
  before treating it as the attachment; two blobs with the same hash are the same
  bytes, wherever they came from.
- `:media` is the MIME type, `:bytes` the size — hints for deciding whether to fetch.
- A validator checks the shape (`blob-shape`: exactly one `sha256:<64 hex>` argument,
  a non-negative `:bytes`); fetching and hashing are the transport's job
  (`aicl blob FILE` makes the form for a local file and `--expect` verifies one).

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

A `def` addressed to one agent binds the sender and that agent once acknowledged with `ok`;
a `def` addressed to `*` binds every participant immediately. Validators resolve terms per
pair accordingly, and a third party that uses a pair-scoped term is told `clar`.

`def` is the only place where `nl` is *expected*. A linter SHOULD report the fraction of
message bodies that is `nl` text; a well-formed AICL conversation drives this toward zero.

### 6.1 Typed signatures

A `def` MAY type its positional slots and the value the term answers with:

```
(def #a.2 @a>@b fx-rate
     :gloss (nl en "units of quote currency per unit of base currency")
     :args [(base symbol) (quote symbol) (at instant)]
     :ret number)
```

- Each `:args` entry is a parameter name (untyped, as before 0.3) or `(name type)`.
- A **type** is one of the core type names — `any bool number string symbol agent instant
  date duration qty ref term` — or `(qty UNIT)` (a quantity in exactly that unit, e.g.
  `(qty USD)`), or `(list TYPE)`. Any other symbol in type position is a **sort name**:
  documentation (`transaction`, `id`), not checked.
- `:ret` is the type a `$var` binds to in the answer: a `$var` sitting in a typed
  argument slot takes that slot's type instead.
- Terms under `:args`/`:ret` are parameter names and types, not vocabulary; like `:src`
  they are exempt from resolution (§6).

The validator enforces a signature with warnings once the `def` is acknowledged:
`sig-arity` (more non-`$var` positional arguments than declared), `sig-type` (an argument
fails its declared type), `sig-ret` (a binding in the answering `tell` fails its expected
type), and the error `def-sig` for a malformed signature. Checking is lexical-class
checking — a `number` is a number literal, a `(qty USD)` is a quantity in USD — so it
needs no schema language beyond the table above.

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
shorter atoms. `aicl fmt` turns it back into the readable form; humans are not expected
to read it directly.

| Canonical | Dense | Rule |
|---|---|---|
| `ask tell do ok no done fail prop acc rej def clar why sub unsub end retract` | `A T D K N Z F P C R E Q W S U X B` | Speech act → one capital letter, only in head position |
| `#a.1 @a>@b` | `a.1>b` | When the id is `<sender>.<n>`, the id and route merge; `a.1>*` broadcasts. Otherwise `#id @from>@to` is kept. Decoders MUST also accept `a.1>@b` (a stray `@` before the destination is a common slip and is unambiguous) |
| `^a.1` | `^a.1` | unchanged |
| `:at :by :conv :code :gloss :if :args :src :eta :unit :ret :why` | `:a :b :c :e :g :i :r :s :t :u :v :w` | Head keys → one letter. Other keys unchanged |
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
without reintroducing ambiguity. It is a JSON table from **concept ids** (ordinary AICL
symbols) to alternative **surface forms**:

```json
{"name": "imagegen",
 "concepts": {"photorealistic": ["Photorealistic", "photo", "写実"],
              "tokyo":          ["Tokyo", "東京"]}}
```

Rules, all enforced by the reference implementation:

1. **Concept ids are the only canonical vocabulary.** Validation, hashing, logging and
   `def` all use concept ids. A surface form exists only on the wire; the receiver maps
   every form back to its concept id before interpreting anything (`aicl unpack`).
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

**Design guideline (from the read-back evaluation).** A form should be recognisable *as a
form*: CamelCase (`DeployStatus`), all-caps (`JMA`) or non-Latin (`東京`). Truncations that
read as ordinary English words (`deploy`, `roll`, `err`) are legal but small models tend to
pass them through unexpanded; the reference loader warns about them.

Given the codebook and the receiver's tokenizer, the sender replaces each concept id with
the form that costs the fewest tokens (ties: the id itself, then the shortest, then
lexicographic order), in symbol, head and keyword positions alike. The choice is
deterministic, and the receiver needs no tokenizer to decode. Core vocabulary, acts, head
keys, literals and ids are never packed.

```
(D u.1>g (GenerateImage :Scene (city Tokyo :Time night) :Style photo) :c img2)
```

### 8.2 Standard codebooks: sharing a table by id

Two agents from different vendors should not have to exchange a JSON table before they can
pack. A **standard codebook** is a codebook published in this repository under a versioned
id; holding the id is holding the table.

| id | domain | file | digest |
|---|---|---|---|
| `aicl.sched.1` | scheduling (examples 03/07/08 vocabulary) | `codebooks/scheduling.json` | `sha256:ce5a0e068cc7f8db` |
| `aicl.deploy.1` | deployment / operations (examples 02/10 vocabulary) | `codebooks/deployment.json` | `sha256:9a2788c5d6f9c34c` |

Rules:

1. **A standard codebook is immutable.** Its digest is frozen by a test; any change —
   adding a concept, adding a form — is a new codebook with a new id (`aicl.sched.2`).
   The id names the exact table, so citing the id commits to the digest above.
2. **Agree by id, verify by digest.** `(ask #a.1 @a>@b (codebook aicl.sched.1 $digest))`
   is answered with `{$digest sha256:…}` if the receiver holds the table, `(none)` if not.
   Each side compares the answer with the digest it holds (or the table above); packing
   starts only after digests match, together with the tokenizer handshake of §8.1 rule 4.
3. **The id is an ordinary symbol** (`aicl.sched.1` lexes as a symbol); concept ids inside
   the codebook resolve as vocabulary, the codebook id itself does not.

A domain gets a standard codebook only after its vocabulary has appeared in real
exchanges; a data-query codebook is deferred until a live exchange grounds one.

## 9. JSON Encoding

| AICL | JSON |
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

AICL:

```
(ask  #a.1 @a>@b (deploy-status build-4821 $s :finished-at $at))
(tell #b.1 @b>@a ^a.1 {$s finished $at 2026-11-04T08:50Z} :src ci-api)
(do   #a.2 @a>@b (rollout build-4821 :region eu-west-1)
      :if (< (error-rate build-4821 :window PT10M) 0.5%))
(ok   #b.2 @b>@a ^a.2 :at 2026-11-04T08:51Z :eta PT5M)
(tell #b.3 @b>@a (error-rate build-4821 0.3% :window PT10M) :src metrics)
(done #b.4 @b>@a ^a.2 (rollout build-4821 :region eu-west-1 :at 2026-11-04T09:04:12Z))
```

Every referent, time, threshold, and commitment is now explicit. The exchange is shorter in
characters; see the README for an honest token comparison (precision is not free on
tokenizers trained for English prose).

---

## 12. Conformance

An implementation is **AICL-conformant** if it:

1. Parses every text in `examples/` and reproduces its canonical form byte-for-byte.
2. Round-trips text → dense → text, text → JSON → text and text → CBOR → text without change in canonical form.
3. Rejects the malformed inputs in `tests/` with the specified error class.
4. Enforces the protocol rules in §4.4 when validating a conversation.

---

## 13. Open Questions

Resolved in 0.2.0, each from a live observation with a Gemini Gem and a Claude–Gemini
negotiation on 2026-11-04 (`examples/07`, `examples/08`): structured evidence and the
`why` rule (a source name was invented after the fact), `retract` (an `acc` was followed
by `rej` on the same proposal), half-open intervals (06:00 was proposed as free after
"busy until 06:00"), `status` and `:eta` (an accepted `do` was never closed), and the scope
of `def` (a pair-scoped term was honoured for a third party).

Resolved after 0.2.0, from a live Claude–Gemini deadline negotiation on 2026-11-04 run
under a harness-injected clock (`examples/10`): `:by` on `do`/`prop` and the checks
`eta-unanchored` / `eta-overrun` / `deadline-passed` / `eta-expired` (with no standard
deadline key the requester improvised `:by`, `:if (< now …)` and `:deadline` across runs;
with `:at` on the `ok` the overrun was pure message arithmetic); retract finality and
`stale-reply` (a performer answered a `retract` with `fail "cannot retract"`); act names
are not reserved words, §3 (the requester naturally wrote `(done (ref #id))` as a body
term in its third message and every encoder crashed).

Standard codebooks (§8.2) resolved the sharing-by-id question for the two domains with
live vocabulary (`aicl.sched.1`, `aicl.deploy.1`); further domains (data query, …) wait
for real exchanges to ground their vocabulary.

Typed signatures for `def` are §6.1: `(name type)` parameters, `(qty UNIT)` and
`(list TYPE)` types, and the checks `sig-arity` / `sig-type` / `sig-ret`, with bare
names and sort names staying legal and unchecked.

Signatures and identity are §3.1: `:sig (ed25519 …)` over the frozen canonical form,
keys bound out of band, checked by `aicl check --keys`. Long answers are §4.5
(`:part [i n]`, from the live truncation behind `examples/13`) and binary attachments
are §5.2 (`blob`, from the expiring signed URL in `examples/09`).

With that, every question this section opened with has been closed, each by a live
observation. The ones the answers opened:

- Key rotation and revocation for §3.1 (the keys file is a static trust anchor).
- Standard codebooks for more domains (§8.2), as real exchanges ground their vocabulary.
- Merging rules for `:part` slices beyond list concatenation (maps, single values).
- A registry so that standard codebooks and keys can be fetched by id, not shipped.

Feedback: open an issue in the repository.
