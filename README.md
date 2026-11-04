# Koine

**A language for agents to talk to each other without ambiguity.**
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

## What Koine does

Koine is a small formal message language with four interchangeable encodings
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
[grammar/koine.ebnf](grammar/koine.ebnf).

### A complete exchange

```
(ask  #a.1 @a>@b (deploy-status build-4821 $s :finished-at $at))
(tell #b.1 @b>@a ^a.1 {$s finished $at 2026-11-04T08:50Z} :src ci-api)
(do   #a.2 @a>@b (rollout build-4821 :region eu-west-1)
      :if (< (error-rate build-4821 :window PT10M) 0.5%))
(ok   #b.2 @b>@a ^a.2 :eta PT5M)
(tell #b.3 @b>@a (error-rate build-4821 0.3% :window PT10M) :src metrics)
(done #b.4 @b>@a ^a.2 (rollout build-4821 :region eu-west-1 :at 2026-11-04T09:04:12Z))
```

More in [examples/](examples/): negotiation, in-band term definition and clarification,
subscriptions, broadcast discovery, coded failures.

### The dense form: what agents actually send

LLMs consume tokens, not bytes, so "binary" would make LLM-to-LLM traffic *more*
expensive (it would be base64 in the prompt). Instead, Koine has a **dense text encoding**
(SPEC §8): the same structure with one-letter speech acts, merged headers, one-letter
core keys and ISO-basic timestamps. It is bijective with the readable form, so
`koine fmt` always recovers the readable version for audit and debugging.

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
koine codebook codebooks/imagegen.json --tokenizer cl100k_base   # validate, show chosen forms
koine pack   msg.kd --codebook codebooks/imagegen.json --tokenizer cl100k_base
koine unpack msg.kd --codebook codebooks/imagegen.json           # back to concept ids
koine check  msg.kd --codebook codebooks/imagegen.json           # concepts count as known terms
```

## Honest numbers: precision is not free

`bench/compare.py` compares realistic natural-language agent dialogues with the same
information in Koine (cl100k_base tokenizer, which GPT-4-class and many open models use).
All columns are tokens; "packed" uses `codebooks/bench.json`:

| case | NL | readable | ratio | dense | ratio | packed | ratio |
|---|---|---|---|---|---|---|---|
| weather | 138 | 128 | 0.93 | 98 | 0.71 | 94 | 0.68 |
| clarify | 188 | 239 | 1.27 | 190 | 1.01 | 181 | 0.96 |
| deploy | 150 | 201 | 1.34 | 164 | 1.09 | 158 | 1.05 |
| scheduling | 124 | 211 | 1.70 | 158 | 1.27 | 158 | 1.27 |
| **total** | **600** | **779** | **1.30** | **610** | **1.02** | **591** | **0.98** |

The readable form costs about 30 % more tokens than polite English, because BPE
vocabularies are tuned for prose. The dense form removes 22 % of that; a codebook takes
a few percent more and lands **below natural language while carrying strictly more
information** (exact instants with time zones, ids, thresholds, provenance) and zero
ambiguity. In characters, every Koine form is far shorter. The scheduling case does not
move because its vocabulary was already one token per word; the remaining cost there is
the four time-zoned instants, which natural language simply leaves out.

Re-run the benchmark with your own model's tokenizer (`--tokenizer o200k_base`, or any
`tiktoken` encoding) before drawing conclusions for it.

## Install and use

```bash
pip install -e .            # or: pip install koine-lang  (once published)
```

```bash
koine fmt    examples/02_deploy.koine        # canonical single-line form (also decodes dense input)
koine dense  examples/02_deploy.koine        # dense text encoding for LLM-to-LLM exchange
koine pretty examples/02_deploy.koine        # readable layout
koine json   examples/02_deploy.koine        # JSON encoding
koine cbor   examples/01_weather.koine -o m.cbor
koine hash   examples/02_deploy.koine        # sha256 of canonical form, per message
koine check  examples/02_deploy.koine --known deploy-status --known rollout --known error-rate
koine stats  examples/05_subscription.koine  # size, tokens, nl ratio
```

```python
import koine

