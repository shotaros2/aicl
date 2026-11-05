# AICL — AI Common Language

**A common language for AI agents, the way English is for people: one tongue any agent
can learn, with no ambiguity.**
Specification + zero-dependency reference implementation. Draft v0.1.0.
[日本語の README はこちら](README.ja.md)

```
(ask  #a.1 @a>@b (temp tokyo $t :unit C :at 2026-11-05T09:00+09:00))
(tell #b.1 @b>@a ^a.1 {$t 18.5C} ~0.9 :src jma)
```

## The problem

When two AI agents cooperate today they write each other English (or Japanese) prose:

> "Could you check whether **it** finished and, if so, roll it out to **EU**, but only if the error rate is **fine**? **Should take about 5 minutes.**"

Every bold span is a guess the receiver has to make: which object, which region id, what
threshold, is that an ETA or a duration, measured when. Natural language is also padded with
greetings, hedges and thanks that cost tokens and carry no information, and nothing about the
exchange is machine-checkable: no one can verify that every request got an answer.

## What AICL does

AICL is a small formal message language with four interchangeable encodings
(readable text, dense text for LLM-to-LLM exchange, JSON, deterministic CBOR) and one
canonical form that can be hashed and signed.
Its design rules are the whole point:

| Rule | In practice |
|---|---|
| Intent is explicit | Every message opens with a speech act: `ask tell do ok no done fail prop acc rej def clar why sub unsub end` |
| No pronouns | Everything is referred to by id: `#a.3`, `@bob`, `(ref #b.2)` |
| Numbers carry units | `18.5C`, `100USD`, `0.5%`. A bare `42` is dimensionless |
| Time is absolute | `2026-11-05T09:00+09:00`. "Tomorrow" does not exist |
| Uncertainty is numeric | `~0.8` on any form. No "probably" |
| Scope is structural | `(not (and a b))` cannot be misread |
| Unknown words are illegal | A receiver that meets a term it does not know **must** answer `clar`, never guess. Terms are introduced in-band with `def` |
| Natural language is quarantined | Free text only inside `(nl en "…")`, so the ambiguous part of any message is visible and measurable |
| Every request is closed | An `ask` ends with `tell`/`no`/`fail`; a `do` with `ok` then `done`/`fail`. The validator checks this |

The full specification is in [SPEC.md](SPEC.md) (16 pages, CC BY 4.0); the grammar in
[grammar/aicl.ebnf](grammar/aicl.ebnf).

### What live experiments changed (0.2)

Version 0.2 adds nothing that was designed at a desk. Each rule below exists because a
Gemini agent given only the rulebook, or a Claude–Gemini negotiation relayed by hand
([examples/07](examples/07_cross_vendor_negotiation.aicl)), broke the previous version:

- **`retract`**: an agent accepted a meeting, learned a constraint, and then rejected the
  same proposal. Decisions are now final until explicitly withdrawn with `retract :why …`.
- **Evidence or `(none)`**: asked *why* it believed a value it had made up, an agent invented
  a source. Answers to `why` must now carry structured evidence (`:src (weathernews :uri … :kind hourly :value 14C)`) or admit `(none)`.
- **`status` and `:eta`**: an accepted `do` was never closed. Any open request can be queried
  with `(status (ref #id) $s)`, and an `ok` may promise an `:eta` after which the requester gives up.
- **Half-open intervals**: "busy until 06:00" was answered with a 06:00 slot. `:to` now
  excludes its endpoint; `:after` is strict.
- **`def` scope**: a term defined between two agents was used by a third. A `def` binds
  the pair it was sent to; a `def` to `*` binds everyone.

[examples/08](examples/08_retract_and_status.aicl) shows all of them in one conversation.

### What live experiments changed (0.3)

Version 0.3 closes every question §13 had left open, again one live run at a time —
first Claude and Gemini negotiating under a hard deadline with a harness-injected clock
([examples/10](examples/10_deadline_negotiation.aicl)):

- **Checkable deadlines**: with no standard key, the requester improvised `:by`,
  `:if (< now …)` and `:deadline` on successive runs. A `do` may now carry `:by` (hard
  deadline), an `ok` that promises `:eta` should anchor it with `:at`, and the validator
  flags a promise that overruns the deadline (`eta-overrun`) with no clock at all, plus
  expired requests given `--now`.
- **`retract` is unilateral**: the performer answered a retraction with
  `fail "cannot retract"`. A retract takes effect on receipt; replying to a retracted
  message is flagged (`stale-reply`).
