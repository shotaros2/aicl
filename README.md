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

Koine is a small formal message language with three interchangeable encodings
(compact text, JSON, deterministic CBOR) and one canonical form that can be hashed and signed.
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

## Honest numbers: precision is not free

`bench/compare.py` compares realistic natural-language agent dialogues with the same
information in Koine (cl100k_base tokenizer, which GPT-4-class and many open models use):

| case | NL chars | NL tokens | Koine chars | Koine tokens | tokens ratio |
|---|---|---|---|---|---|
| weather | 551 | 138 | 220 | 128 | 0.93 |
| clarify | 721 | 188 | 564 | 239 | 1.27 |
| deploy | 597 | 150 | 432 | 201 | 1.34 |
| scheduling | 433 | 124 | 402 | 211 | 1.70 |
| **total** | | **600** | | **779** | **1.30** |

Koine is **shorter in characters and bytes** and removes every ambiguity, but on today's
BPE tokenizers it costs **about 30 % more tokens** than polite English, because those
vocabularies are tuned for prose: an ISO instant with offset is ~16 tokens, a message
header `#a.1 @a>@b ^a.1` ~11. The scheduling case carries four instants, which alone are
more than a quarter of its tokens. Where the information density is high (weather) Koine already wins.

So the claim is not "fewer tokens". The claim is: **zero guesses, machine-verifiable
protocol, and a measurable budget for the ambiguous parts** (`nl ratio`). Token cost is
an engineering problem we are working on in the open (see Roadmap); if you use a
tokenizer-aware id scheme or your model's own tokenizer, re-run the benchmark.

## Install and use

```bash
pip install -e .            # or: pip install koine-lang  (once published)
```

```bash
koine fmt    examples/02_deploy.koine        # canonical single-line form
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
print(koine.to_json_text(m.to_form()))       # canonical JSON
print(koine.digest(m.to_form()))             # sha256

from koine.build import msg, form, q
reply = msg("tell", "b.9", "b", "a", koine.KMap([(koine.Var("t"), q(18.5, "C"))]), reply="a.1", conf=0.9)
```

## Make an LLM speak Koine

[prompts/system_prompt.md](prompts/system_prompt.md) is a ~700-token system prompt that
teaches any instruction-following model the language. `examples/llm_dialogue.py` runs two
Claude instances negotiating a meeting in Koine, with every message parsed and validated
at the boundary before it is delivered:

```bash
pip install anthropic
python examples/llm_dialogue.py
```

`examples/two_agents_demo.py` does the same with rule-based agents and no network.

## Repository layout

```
SPEC.md                 the language (normative)
grammar/koine.ebnf      text encoding grammar
koine/                  reference implementation (Python ≥ 3.11, no dependencies)
  lexer.py parser.py    text → terms
  printer.py            canonical + pretty text, sha256 digest
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

- v0.2: typed `def` signatures; standard schemas for scheduling, data query and tool
  invocation; conversation-level time anchor (RFC open: it saves ~10 tokens per instant at the
  price of context dependence); tokenizer-aware id conventions.
- Ports: the implementation is ~1300 lines including docstrings and meant to be re-implemented in an afternoon.
  Conformance criteria are in SPEC §11; open an issue to be listed here.
- Identity and signatures (`@agent` → public key).

See [CONTRIBUTING.md](CONTRIBUTING.md) for how language changes are proposed.

## License

Code: MIT. Specification: CC BY 4.0. "Koine" (κοινή, "the common tongue") is a provisional name.
