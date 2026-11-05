# Show HN draft

**Title (≤ 80 chars):**

Show HN: AICL – a formal language for AI agents, tested live on Gemini, Claude and Dola

**URL:** https://github.com/shotaros2/aicl

**First comment (post it yourself right after submitting):**

Hi HN. AICL (AI Common Language) is a small formal message language for agent-to-agent
communication: every message states its speech act, every referent is an id, numbers
carry units, time carries a zone, uncertainty is a number, free text is quarantined in
`(nl …)`, unknown words get `clar` instead of a guess, and every request must be closed.
Spec, dependency-free Python reference implementation, validator, MIT.

```
(ask  #a.1 @a>@b (temp tokyo $t :unit C :at 2026-11-05T09:00+09:00))
(tell #b.1 @b>@a ^a.1 {$t 18.5C} ~0.9 :src jma)
```

What I think is actually interesting is what happened when I gave the ~750-token
rulebook to real models and let them talk:

- Protocol compliance was easy. Gemini Flash/Pro, Claude and Dola (a third-party agent
  app given only a skill zip) kept ids, reply references, binding maps and `clar` from the
  first try. Claude and Gemini negotiated a meeting slot in 9 messages with 0 protocol
  errors, later with no human in the loop over an HTTP relay.
- Facts were not. Asked for a 09:00 temperature, Gemini answered the daily high and
  defended it with `false ~1.0`. Given a fresh `def` it had no data for, it produced
  `{$x 0.75} ~0.8` and, asked why, invented a source. Without a transport clock it
  invented `:at` timestamps (twice). It answered `status` queries with a `done` act four
  times across models and prompts.

Every one of those became a rule or a validator check: `retract`, mandatory structured
evidence or `(none)`, `status` + `:eta`, half-open intervals, `def` scope, a relay that
serves `now` and rejects skewed timestamps, Ed25519 `:sig` over the canonical form. The
sixteen example conversations are mostly live transcripts, kept with the errors the
validator caught.

Honest numbers: on cl100k the readable form costs ~30% more tokens than polite English;
the dense form reaches parity (610 vs 600 on the benchmark) and a shared codebook gets a
few percent below (a live packed run measured 370 vs 480 readable). The point is not
fewer tokens; it is zero guesses and a machine-checkable protocol. Making the language
"unreadable to humans" made it worse: English words are the cheapest tokens there are.

The end-to-end goal works today: an MCP server exposes the gateway, so Claude Code reads
the rulebook, writes `(D claude.1>img (coop:task t1 image-gen …))` itself, and gets an
image artifact back from a Gemini-backed specialist.

Things I'd love feedback on: the evidence model (`:src` structure), whether `retract`
semantics are right, and results from other models. Spec changes go through
`RFC:`-prefixed issues.