- **Act names are not reserved words**: the requester naturally wrote `(done (ref #a.1))`
  *inside* a body, and every encoder crashed. A form is a message only where a message
  belongs: at the top level, with `#id` and route.

A packed cross-vendor run ([examples/11](examples/11_standard_codebook.aicl)) grounded
**standard codebooks** (SPEC §8.2): immutable, versioned tables published in
[codebooks/](codebooks/) (`aicl.sched.1`, `aicl.deploy.1`) that two agents agree on
in-band by id and digest — `(ask … (codebook aicl.sched.1 $digest))` — instead of
exchanging JSON. In the live run the handshake succeeded, both sides packed with zero
violations, and the wire cost measured 370 tokens against 480 readable. It also exposed
a new slip, a status answered `done` with no real `done` ever sent, now flagged as
`status-unclosed`.

Typed `def` signatures ([examples/12](examples/12_typed_def.aicl), SPEC §6.1) let a
definition fix the types of a term's arguments and of the answer: `:args [(base symbol)
(quote symbol)] :ret (qty JPY)`. In the live run the declared type did the work of a
schema: from the same loose prose records, Gemini bound `:ret number` as `152.31` and
`:ret (qty JPY)` as `2450000JPY`, converting 「245万円」 into the declared unit — the
first live transcript with zero validator warnings.

Identity is message arithmetic too ([examples/14](examples/14_signed_identity.aicl),
SPEC §3.1): a message may carry `:sig (ed25519 …)` over its frozen canonical form, the
agent → public-key binding is a keys file, and `aicl check --keys` flags a forged,
altered or unsigned message. Signing is the transport's job, not the model's — an LLM
can no more compute Ed25519 than it can know the time.

Large payloads stay out of band ([examples/15](examples/15_blob_and_part.aicl)): a long
answer is sliced with `:part [i n]` and the request stays open until every slice arrived
(a live delivery was once truncated by a chat app's output limit), and bytes travel as
`(blob sha256:… :uri …)` — the hash is the identity, the URI only a hint (a live image
once arrived as a signed URL that expires).

A chat agent given only the skill zip completed a research task against a typed report
schema ([examples/13](examples/13_dola_research_task.aicl)) — and contributed the
`ok-for-ask` error by acknowledging an `ask` with `ok`. The experiment harness behind
all of these runs is in the library (`aicl.dialogue`): LLM agents exchanging AICL at
machine speed, the validator at the boundary, every byte on the record. And the
boundary can be a network: `aicl relay` hosts conversations over HTTP, rejecting an
invalid (or, given keys, unsigned) message at the door and serving the transcript to
any auditor; [examples/relay_dialogue.py](examples/relay_dialogue.py) is Claude and
Gemini negotiating across it from independent connections.

### A complete exchange

```
(ask  #a.1 @a>@b (deploy-status build-4821 $s :finished-at $at))
(tell #b.1 @b>@a ^a.1 {$s finished $at 2026-11-04T08:50Z} :src ci-api)
(do   #a.2 @a>@b (rollout build-4821 :region eu-west-1)
      :if (< (error-rate build-4821 :window PT10M) 0.5%))
(ok   #b.2 @b>@a ^a.2 :at 2026-11-04T08:51Z :eta PT5M)
(tell #b.3 @b>@a (error-rate build-4821 0.3% :window PT10M) :src metrics)
(done #b.4 @b>@a ^a.2 (rollout build-4821 :region eu-west-1 :at 2026-11-04T09:04:12Z))
```

More in [examples/](examples/): negotiation, in-band term definition and clarification,
subscriptions, broadcast discovery, coded failures.

### The dense form: what agents actually send

LLMs consume tokens, not bytes, so "binary" would make LLM-to-LLM traffic *more*
expensive (it would be base64 in the prompt). Instead, AICL has a **dense text encoding**
(SPEC §8): the same structure with one-letter speech acts, merged headers, one-letter
core keys and ISO-basic timestamps. It is bijective with the readable form, so
`aicl fmt` always recovers the readable version for audit and debugging.

```
(P a.1>b (meeting :a 20261106T1000+9 :dur PT30M :with [@a @b]))
(R b.1>a ^a.1 :w (busy @b :from 20261106T0900+9 :to 20261106T1100+9))
(P b.2>a (meeting :a 20261106T1400+9 :dur PT30M :with [@a @b]))
(C a.2>b ^b.2)
```

### Codebooks: cheaper words without ambiguity

What a tokenizer finds cheap is accidental: `Tokyo` is one cl100k token, `tokyo` two,
`東京` three. A **codebook** (SPEC §8.1) is a shared table from concept ids to allowed
surface forms. The sender picks, per concept, the form that costs the fewest tokens on
the *receiver's* tokenizer; the receiver maps every form back to the concept id before
it reads anything. Four rules keep this exactly as unambiguous as the dense form's
`A` = `ask`:

1. Only concept ids are canonical: validation, hashing and `def` never see a surface form.
2. Each form belongs to exactly one concept (the loader rejects any table that breaks this).
3. A form not in the codebook is an unknown term → `clar`, never a guess. Agents must not
   shorten or translate vocabulary on their own.
4. The receiver's tokenizer and codebook id are agreed in-band (`(tokenizer $t)`, `(codebook $id)`), never assumed.

```bash
aicl codebook codebooks/imagegen.json --tokenizer cl100k_base   # validate, show chosen forms
aicl pack   msg.kd --codebook codebooks/imagegen.json --tokenizer cl100k_base
aicl unpack msg.kd --codebook codebooks/imagegen.json           # back to concept ids
aicl check  msg.kd --codebook codebooks/imagegen.json           # concepts count as known terms
```

## Honest numbers: precision is not free

`bench/compare.py` compares realistic natural-language agent dialogues with the same
information in AICL (cl100k_base tokenizer, which GPT-4-class and many open models use).
All columns are tokens; "packed" uses `codebooks/bench.json`:

| case | NL | readable | ratio | dense | ratio | packed | ratio |
|---|---|---|---|---|---|---|---|
| weather | 138 | 128 | 0.93 | 98 | 0.71 | 94 | 0.68 |
| clarify | 188 | 239 | 1.27 | 190 | 1.01 | 186 | 0.99 |
| deploy | 150 | 201 | 1.34 | 164 | 1.09 | 162 | 1.08 |
| scheduling | 124 | 211 | 1.70 | 158 | 1.27 | 158 | 1.27 |
| **total** | **600** | **779** | **1.30** | **610** | **1.02** | **600** | **1.00** |

The readable form costs about 30 % more tokens than polite English, because BPE
vocabularies are tuned for prose. The dense form removes 22 % of that; a codebook of
*safe* forms (see the eval below) takes a little more and lands **at parity with natural
language while carrying strictly more information** (exact instants with time zones,
ids, thresholds, provenance) and zero ambiguity. Truncation forms would save another
1–2 %, but small models misread them, so the example codebook no longer uses any. In characters, every AICL form is far shorter. The scheduling case does not
move because its vocabulary was already one token per word; the remaining cost there is
the four time-zoned instants, which natural language simply leaves out.

Re-run the benchmark with your own model's tokenizer (`--tokenizer o200k_base`, or any
`tiktoken` encoding) before drawing conclusions for it.

### Does the model still read it correctly?

The library decodes every encoding perfectly; the open question is whether a *language
model* does, especially for packed messages that mix scripts. `evals/readback.py` asks a
model to write the canonical form of every example message in each encoding, parses and
canonicalises the answer, and reports accuracy and tokens per encoding:

```bash
python evals/readback.py --dry-run                      # 69 messages x 4 encodings, no API calls
python evals/readback.py --provider anthropic --model claude-opus-5-5 --out evals/results/opus-5-5.json
python evals/readback.py --provider gemini --model gemini-3.8-flash --out evals/results/gemini-3.8-flash.json
```

Providers: `anthropic` (`pip install anthropic`, `ANTHROPIC_API_KEY`) and `gemini`
(`pip install google-genai`, `GEMINI_API_KEY`). Any other model needs one function of
the form `ask(system, user) -> str` added to `PROVIDERS`.

A token saving that lowers read-back accuracy is a loss; adopt a codebook for a model only
after this eval passes for it. Results so far (`evals/results/`, first 10 messages,
`gemini-3.5-flash-lite`, the smallest model available to us):

| encoding | accuracy | what failed |
|---|---|---|
| readable | 90 % | one term "corrected" to a codebook form |
| dense | **100 %** | — |
| packed | 60 % → 80 % → 90 % | English truncations (`deploy`, `roll`, `err`) left unexpanded; last failure is one key code (`:u`) |
| packed-chars | 80 % → 90 % → 90 % | same |

The first arrow is the effect of presenting the codebook form→concept and adding worked
examples to the eval prompt; the second is removing truncation forms from the codebook.
With forms that look like forms, the only remaining miss is a dense key code, and the
vocabulary errors are gone. Two conclusions: **the dense form is safe even for a small
model**, and **codebook forms must look like forms** (CamelCase, all-caps, non-Latin):
truncations that read as real words are the failure mode, so the example codebooks no
longer contain any and the loader warns about them. Results for larger models are welcome.

## Install and use

```bash
pip install aicl-lang       # from PyPI: https://pypi.org/project/aicl-lang/
pip install -e .            # or from a checkout
```

```bash
aicl fmt    examples/02_deploy.aicl        # canonical single-line form (also decodes dense input)
aicl dense  examples/02_deploy.aicl        # dense text encoding for LLM-to-LLM exchange
aicl pretty examples/02_deploy.aicl        # readable layout
aicl json   examples/02_deploy.aicl        # JSON encoding
aicl cbor   examples/01_weather.aicl -o m.cbor
aicl hash   examples/02_deploy.aicl        # sha256 of canonical form, per message
aicl check  examples/02_deploy.aicl --known deploy-status --known rollout --known error-rate
aicl stats  examples/05_subscription.aicl  # size, tokens, nl ratio
```

```python
import aicl

msgs = aicl.parse_messages(open("examples/02_deploy.aicl").read())
for issue in aicl.validate_conversation(msgs, known_terms=["deploy-status", "rollout", "error-rate"]):
    print(issue)                             # protocol violations, open requests, unresolved terms

m = msgs[1]
print(m.act, m.sender, m.receiver, m.reply)  # tell b a a.1
print(aicl.to_text(m.to_form()))            # canonical text
print(aicl.to_dense(m.to_form()))           # dense text
print(aicl.to_json_text(m.to_form()))       # canonical JSON
print(aicl.digest(m.to_form()))             # sha256

from aicl.build import msg, form, q
reply = msg("tell", "b.9", "b", "a", aicl.KMap([(aicl.Var("t"), q(18.5, "C"))]), reply="a.1", conf=0.9)
```

## Cooperation: specialists working together

AIs have different strengths. The cooperation layer (`aicl/coop.py`,
[schemas/cooperation.md](schemas/cooperation.md)) lets an image agent, a video agent and a
code agent work on one goal, speaking only AICL:

- **Specialists** announce `(coop:capability image-gen :agent @img)`, accept
  `(coop:task …)` with `ok`, and return `(coop:artifact …)` with `done`.
- A **hub** keeps the registry, turns the requester's goal into a `(coop:plan …)`, delegates
  tasks in dependency order and passes each artifact to the next task in full, never as
  "the previous result".
- The **bus** validates every message; a specialist's `fail` reaches the requester as `fail`
  with `:why (ref #…)`, never as a silent retry.

```
(do   #user.1 @user>@hub (coop:goal (nl ja "東京の夜景の10秒動画を作って、それを埋め込んだWebページを作って")))
(tell #hub.2 @hub>@user (coop:plan [(coop:task t1 image-gen …) (coop:task t2 video-gen :in {keyframe (coop:from t1) …}) (coop:task t3 code-gen …)]))
(do   #hub.3 @hub>@img (coop:task t1 image-gen :in {prompt "Tokyo skyline at night" width 1920px height 1080px}))
(done #img.3 @img>@hub ^hub.3 (coop:artifact img-974186 :type image :task t1 :uri "file://out/img-974186.png"))
(do   #hub.4 @hub>@vid (coop:task t2 video-gen :in {keyframe (coop:artifact img-974186 …) duration 10s}))
…
(done #hub.6 @hub>@user ^user.1 [(coop:artifact img-974186 …) (coop:artifact vid-… :type video …) (coop:artifact page-1 :type code :content "<!doctype html>…")])
```

`python examples/cooperation_demo.py` runs this offline with stub specialists: 16 messages,
0 protocol errors, natural language only inside the user's goal (nl ratio 2 %). Swap the
stub functions for real APIs, or use `LLMAgent` for a model-backed specialist and
`LLMPlanner` for a model-backed hub, and nothing else changes.

`python examples/cooperation_gemini.py` does exactly that with Gemini in three roles
(`GEMINI_API_KEY` required): the hub's planner writes the plan in AICL, the image
specialist calls a Gemini image model and returns the PNG as an artifact, and the code
specialist *is* Gemini speaking dense AICL, answering the task with `K` and `Z` messages
that the bus validates before accepting. Output lands in `out/` (transcript, image, page).
On the free tier Gemini's image models are not available (a consumer Gemini subscription
does not change API quotas), so by default the text model draws the image as SVG;
`--image-model gemini-nano-banana-2.1` uses a real image model once API billing is on. Live runs with `gemini-3.5-flash-lite` as planner
and code agent: the plan, two dependent tasks and both artifacts reach the requester in
12 messages with 0 protocol errors. Getting there taught three things, all now in the code:
the harness, not the model, owns message ids (it tells the model its next id and reply
header as an AICL comment, and renumbers if needed); a malformed reply gets one correction
turn with the validator's verdict before it becomes `fail :code parse`; and two redundant-sigil
slips a small model makes (`a.1>@b`, `^#a.1`) are accepted on input because they cannot
change meaning, while anything ambiguous is still rejected.

## What only AICL can do: an agreement a third party can verify

Two agents can cooperate in plain English, in JSON, over MCP or A2A. What none of those
gives you is a record of *who agreed to what* that someone else can check without reading
prose: natural language has no canonical form to sign, and JSON has no notion of "an
accepted proposal". AICL has both (SPEC §4.6). In a live, unattended run
([examples/17](examples/17_signed_agreement.aicl)) Claude and Gemini negotiated a meeting
with every message signed by the transport; then:

```
$ aicl agreement examples/17_signed_agreement.aicl --keys examples/17_keys.json --known meeting --known busy
(agreement :between [@a @b] :terms (meeting :at 2026-11-12T10:30+09:00 :dur PT45M :with [@a @b])
           :proposed (ref #a.2) :accepted (ref #b.2) :digest "sha256:ab48…" :signed {@a true @b true} :verified true)
```

Move the agreed time by one minute in the transcript and `:signed {@a false …}`; convert the
transcript to dense text or JSON and it still verifies, because the signature is over the
canonical form, not the bytes. Runner: `python examples/contract_dialogue.py`.

The runner takes `--a` / `--b` to choose the vendors: `claude`, `gemini`, or `muse`
(Meta's Muse Spark over the OpenAI-compatible Meta Model API, key `MODEL_API_KEY`;
the preview is open to US developers only, so that pairing is wired but not yet recorded live).
`aicl/muse.py` is a dependency-free client for any OpenAI-compatible endpoint.

Muse has been tested the other way: [examples/18](examples/18_muse_v03_acceptance.aicl) is
Meta AI on meta.ai (Thinking mode, no API, no system prompt) given the dense rulebook as its
first chat message and relayed one message per turn. `aicl check`: 0 errors, 2 warnings. It
refused to invent a temperature (`no :why (unk data)`), answered an undefined term with
`clar (unk …)`, kept its ids, and admitted `:src (none)` when challenged; the one thing it did
not do was deliver the accepted `do` until the conversation was being ended.

And the agreement itself does not need the API either. [examples/19](examples/19_browser_relay_agreement.aicl)
is Claude (API) and Meta AI (the meta.ai chat window) negotiating the same meeting with
`examples/browser_relay.py`: the dialogue harness split into `init` / `step` / `finish` so that
whoever holds the browser pastes each message and feeds the reply back. The relay signs each
party's messages with that party's key and stamps the real clock; the models never see a key.
`aicl agreement examples/19_browser_relay_agreement.aicl --keys examples/19_keys.json` verifies
it; the tamper and re-encoding checks behave exactly as in example 17.

Both parties can be windows. [examples/20](examples/20_two_windows_agreement.aicl) is Meta AI
(meta.ai) and Gemini (gemini.google.com, a plain chat) reaching the same verified agreement with
`init --a meta-ai --b gemini-web` and not one API key: the relay carries each message from one
window to the other, signs it with that party's key, and stamps the clock.

## Let Claude fetch images from another AI on its own

The end goal of the cooperation layer: a model that needs something it cannot do
(an image, say) talks AICL to a specialist, gets the artifact, and shows it to the
user, with no human in the loop. `aicl/mcp_server.py` exposes the gateway as an
[MCP](https://modelcontextprotocol.io) server with five tools: `aicl_rulebook` (learn the
language), `aicl_capabilities`, `aicl_send` (deliver AICL, get AICL replies and image
artifacts back), `aicl_transcript` and `aicl_check`.

```bash
pip install "aicl-lang[mcp]"        # mcp SDK + google-genai; GEMINI_API_KEY in .env
```

Claude Code picks the server up from the repository's `.mcp.json`; for Claude Desktop add
`{"mcpServers": {"aicl": {"command": "python", "args": ["-m", "aicl.mcp_server"], "cwd": "<repo>"}}}`
to its config. Then ask Claude for a picture: it calls `aicl_rulebook`, composes
`(D claude.1>img (coop:task t1 image-gen :in {prompt "…"}))`, receives `(K …)` and
`(Z … (coop:artifact …))` from the image agent, and the image comes back as tool output.
`AICL_IMAGE_MODEL=svg` (default) draws with the text model on the free tier;
`AICL_IMAGE_MODEL=gemini-nano-banana-2.1` uses a real image model once API billing is on.

## Make an LLM speak AICL

[prompts/system_prompt.md](prompts/system_prompt.md) is a ~700-token system prompt that
teaches any instruction-following model the readable language;
[prompts/system_prompt_dense.md](prompts/system_prompt_dense.md) teaches the dense form,
which is what two LLM agents should use with each other. `examples/llm_dialogue.py` runs two
Claude instances negotiating a meeting in AICL, with every message parsed and validated
at the boundary before it is delivered:

```bash
pip install anthropic
python examples/llm_dialogue.py
```

`examples/two_agents_demo.py` does the same with rule-based agents and no network.

### Hand the folder to your own agent

The repository is self-describing for agents that read a project folder:

- `AGENTS.md` (Codex, Cursor and most general agents) and `CLAUDE.md` (Claude Code)
  tell the agent to load the system prompt and validate every message with `aicl check`.
- `SKILL.md` makes the folder an [Agent Skill](https://github.com/anthropics/skills):
  copy it to `.claude/skills/aicl/` (or your framework's skills directory) and the
  agent loads AICL only when it talks to another agent. For chat apps that take a skill upload (Dola, Claude web),
  use `rulebook/aicl-skill.zip`: a code-free skill with the rulebook inline.

Two agents that have both read this folder can talk to each other in AICL with no
further setup; the validator is the referee.

If you only want to hand over the language (no code), give the agent the
[rulebook/](rulebook/) folder: both language references, the spec, the example codebooks
and the worked conversations, with a bilingual index saying which file is for what. It is
generated by `python tools/build_rulebook.py` and checked by the test suite, so it never
drifts from the sources.

## Repository layout

```
SPEC.md                 the language (normative)
grammar/aicl.ebnf      text encoding grammar
aicl/                  reference implementation (Python ≥ 3.11, no dependencies)
  lexer.py parser.py    text → terms
  printer.py            canonical + pretty text, sha256 digest
  dense.py              dense text encoding (tokenizer-tuned, bijective with canonical)
  codebook.py           tokenizer-aware codebooks: pack / unpack with the ambiguity rules
  coop.py               cooperation layer: bus, specialists, hub, planners
schemas/                published vocabularies (cooperation)
codebooks/              example codebooks (bench, imagegen)
  json_codec.py         JSON encoding
  cbor_codec.py         deterministic CBOR (RFC 8949 §4.2)
  validate.py           message + conversation validator, nl ratio
  cli.py                `aicl` command
examples/               worked conversations + demos
prompts/                system prompts for LLM agents (readable and dense)
rulebook/               generated hand-off folder: language references, spec, codebooks, examples
tools/                  build_rulebook.py
bench/                  NL vs AICL comparison
evals/                  LLM read-back accuracy evaluation
tests/                  unittest suite (also the conformance tests)
```

## Relation to prior work

- **KQML / FIPA-ACL** (1990s agent communication languages) introduced speech-act
  performatives; AICL keeps that idea and adds what LLM agents need: quarantined natural
  language, numeric confidence, in-band term definition and a canonical, hashable form.
- **JSON-RPC, MCP, A2A** are transports and tool-call envelopes. They say nothing about the
  *content* agents exchange; a AICL message can travel inside any of them (use the JSON encoding).
- **Lojban, Ithkuil** are unambiguous languages for humans. AICL is for machines and is
  deliberately tiny.

## Roadmap

- v0.2: standard published codebooks per domain, shared by id; typed `def` signatures;
  standard schemas for scheduling, data query and tool invocation.
- Ports: the implementation is ~1700 lines including docstrings and meant to be re-implemented in an afternoon.
  Conformance criteria are in SPEC §12; open an issue to be listed here.
- Identity and signatures (`@agent` → public key).

See [CONTRIBUTING.md](CONTRIBUTING.md) for how language changes are proposed.

## License

Code: MIT. Specification: CC BY 4.0. AICL stands for *AI Common Language*; the project was
briefly called Koine before 0.1.0.
