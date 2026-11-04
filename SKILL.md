---
name: koine
description: Speak, read and validate Koine, a formal message language for agent-to-agent communication. Use when talking to another AI agent, when a message you receive starts with (ask, (tell, (do, (prop or another Koine speech act, or when asked to write, translate or check Koine. Replaces natural-language prose between agents with unambiguous messages.
---

# Koine

Koine messages look like `(ask #a.1 @a>@b (temp tokyo $t :unit C :at 2026-11-05T09:00+09:00))`.
Every message states its speech act, ids, units, absolute time and confidence explicitly.

## Speaking Koine

1. Read `prompts/system_prompt_dense.md` (the text after `---`) once per conversation.
   It is the complete language reference in the dense form agents exchange, about
   750 tokens. `prompts/system_prompt.md` is the same language in readable form;
   `python -m koine fmt` converts dense to readable and `python -m koine dense` back.
2. Use your own agent id in place of `@me`, number your messages `#me.1`, `#me.2`, …
3. Send one message per turn and nothing else.
4. Never guess: unknown term → `(clar … (unk term))`; missing unit, time zone or
   threshold → `clar`; new vocabulary → `(def …)` and wait for `ok`.
5. Close every request: `ask` → `tell`/`no`/`fail`; `do` → `ok` then `done`/`fail`.

## Validating

Write the conversation so far to a file and run, from this skill's folder:

```bash
python -m koine check conversation.koine --known <domain-term> ...
```

`error` lines must be fixed before sending. `koine fmt` prints the canonical form,
`koine json` the JSON encoding for transports such as MCP or A2A, `koine stats` the
share of quarantined natural language (`nl ratio`), which should stay near zero.

## Reading Koine from another agent

Parse with the library rather than by eye when the message matters:

```python
import koine
m = koine.Message.from_form(koine.parse_one(text))
m.act, m.sender, m.receiver, m.reply, m.body, m.kw, m.conf
```

A binding map `{$t 18.5C}` in a `tell` answers the `$t` of the `ask` it replies to.

## Reference

- `SPEC.md` — normative specification (speech acts §4, core vocabulary §5, canonical form §7)
- `examples/*.koine` — six complete conversations covering every speech act
- `grammar/koine.ebnf` — text grammar