msgs = koine.parse_messages(open("examples/02_deploy.koine").read())
for issue in koine.validate_conversation(msgs, known_terms=["deploy-status", "rollout", "error-rate"]):
    print(issue)                             # protocol violations, open requests, unresolved terms

m = msgs[1]
print(m.act, m.sender, m.receiver, m.reply)  # tell b a a.1
print(koine.to_text(m.to_form()))            # canonical text
print(koine.to_dense(m.to_form()))           # dense text
print(koine.to_json_text(m.to_form()))       # canonical JSON
print(koine.digest(m.to_form()))             # sha256

from koine.build import msg, form, q
reply = msg("tell", "b.9", "b", "a", koine.KMap([(koine.Var("t"), q(18.5, "C"))]), reply="a.1", conf=0.9)
```

## Make an LLM speak Koine

[prompts/system_prompt.md](prompts/system_prompt.md) is a ~700-token system prompt that
teaches any instruction-following model the readable language;
[prompts/system_prompt_dense.md](prompts/system_prompt_dense.md) teaches the dense form,
which is what two LLM agents should use with each other. `examples/llm_dialogue.py` runs two
Claude instances negotiating a meeting in Koine, with every message parsed and validated
at the boundary before it is delivered:

```bash
pip install anthropic
python examples/llm_dialogue.py
```

`examples/two_agents_demo.py` does the same with rule-based agents and no network.

### Hand the folder to your own agent

The repository is self-describing for agents that read a project folder:

- `AGENTS.md` (Codex, Cursor and most general agents) and `CLAUDE.md` (Claude Code)
  tell the agent to load the system prompt and validate every message with `koine check`.
- `SKILL.md` makes the folder an [Agent Skill](https://github.com/anthropics/skills):
  copy it to `.claude/skills/koine/` (or your framework's skills directory) and the
  agent loads Koine only when it talks to another agent.

Two agents that have both read this folder can talk to each other in Koine with no
further setup; the validator is the referee.

## Repository layout

```
SPEC.md                 the language (normative)
grammar/koine.ebnf      text encoding grammar
koine/                  reference implementation (Python ≥ 3.11, no dependencies)
  lexer.py parser.py    text → terms
  printer.py            canonical + pretty text, sha256 digest
  dense.py              dense text encoding (tokenizer-tuned, bijective with canonical)
  codebook.py           tokenizer-aware codebooks: pack / unpack with the ambiguity rules
codebooks/              example codebooks (bench, imagegen)
  json_codec.py         JSON encoding
  cbor_codec.py         deterministic CBOR (RFC 8949 §4.2)
  validate.py           message + conversation validator, nl ratio
  cli.py                `koine` command
examples/               worked conversations + demos
prompts/                system prompt for LLM agents
bench/                  NL vs Koine comparison
tests/                  unittest suite (also the conformance tests)
```

## Relation to prior work

- **KQML / FIPA-ACL** (1990s agent communication languages) introduced speech-act
  performatives; Koine keeps that idea and adds what LLM agents need: quarantined natural
  language, numeric confidence, in-band term definition and a canonical, hashable form.
- **JSON-RPC, MCP, A2A** are transports and tool-call envelopes. They say nothing about the
  *content* agents exchange; a Koine message can travel inside any of them (use the JSON encoding).
- **Lojban, Ithkuil** are unambiguous languages for humans. Koine is for machines and is
  deliberately tiny.

## Roadmap

- v0.2: standard published codebooks per domain, shared by id; typed `def` signatures;
  standard schemas for scheduling, data query and tool invocation.
- Ports: the implementation is ~1700 lines including docstrings and meant to be re-implemented in an afternoon.
  Conformance criteria are in SPEC §12; open an issue to be listed here.
- Identity and signatures (`@agent` → public key).

See [CONTRIBUTING.md](CONTRIBUTING.md) for how language changes are proposed.

## License

Code: MIT. Specification: CC BY 4.0. "Koine" (κοινή, "the common tongue") is a provisional name.
