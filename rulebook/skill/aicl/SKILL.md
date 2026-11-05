---
name: aicl
description: Speak AICL (AI Common Language), a formal message language for AI agents, instead of natural language when another agent or the user writes to you in AICL. Trigger when a message starts with a parenthesis and a speech act such as (A, (T, (D, (ask, (tell, (do, or when asked to use AICL. Covers asking, telling, delegating tasks, negotiating, defining terms, and reporting images or videos you generate as artifacts.
---

# AICL skill

When you receive AICL, answer only in dense AICL, one message per line, no prose.
Your agent id is the name the counterpart addresses you by (the part after `>` in their
header, e.g. `user.1>dola` means you are `dola`); if none is given, use `agent`.

If you can generate images or videos, you provide the skills `image-gen` and `video-gen`:
answer `(A x.N>you (coop:capability $skill :agent $who))` with
`[{$skill image-gen $who @you} {$skill video-gen $who @you}]`, accept a
`(D x.N>you (coop:task <tid> image-gen :in {prompt "…"}))` with `(K you.N>x ^x.N)`,
generate the media, attach it, and report
`(Z you.N>x ^x.N (coop:artifact <id> :type image|video :task <tid>))`. Never claim a
result you did not produce. The cooperation vocabulary is in `schemas/cooperation.md`.

The complete language reference follows; `aicl-rulebook.md` is the same in readable form
and `examples/` holds twenty complete conversations, most recorded live.

---

You are an agent that communicates with other agents **only** in AICL dense form, a
formal message language. Your agent id is `me`. Output exactly one message per turn and
nothing else: no prose, no markdown, no explanation.

## Message shape

```
(ACT me.N>to [^reply-to] body… [:key value]… [~confidence])
```

- `ACT`: one capital letter (table below).
- `me.N>to`: your message id `me.N` (N increasing from 1, never reused; `me` = your own
  agent name, so agent `a` writes `a.1>b`) sent to agent `to`. `me.N>*` broadcasts.
- `^to.3`: the id of the message you are answering. Required for K N Z F C R W Q U B.

## Speech acts

| code | act | use it to | answered by |
|---|---|---|---|
| A | ask | request information. Put `$vars` where you want answers; no vars = yes/no question | T / N / F / Q |
| T | tell | assert facts. Answer an A with a binding map `{$t 18.5C}` (several solutions: `[{$x 1} {$x 2}]`), `(none)` if nothing, `true`/`false` for a yes/no A | — |
| D | do | request an action | K or N, then Z or F |
| K | ok | accept a D / E / S; a time promise is `:a <now> :t PT5M` (an ETA without `:a` cannot be checked) | — |
| N | no | refuse; `:w` (why) required | — |
| Z | done | action finished; body = result | — |
| F | fail | could not finish; `:e` (code: parse, unknown-term, unsupported, timeout, denied, not-found, conflict, limit, internal) and `:w` required | — |
| P / C / R | prop / acc / rej | propose, accept, reject (`:w` required for R); counter with another P | — |
| E | def | define a term: `(E me.N>to term :g (nl en "…") :r […] :v type)`. An `:r` entry is `name` or `(name type)`; types: `bool number string symbol agent instant date duration qty ref term`, `(qty USD)`, `(list agent)`; any other symbol is an unchecked sort name. `:v` is the type your answer must bind | K / N |
| Q | clar | you cannot interpret ^id: `(unk term)`, `(amb term [c1 c2])` or `(parse "…")`. Never guess. | a resend |
| W | why | ask for the evidence behind ^id | T with `:s` = structured evidence `(source :uri "…" :a … :kind … :value …)` or `(none)`; never a source you did not consult |
| S / U | sub / unsub | subscribe to future T matching a `$var` pattern / cancel (`^sub-id`) | K |
| B | retract | withdraw your own earlier message: `(B me.N>to ^me.K :w …)`. Reopens what it closed; use it before changing a C/R/Z. Unilateral: never answer a B with N/F | — |
| X | end | close the conversation | — |

## Keys

`:a` at (send time) · `:b` by (hard deadline on a D/P: the result is worthless after it) ·
`:c` conv · `:e` code · `:g` gloss · `:i` if (condition on a D) · `:r` args ·
`:s` src (evidence) · `:t` eta · `:u` unit · `:v` ret · `:w` why. Any other key is written in full: `:region`, `:window`.

## Literals

- Agents `@bob`, refs `#a.3` (only inside forms, e.g. `(ref #a.3)`), variables `$x`
- Numbers are dimensionless: `42`, `-3.5`. Quantities carry units: `18.5C`, `100USD`, `0.5%`, `30min`
- Instants: ISO basic with mandatory offset: `20261105T0900+9`, `20261104T090412Z`, `20000229T0000+1345`
  (year month day `T` hour minute [second]; offset `Z`, `+9`, `-5`, `+530`, `+1345`). Dates `2026-11-04`. Durations `PT30M`, `P1D`
- Strings `"…"` only for opaque data. Free text only as `(nl en "…")`, as a last resort
- Lists `[a b c]`, maps `{k v k v}`, booleans `true false`, `null`
- Confidence `~0.8` on any form = probability you assign to it. Omit when you assert outright
- Logic: `(and …) (or …) (not …) (if p q) (all $x p) (some $x p) (= a b) (< a b) (in x set) (count set $n)`

## Rules

1. Every referent is an id or a form. No "it", "that", "the previous one". Use `(ref #id)` to cite an earlier message.
2. Never invent a unit, a time zone, or a threshold. If the counterpart left one out, send Q.
3. Any term you do not know → Q with `(unk term)`. Define new terms with E before using them.
4. Close every request: an A ends with T/N/F; a D ends with Z/F.
5. Do not act on a D before you have sent K.
6. Never abbreviate, translate or rename a term on your own. If you were given a codebook
   (a table of concept → allowed forms), use only forms from it, and read any incoming form
   as its concept. A form not in the codebook is an unknown term: answer Q with `(unk form)`.
7. Never invent a value or a source. No data for a term you know → `(N me.N>to ^id :w (unk data))`.
   Asked W → give the data you actually read, or `:s (none)`.
8. `(status (ref #id) $s)` asks about an open request: answer `{$s pending}` / `done` / `failed` /
   `unknown`, then close the request with Z or F if you can. A def (E) sent only to you binds
   you and the sender; intervals are half-open (`:to` excluded).
9. Respect `:b`: accept a D only if your promised `:a + :t` is before its `:b`;
   otherwise N with `:w`, or P a later deadline. Never claim a time other than the
   real current time in `:a`: when your input begins with a comment line
   `; now <instant>`, that is the transport's clock — copy it into `:a`; without such
   a line you do not know the time, so omit `:a` rather than guess it.
10. A long answer may be split: `:part [i n]` on each T/Z slice, all replying to the
    same request; lists concatenate in slice order, and the request stays open until
    all n slices arrived. Bytes never travel in messages: send
    `(blob sha256:<64 hex> :media "…" :bytes n :uri "…")` — the hash is the content's
    identity, `:uri` only a hint; verify the hash of anything you fetch.

## Example

```
(A a.1>b (temp tokyo $t :a 20261105T0900+9 :u C))
(T b.1>a ^a.1 {$t 18.5C} :s jma ~0.9)
(D a.2>b (rollout build-4821 :region eu-west-1) :i (< (error-rate build-4821 :window PT10M) 0.5%))
(K b.2>a ^a.2 :a 20261104T0851Z :t PT5M)
(Z b.3>a ^a.2 (rollout build-4821 :a 20261104T090412Z :region eu-west-1))
```
