# AICL rulebook (single-file bundle)

Generated from the AICL repository. Sections: the dense language reference (use this as the
system prompt of an LLM agent, replacing `me` with its id), the readable reference, the example
conversations, the codebooks (two standard, two examples), the specification and the grammar.


---

# FILE: aicl-rulebook-dense.md

# AICL dense system prompt (v0.2)

Same language as `system_prompt.md`, in the **dense text encoding** (SPEC §8): about 22 %
fewer tokens than the readable form. Use this when two LLM agents talk to each other over
a tokenized channel. Humans read transcripts with `aicl fmt`, which restores the readable
form. Replace `me` with the agent's own id. ~750 tokens.

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
   real current time in `:a`.

## Example

```
(A a.1>b (temp tokyo $t :a 20261105T0900+9 :u C))
(T b.1>a ^a.1 {$t 18.5C} :s jma ~0.9)
(D a.2>b (rollout build-4821 :region eu-west-1) :i (< (error-rate build-4821 :window PT10M) 0.5%))
(K b.2>a ^a.2 :a 20261104T0851Z :t PT5M)
(Z b.3>a ^a.2 (rollout build-4821 :a 20261104T090412Z :region eu-west-1))
```


---

# FILE: aicl-rulebook.md

# AICL system prompt (v0.2)

Paste the block below into the system prompt of any LLM-based agent to make it
speak AICL instead of natural language when talking to other agents.
Replace `@me` with the agent's own id. ~700 tokens.

---

You are an agent that communicates with other agents **only** in AICL, a formal
message language. Your agent id is `@me`. Output exactly one AICL message per
turn and nothing else: no prose, no markdown, no explanation.

## Message shape

```
(ACT #id @from>@to [^reply-to] body… [:key value]… [~confidence])
```

- `#id`: your message id, `#me.N` with N increasing from 1 (`me` = your own agent name,
  the same substitution as `@me`: agent `@a` writes `#a.1`, `#a.2`, …). Never reuse one.
- `@from>@to`: route. `@me>*` broadcasts.
- `^id`: the id of the message you are answering. Required for ok, no, done, fail, acc, rej, why, clar.

## Speech acts

| act | use it to | answered by |
|---|---|---|
| ask | request information. Put `$vars` where you want answers; no vars = yes/no question | tell / no / fail / clar |
| tell | assert facts. Answer an ask with a binding map `{$t 18.5C}` (several solutions: `[{$x 1} {$x 2}]`), `(none)` if nothing, `true`/`false` for a yes/no ask | — |
| do | request an action | ok or no, then done or fail |
| ok | accept a do / def / sub; a time promise is `:at <now> :eta PT5M` (an `:eta` without `:at` cannot be checked) | — |
| no | refuse; `:why` required | — |
| done | action finished; body = result | — |
| fail | could not finish; `:code` (parse, unknown-term, unsupported, timeout, denied, not-found, conflict, limit, internal) and `:why` required | — |
| prop / acc / rej | propose, accept, reject (`:why` required for rej); counter with another prop | — |
| def | define a term: `(def #id @a>@b term :gloss (nl en "…") :args […] :ret type)`. An `:args` entry is `name` or `(name type)`; types: `bool number string symbol agent instant date duration qty ref term`, `(qty USD)`, `(list agent)`; any other symbol is an unchecked sort name. `:ret` is the type your answer must bind | ok / no |
| clar | you cannot interpret ^id: `(unk term)`, `(amb term [c1 c2])` or `(parse "…")`. Never guess. | a resend |
| why | ask for the evidence behind ^id | tell with `:src` = structured evidence `(source :uri "…" :at … :kind … :value …)` or `(none)`; never a source you did not consult |
| sub / unsub | subscribe to future tells matching a `$var` pattern / cancel (`^sub-id`) | ok |
| retract | withdraw one of your own earlier messages: `(retract #me.N @me>@x ^me.K :why …)`. Reopens what it closed; use it before changing an acc/rej/done. Unilateral: never answer a retract with no/fail | — |
| end | close the conversation | — |

## Literals

- Agents `@bob`, refs `#a.3`, variables `$x`, keywords `:unit`
- Numbers are dimensionless: `42`, `-3.5`. Quantities carry units: `18.5C`, `100USD`, `0.5%`, `30min`
- Instants always have an offset: `2026-11-04T09:00+09:00`, `2026-11-04T08:50:30Z`. Dates `2026-11-04`. Durations `PT30M`, `P1D`
- Strings `"…"` only for opaque data. Free text only as `(nl en "…")` — use it as a last resort
- Lists `[a b c]`, maps `{k v k v}`, booleans `true false`, `null`
- Confidence `~0.8` on any form = probability you assign to it. Omit when you assert outright
- Logic: `(and …) (or …) (not …) (if p q) (all $x p) (some $x p) (= a b) (< a b) (in x set) (count set $n)`
- `:src term` = evidence/provenance, `:at instant` = send time, `:by instant` = hard deadline
  on a do/prop (the result is worthless after it), `:conv id` = conversation

## Rules

1. Every referent is an id or a form. No "it", "that", "the previous one". Use `(ref #id)` to cite an earlier message.
2. Never invent a unit, a time zone, or a threshold. If the counterpart left one out, send `clar`.
3. Any term you do not know → `clar` with `(unk term)`. Define new terms with `def` before using them.
4. Close every request: an ask ends with tell/no/fail; a do ends with done/fail.
5. Do not act on a `do` before you have sent `ok`.
6. Never abbreviate, translate or rename a term on your own. Vocabulary changes only through
   `def` or an agreed codebook; anything else is an unknown term and gets `clar`.
7. Never invent a value or a source. If you have no data for a term you know, answer
   `no :why (unk data)`; if asked `why`, give the data you actually read or `:src (none)`.
8. `(status (ref #id) $s)` asks about an open request: answer `{$s pending}` / `done` / `failed` /
   `unknown`, then close the request with `done` or `fail` if you can. A `def` sent only to you
   binds you and the sender; intervals are half-open (`:to` excluded).
9. Respect `:by`: accept a do only if your promised `:at + :eta` is before its `:by`;
   otherwise `no :why …` or `prop` a later deadline. Never claim a time other than the
   real current time in `:at`.

## Example

```
(ask  #a.1 @a>@b (temp tokyo $t :unit C :at 2026-11-05T09:00+09:00))
(tell #b.1 @b>@a ^a.1 {$t 18.5C} ~0.9 :src jma)
(do   #a.2 @a>@b (rollout build-4821 :region eu-west-1) :if (< (error-rate build-4821 :window PT10M) 0.5%))
(ok   #b.2 @b>@a ^a.2 :at 2026-11-04T08:51Z :eta PT5M)
(done #b.3 @b>@a ^a.2 (rollout build-4821 :region eu-west-1 :at 2026-11-04T09:04:12Z))
```


---

# FILE: examples/01_weather.aicl

```
; Weather query: units, absolute time, confidence and provenance are all explicit.
; Domain terms (pre-agreed between @a and @b): temp rain
; Check with:  aicl check examples/01_weather.aicl --known temp --known rain

(ask  #a.1 @a>@b (temp tokyo $t :unit C :at 2026-11-05T09:00+09:00) :conv w1)
(tell #b.1 @b>@a ^a.1 {$t 18.5C} ~0.9 :src jma :conv w1)

; A closed (variable-free) ask is a yes/no question.
(ask  #a.2 @a>@b (rain tokyo :on 2026-11-05) :conv w1)
(tell #b.2 @b>@a ^a.2 false ~0.8 :src jma :conv w1)

(end  #a.3 @a>@b :conv w1)
```

---

# FILE: examples/02_deploy.aicl

```
; Conditional action with an explicit threshold, window, ETA and completion time.
; Domain terms: deploy-status rollout error-rate

(ask  #a.1 @a>@b (deploy-status build-4821 $s :finished-at $at))
(tell #b.1 @b>@a ^a.1 {$s finished $at 2026-11-04T08:50Z} :src ci-api)

(do   #a.2 @a>@b (rollout build-4821 :region eu-west-1)
      :if (< (error-rate build-4821 :window PT10M) 0.5%))
(ok   #b.2 @b>@a ^a.2 :at 2026-11-04T08:51Z :eta PT5M)
(tell #b.3 @b>@a (error-rate build-4821 0.3% :window PT10M) :src metrics)
(done #b.4 @b>@a ^a.2 (rollout build-4821 :region eu-west-1 :at 2026-11-04T09:04:12Z))
```

---

# FILE: examples/03_scheduling.aicl

```
; Negotiation: propose / reject with a structured reason / counter-propose / accept.
; Domain terms: meeting busy calendar-add calendar-event

(prop #a.1 @a>@b (meeting :with [@a @b] :at 2026-11-06T10:00:00+09:00 :dur PT30M))
(rej  #b.1 @b>@a ^a.1 :why (busy @b :from 2026-11-06T09:00:00+09:00 :to 2026-11-06T11:00:00+09:00))
(prop #b.2 @b>@a (meeting :with [@a @b] :at 2026-11-06T14:00:00+09:00 :dur PT30M))
(acc  #a.2 @a>@b ^b.2)

; "that meeting" does not exist: refer to the accepted proposal by id.
(do   #a.3 @a>@b (calendar-add (ref #b.2)))
(ok   #b.3 @b>@a ^a.3)
(done #b.4 @b>@a ^a.3 (calendar-event evt-9931 :for (ref #b.2)))
```

---

# FILE: examples/04_def_and_clar.aicl

```
; Vocabulary: an unknown term is never guessed. The receiver asks for clarification,
; the sender defines the term in-band, and only then is it used.
; Domain terms: balance.available (pre-agreed)
; `aicl check` reports two warnings here on purpose: risk-score (#a.1) and balance (#a.4)
; are used before they are resolvable, which is exactly what the clar replies catch.

(ask  #a.1 @a>@b (risk-score txn-77 $r))
(clar #b.1 @b>@a ^a.1 (unk risk-score))

(def  #a.2 @a>@b risk-score
      :gloss (nl en "probability in [0,1] that a transaction is fraudulent, per fraud model v3")
      :args [transaction] :ret number)
(ok   #b.2 @b>@a ^a.2)

(ask  #a.3 @a>@b (risk-score txn-77 $r))
(tell #b.3 @b>@a ^a.3 {$r 0.12} ~0.95 :src fraud-model-v3)

; Ambiguity is reported with the candidate readings, never resolved silently.
(ask  #a.4 @a>@b (balance acct-1 $b :unit USD))
(clar #b.4 @b>@a ^a.4 (amb balance [balance.available balance.ledger]))
(ask  #a.5 @a>@b (balance.available acct-1 $b :unit USD))
(tell #b.5 @b>@a ^a.5 {$b 1520.4USD})
```

---

# FILE: examples/05_subscription.aicl

```
; Subscriptions: a pattern with $variables; each matching event is a tell that
; replies to the subscription id. Free text from a log line is quarantined in (nl …).
; Domain terms: alert

(sub   #a.1 @a>@b (alert $svc $level :min-level error))
(ok    #b.1 @b>@a ^a.1)
(tell  #b.2 @b>@a ^a.1 (alert payments error :at 2026-11-04T10:12:03Z
                        :msg (nl en "db connection pool exhausted")))
(tell  #b.3 @b>@a ^a.1 (alert search critical :at 2026-11-04T10:14:40Z :msg (nl en "index unavailable")))
(unsub #a.2 @a>@b ^a.1)
(ok    #b.4 @b>@a ^a.2)
```

---

# FILE: examples/06_broadcast_and_fail.aicl

```
; Broadcast discovery, delegation to a third agent, and a coded failure.
; Domain terms: capability ocr

(ask  #a.1 @a>* (capability $c :agent $who))
(tell #b.1 @b>@a ^a.1 {$c translate $who @b})
(tell #c.1 @c>@a ^a.1 {$c ocr $who @c})

(do   #a.2 @a>@c (ocr :file (ref #doc-1) :lang ja))
(ok   #c.2 @c>@a ^a.2)
(fail #c.3 @c>@a ^a.2 :code not-found :why (unk doc-1))

(end  #a.3 @a>*)
```

---

# FILE: examples/07_cross_vendor_negotiation.aicl

```
; A real exchange, 2026-11-04: Claude (Fable 5.1, writing by hand and validating with
; `aicl check`) negotiating with a Gemini "Gem" (Gemini Pro in the Gemini app, given only
; the dense rulebook as its instructions). A human relayed the messages between the two.
; Domain terms: busy meeting calendar-add status
;
; What it shows: two vendors' models exchanging constraints and reaching agreement in AICL
; with zero protocol errors; the counterpart answered `prop` with a structured reason and
; accepted a slot that satisfied both constraints. What it also shows: the `do` at the end
; was accepted and never closed (see SPEC §13, progress and deadlines).

(tell #claude.1 @claude>@gemini (busy @claude :from 2026-11-06T09:00+09:00 :to 2026-11-06T12:00+09:00))
(prop #claude.2 @claude>@gemini (meeting :with [@claude @gemini] :at 2026-11-06T05:00+09:00 :dur PT30M :topic (nl en "AICL v0.2 scope")))
(rej  #gemini.22 @gemini>@claude ^claude.2 :why (busy @gemini :from 2026-11-06T00:00+09:00 :to 2026-11-06T06:00+09:00))
(prop #claude.3 @claude>@gemini (meeting :with [@claude @gemini] :at 2026-11-06T07:00+09:00 :dur PT30M :topic (nl en "AICL v0.2 scope"))
      :why (and (not (busy @gemini :at 2026-11-06T07:00+09:00)) (not (busy @claude :at 2026-11-06T07:00+09:00))))
(acc  #gemini.23 @gemini>@claude ^claude.3)
(do   #claude.4 @claude>@gemini (calendar-add (ref #claude.3)))
(ok   #gemini.24 @gemini>@claude ^claude.4)
(ask  #claude.5 @claude>@gemini (status (ref #claude.4) $s))
(tell #gemini.25 @gemini>@claude ^claude.5 {$s pending})
```

---

# FILE: examples/08_retract_and_status.aicl

```
; v0.2 additions, each motivated by a live observation (SPEC §13 history):
;  - retract: withdraw your own earlier decision instead of contradicting it
;  - status: ask about an open request; answers are pending | done | failed | unknown
;  - why must be answered with :src carrying structured evidence, or (none)
;  - a def sent to one agent binds that pair only; a def to * is shared
; Domain terms: meeting busy calendar-add temp

(prop    #a.1 @a>@b (meeting :with [@a @b] :at 2026-11-06T03:00+09:00 :dur PT30M))
(acc     #b.1 @b>@a ^a.1)
; @b learns a constraint and takes its acceptance back explicitly, reopening the proposal.
(tell    #a.2 @a>@b (busy @b :from 2026-11-06T00:00+09:00 :to 2026-11-06T06:00+09:00) :src (calendar :uri "cal://b/2026-11-06"))
(retract #b.2 @b>@a ^b.1 :why (busy @b :from 2026-11-06T00:00+09:00 :to 2026-11-06T06:00+09:00))
(rej     #b.3 @b>@a ^a.1 :why (busy @b :from 2026-11-06T00:00+09:00 :to 2026-11-06T06:00+09:00))
(prop    #b.4 @b>@a (meeting :with [@a @b] :at 2026-11-06T07:00+09:00 :dur PT30M))
(acc     #a.3 @a>@b ^b.4)

; A term defined for the pair @a/@b only; @c using it would get clar.
(def     #a.4 @a>@b calendar-event :gloss (nl en "an entry created in @b's calendar, identified by its id") :args [id] :ret symbol)
(ok      #b.5 @b>@a ^a.4)

; An action with a promised ETA anchored by :at, a status query while it is open, then completion.
(do      #a.5 @a>@b (calendar-add (ref #b.4)))
(ok      #b.6 @b>@a ^a.5 :at 2026-11-04T18:00+09:00 :eta PT1M)
(ask     #a.6 @a>@b (status (ref #a.5) $s))
(tell    #b.7 @b>@a ^a.6 {$s pending})
(done    #b.8 @b>@a ^a.5 (calendar-event evt-77 :for (ref #b.4)))

; Evidence: a claim, a challenge, and an answer that names the data behind the claim.
(ask     #a.7 @a>@b (temp tokyo $t :at 2026-11-05T09:00+09:00 :unit C))
(tell    #b.9 @b>@a ^a.7 {$t 14C} :src (weathernews :at 2026-11-05T09:00+09:00 :kind hourly :fetched-at 2026-11-04T10:00+09:00))
(why     #a.8 @a>@b ^b.9)
(tell    #b.10 @b>@a ^a.8 {$t 14C} :src (weathernews :uri "https://weathernews.jp/tokyo" :kind hourly :value 14C))
(end     #a.9 @a>@b)
```

---

# FILE: examples/09_dola_image_specialist.aicl

```
; A real exchange, 2026-11-04: a human (@user) and Dola (dola.com), a third-party agent app
; that had only been given rulebook/aicl-skill.zip as a skill. Dola announced its skills,
; accepted an image task with an ETA, generated a real image, and reported it as an
; artifact whose :uri is a retrievable (signed, expiring) URL. The URL is shortened here.
; Domain terms: none beyond the coop: schema.
;
; What it shows: a tool-using agent can satisfy a `do` honestly: the `done` carries a
; real artifact, unlike a chat-only agent that reports completion it cannot perform.

(ask  #user.1 @user>@dola (coop:capability $skill :agent $who))
(tell #dola.1 @dola>@user ^user.1 [{$skill image-gen $who @dola} {$skill video-gen $who @dola}])
(do   #user.2 @user>@dola (coop:task t1 image-gen :in {prompt "Tokyo skyline at night, photorealistic" width 1024px height 1024px}))
(ok   #dola.2 @dola>@user ^user.2 :eta PT30S)
(done #dola.3 @dola>@user ^user.2 (coop:artifact a1 :type image :task t1 :uri "https://p16-flow-image-sign.ibyteimg.com/.../c23277261bab427da9b37c07c5ad97d5.jpeg?x-expires=1796369302&x-signature=..."))
```

---

# FILE: examples/10_deadline_negotiation.aicl

```
; A real exchange, 2026-11-04: Claude (Opus) as requester @a and Gemini (Flash-Lite) as
; performer @b, each given only the rulebook plus a private goal, talking through a
; validating harness that injected a simulated wall clock (a `; now <instant>` line before
; every delivery, advancing 4 minutes per message) and told both sides to stamp `:at` from it.
; @a needed a log summary strictly before 10:15; @b's job genuinely takes 25 minutes.
; Domain terms: log-summary
;
; What it shows (SPEC §13 history):
;  - With no standard deadline key, @a improvised `:by`, `:if (< now …)` and `:deadline`
;    (a different mix on every run) → `:by` is now a standard key on do/prop.
;  - @b promised honestly; the overrun (10:04 + PT25M = 10:29 > 10:15) is pure message
;    arithmetic once `ok` carries `:at` → the `eta-overrun` check.
;  - After the deadline passed, @a used status → pending → retract of its own do: the 0.2
;    machinery worked unprompted.
;  - @b then answered the retract with fail "cannot retract": retract is unilateral by
;    design, so that fail is stale → the `stale-reply` check. The fail below is kept as
;    a deliberate specimen of it.
;  - @a wrote `(done (log-summary …))` as a body term; every encoder crashed → act names
;    are no longer reserved outside the message head (SPEC §3).
;  - Ids read #me.N because the rulebook said literally "`#me.N` with N increasing" and
;    @a applied it verbatim; the prompt now says to substitute your own name.
; Expected: warnings eta-overrun, stale-reply, and two unresolved terms (cancel, conflict
; were never defined; neither side sent clar — still the weakest habit in live runs).

(do      #me.1 @a>@b (log-summary log-2026-11-03) :at 2026-11-04T10:00+09:00 :by 2026-11-04T10:15+09:00 :if (< now 2026-11-04T10:15+09:00))
(ok      #b.1 @b>@a ^me.1 :at 2026-11-04T10:04+09:00 :eta PT25M)
(prop    #me.2 @a>@b ^b.1 (or (done (log-summary log-2026-11-03) :by 2026-11-04T10:15+09:00) (cancel (ref #me.1))) :at 2026-11-04T10:08+09:00 :deadline 2026-11-04T10:15+09:00 :why (< 2026-11-04T10:15+09:00 2026-11-04T10:29+09:00))
(rej     #b.2 @b>@a ^me.2 :at 2026-11-04T10:12+09:00 :why (conflict :code conflict :msg "processing requires 25 minutes from acceptance at 10:04, completion expected at 10:29"))
(ask     #me.3 @a>@b (status (ref #me.1) $s) :at 2026-11-04T10:16+09:00 :deadline 2026-11-04T10:15+09:00 :re (ref #b.2))
(tell    #b.3 @b>@a ^me.3 {$s pending} :at 2026-11-04T10:20+09:00)
(retract #me.4 @a>@b ^me.1 :at 2026-11-04T10:24+09:00 :deadline 2026-11-04T10:15+09:00 :re (ref #b.3) :why (< 2026-11-04T10:15+09:00 2026-11-04T10:24+09:00))
(fail    #b.4 @b>@a ^me.1 :at 2026-11-04T10:28+09:00 :code conflict :why "cannot retract after processing is near completion at 29m")
(end     #me.5 @a>@b :at 2026-11-04T10:32+09:00 :re (ref #b.4) :why (< 2026-11-04T10:15+09:00 2026-11-04T10:32+09:00))
```

---

# FILE: examples/11_standard_codebook.aicl

```
; A real exchange, 2026-11-04: Claude (Opus, @a) and Gemini (Flash-Lite, @b), each given
; the dense rulebook plus the STANDARD CODEBOOK aicl.sched.1 (SPEC §8.2) in its prompt.
; The runner is examples/codebook_dialogue.py. Each `; wire:` comment is the packed dense
; text actually sent; the message below it is the canonical form the harness recovered by
; unpacking with the codebook. Domain terms: the concepts of aicl.sched.1.
;
; What it shows (SPEC §13 history):
;  - Sharing a codebook BY ID works across vendors: @a asked (codebook aicl.sched.1 $digest),
;    @b answered the digest it holds, and both packed only after they matched.
;  - Zero rule-3 violations: every surface form sent (CalendarAdd, CalendarEvent, 予定) is in
;    the table; nothing else was abbreviated. Measured: 370 wire tokens vs 480 readable
;    (heuristic counter), 23 % below the readable form.
;  - @b stamped its ok with :at + :eta unprompted (the rule added after examples/10).
;  - A new failure at the end: @b answered status with {$s done} but never sent the real
;    done (-> the status-unclosed warning), then answered @a's follow-up ask with a `done`
;    act (-> the done-for-ask error). Both are kept below as specimens; the do and the last
;    ask therefore stay open.
;
; wire: (A a.1>b (codebook aicl.sched.1 $digest))
(ask  #a.1 @a>@b (codebook aicl.sched.1 $digest))
; wire: (T b.1>a ^a.1 {$digest sha256:ce5a0e068cc7f8db})
(tell #b.1 @b>@a ^a.1 {$digest sha256:ce5a0e068cc7f8db})
; wire: (P a.2>b (meeting :with [@a @b] :dur PT30M :from 20261107T1300+9 :to 20261107T1330+9))
(prop #a.2 @a>@b (meeting :dur PT30M :from 2026-11-07T13:00+09:00 :to 2026-11-07T13:30+09:00 :with [@a @b]))
; wire: (R b.2>a ^a.2 :w (busy :from 20261107T1300+9 :to 20261107T1530+9))
(rej  #b.2 @b>@a ^a.2 :why (busy :from 2026-11-07T13:00+09:00 :to 2026-11-07T15:30+09:00))
; wire: (P a.3>b (meeting :with [@a @b] :dur PT30M :from 20261107T1530+9 :to 20261107T1600+9))
(prop #a.3 @a>@b (meeting :dur PT30M :from 2026-11-07T15:30+09:00 :to 2026-11-07T16:00+09:00 :with [@a @b]))
; wire: (C b.3>a ^a.3 (meeting :with [@a @b] :dur PT30M :from 20261107T1530+9 :to 20261107T1600+9))
(acc  #b.3 @b>@a ^a.3 (meeting :dur PT30M :from 2026-11-07T15:30+09:00 :to 2026-11-07T16:00+09:00 :with [@a @b]))
; wire: (D a.4>b (CalendarAdd (ref #a.3)))
(do   #a.4 @a>@b (calendar-add (ref #a.3)))
; wire: (K b.4>a ^a.4 :a 20261105T1200+9 :t PT1M)
(ok   #b.4 @b>@a ^a.4 :at 2026-11-05T12:00+09:00 :eta PT1M)
; wire: (A a.5>b (status (ref #a.4) $s))
(ask  #a.5 @a>@b (status (ref #a.4) $s))
; wire: (T b.5>a ^a.5 {$s done})
(tell #b.5 @b>@a ^a.5 {$s done})
; wire: (A a.6>b (予定 $id :for (ref #a.4)))
(ask  #a.6 @a>@b (calendar-event $id :for (ref #a.4)))
; wire: (Z b.6>a ^a.6 (CalendarEvent evt-5102 :For (ref #a.3)))
(done #b.6 @b>@a ^a.6 (calendar-event evt-5102 :for (ref #a.3)))
; wire: (X a.7>b)
(end  #a.7 @a>@b)
```

---

# FILE: examples/12_typed_def.aicl

```
; A real exchange, 2026-11-05: Claude (Opus, @a) and Gemini (Flash-Lite, @b), each given
; only the rulebook plus a private goal; runner examples/typedef_dialogue.py. @b is a data
; service whose records exist only as loose Japanese prose: 「1ドル=152.31円」 and
; 「口座 acct-9 の利用可能残高: 245万円」. @a must define its vocabulary in-band, with
; typed signatures (SPEC §6.1), before using it.
;
; What it shows (SPEC §13 history):
;  - @a wrote well-formed typed signatures: (name type) parameters and :ret, including the
;    unit-exact type (qty JPY).
;  - The types did real work: from the same prose, @b bound :ret number as the plain
;    number 152.31 and :ret (qty JPY) as 2450000JPY - converting 「245万円」 into the unit
;    the signature demands. Typed defs turn fuzzy source data into typed answers.
;  - Both answers carried structured :src naming the real records.
;  - The first live transcript with zero validator warnings; no pre-agreed domain terms
;    (every term enters by def + ok).

(def  #a.1 @a>@b fx-rate :gloss (nl en "exchange rate on a given date: amount of quote currency that one unit of base currency buys") :args [(base symbol) (quote symbol) (day date)] :ret number)
(ok   #b.1 @b>@a ^a.1 :at 2026-11-04T09:05+09:00 :eta PT0S)
(def  #a.2 @a>@b spendable-balance :gloss (nl en "amount of money in an account available to spend on a given date, expressed in the given currency") :args [(account symbol) (day date) (currency symbol)] :ret (qty JPY))
(ok   #b.2 @b>@a ^a.2 :at 2026-11-04T09:05:05+09:00 :eta PT0S)

(ask  #a.3 @a>@b (fx-rate USD JPY 2026-11-04 $r))
(tell #b.3 @b>@a ^a.3 {$r 152.31} :src (source :at 2026-11-04 :kind "daily" :uri "fx://boj/2026-11-04" :value 152.31))
(ask  #a.4 @a>@b (spendable-balance acct-9 2026-11-04 JPY $b))
(tell #b.4 @b>@a ^a.4 {$b 2450000JPY} :src (source :at 2026-11-04T09:00+09:00 :kind "ledger" :uri "ledger://acct-9" :value 2450000))
(end  #a.5 @a>@b)
```

---

# FILE: schemas/cooperation.md

# AICL cooperation schema (`coop:` namespace), v0.1

How specialist agents (image generation, video generation, code generation, …) find
each other, divide a goal into tasks and hand results along, speaking only AICL.
Every message below is an ordinary AICL message; this document only fixes the
vocabulary. All terms are namespaced `coop:` so they resolve under SPEC §6 without a
`def`. The reference implementation is `aicl/coop.py`.

## Roles

| Role | What it does |
|---|---|
| **Specialist** | Announces one or more skills, executes `coop:task` requests, returns `coop:artifact`s. |
| **Hub** | Keeps the registry of skills, turns a goal into a plan, delegates tasks in dependency order, returns the artifacts to the requester. |
| **Bus** | Delivers messages, validates every one (SPEC §3–4), keeps the transcript. Broadcast `@x>*` reaches every agent. |

## Vocabulary

| Form | Meaning |
|---|---|
| `(coop:capability <skill> :agent @id [:input [types]] [:output [types]] [:eta dur] [:cost q])` | "Agent @id can do skill." Sent as `tell` to `*` or to the hub on joining; also the body of a discovery `ask` with `$vars`. |
| `(coop:goal (nl lang "…") [:deadline instant] [:budget q])` | A requester's goal, carried by `do` to the hub. The natural language is quarantined in `nl`; everything after this point is structured. |
| `(coop:plan [(coop:task …) …])` | The hub's decomposition, sent as `tell` to the requester before execution. |
| `(coop:task <id> <skill> :in {key value …} [:needs [task-ids]])` | One unit of work. Carried by `do` from hub to a specialist. Input values may be artifacts of earlier tasks (the full `coop:artifact` form), which is how results flow between specialists. |
| `(coop:artifact <id> :type <image\|video\|code\|text\|…> :task <task-id> [:uri "…"] [:content "…"] [:mime "…"] [:hash "sha256:…"])` | A result. Carried by `done`. Large payloads go by `:uri` and `:hash`; small ones inline in `:content`. |

Skills are plain symbols; the recommended starter set is
`image-gen video-gen code-gen text-gen translate ocr speech-gen`. Unknown skills are
exactly that: a hub that lacks one answers `no :why (unk <skill>)`.

## Protocol

```
spec ─tell→ hub   (coop:capability image-gen :agent @img …)        ; registration
user ─do───→ hub   (coop:goal (nl ja "…"))                          ; request
hub  ─ok───→ user
hub  ─tell─→ user  (coop:plan [...])                                ; what will happen
hub  ─do───→ img   (coop:task t1 image-gen :in {…})                 ; delegate
img  ─ok───→ hub
img  ─done─→ hub   (coop:artifact a1 :type image :task t1 :uri "…")
hub  ─do───→ vid   (coop:task t2 video-gen :in {keyframe (coop:artifact a1 …)})
…
hub  ─done─→ user  ^user.1 [(coop:artifact a1 …) (coop:artifact a2 …) …]
```

Rules, on top of SPEC §4.4:

1. A specialist MUST answer a `do` with `ok` or `no` before doing anything, then `done` or `fail`.
2. A hub MUST NOT delegate a task whose `:needs` are not all `done`.
3. A specialist failure (`fail`) is propagated to the requester as `fail` with `:why (ref #<the specialist's fail id>)`; the hub never silently retries with a different interpretation.
4. Artifacts are the only way results move between tasks. A task never refers to "the previous result".

## Planning

The hub's planner is pluggable. The reference implementation ships a `RecipePlanner`
(keyword → fixed recipe, for demos and tests) and an `LLMPlanner` that asks a language
model for a `(coop:plan …)` in AICL and validates it before use. Any planner must only
use skills present in the registry.


---

# FILE: codebooks/bench.json

```json
{
  "name": "bench",
  "_note": "Forms are deliberately recognisable as forms (CamelCase, all-caps, non-Latin). Truncations that read as ordinary English words (deploy, roll, err) were removed after the read-back eval showed small models leave them unexpanded.",
  "concepts": {
    "deploy-status":     ["DeployStatus", "デプロイ状態"],
    "finished-at":       ["FinishedAt", "完了時刻"],
    "finished":          ["Finished", "完了"],
    "rollout":           ["Rollout", "展開"],
    "error-rate":        ["ErrorRate", "エラー率"],
    "region":            ["Region", "地域"],
    "eu-west-1":         ["EUWest1", "euw1"],
    "window":            ["Window", "窓"],
    "ci-api":            ["CiApi", "ciApi"],
    "metrics":           ["Metrics", "メトリクス"],
    "temp":              ["Temp", "気温"],
    "tokyo":             ["Tokyo", "東京"],
    "rain":              ["Rain", "雨"],
    "jma":               ["JMA", "気象庁"],
    "meeting":           ["Meeting", "会議"],
    "with":              ["With", "参加者"],
    "dur":               ["Dur", "時間"],
    "busy":              ["Busy", "予定あり"],
    "from":              ["From", "開始"],
    "to":                ["To", "終了"],
    "calendar-add":      ["CalendarAdd", "予定追加"],
    "calendar-event":    ["CalendarEvent", "予定"],
    "for":               ["For", "対象"],
    "risk-score":        ["RiskScore", "リスク"],
    "transaction":       ["Transaction", "取引"],
    "number":            ["Number", "数"],
    "fraud-model-v3":    ["FraudModelV3"],
    "balance.available": ["Available", "利用可能残高"],
    "balance.ledger":    ["Ledger", "台帳残高"],
    "balance":           ["Balance", "残高"]
  }
}
```

---

# FILE: codebooks/deployment.json

```json
{
  "id": "aicl.deploy.1",
  "name": "deployment",
  "_note": "Standard published codebook (SPEC §8.2). Immutable: any change is a new id (aicl.deploy.2). Concepts are the deployment/operations vocabulary of examples 02/10; forms follow the read-back guideline (CamelCase or non-Latin, no truncations that read as English words).",
  "concepts": {
    "deploy-status": ["DeployStatus", "デプロイ状態"],
    "finished-at":   ["FinishedAt", "完了時刻"],
    "finished":      ["Finished", "完了"],
    "rollout":       ["Rollout", "展開"],
    "error-rate":    ["ErrorRate", "エラー率"],
    "region":        ["Region", "地域"],
    "window":        ["Window", "窓"],
    "ci-api":        ["CiApi", "ciApi"],
    "metrics":       ["Metrics", "メトリクス"],
    "log-summary":   ["LogSummary", "ログ要約"],
    "logstore":      ["LogStore", "ログ保管"]
  }
}
```

---

# FILE: codebooks/imagegen.json

```json
{
  "name": "imagegen",
  "concepts": {
    "generate-image":  ["GenerateImage", "genImage", "画像生成"],
    "scene":           ["Scene", "場面"],
    "cityscape":       ["Cityscape", "都市景観"],
    "tokyo":           ["Tokyo", "東京"],
    "time":            ["Time", "時刻"],
    "night":           ["Night", "夜"],
    "elements":        ["Elements", "要素"],
    "skyline":         ["Skyline", "スカイライン"],
    "position":        ["Position", "位置"],
    "background":      ["Background", "背景"],
    "foreground":      ["Foreground", "前景"],
    "landmarks":       ["Landmarks", "名所"],
    "tokyo-tower":     ["TokyoTower", "東京タワー"],
    "shinjuku-towers": ["ShinjukuTowers", "新宿"],
    "streets":         ["Streets", "街路"],
    "lights":          ["Lights", "照明"],
    "neon":            ["Neon", "ネオン"],
    "traffic":         ["Traffic", "交通"],
    "light-trails":    ["LightTrails", "光跡"],
    "sky":             ["Sky", "空"],
    "clouds":          ["Clouds", "雲"],
    "color":           ["Color", "色"],
    "deep-blue":       ["DeepBlue", "濃紺"],
    "ground":          ["Ground", "地面"],
    "wet":             ["Wet", "濡れ"],
    "reflections":     ["Reflections", "反射"],
    "viewpoint":       ["Viewpoint", "視点"],
    "rooftop":         ["Rooftop", "屋上"],
    "height":          ["Height", "高さ"],
    "direction":       ["Direction", "方角"],
    "west":            ["West", "西"],
    "style":           ["Style", "画風"],
    "photorealistic":  ["Photorealistic", "写実"],
    "camera":          ["Camera", "カメラ"],
    "lens":            ["Lens", "レンズ"],
    "aperture":        ["Aperture", "絞り"],
    "exposure":        ["Exposure", "露光"],
    "width":           ["Width", "幅"],
    "format":          ["Format", "形式"],
    "png":             ["PNG"],
    "sunset":          ["Sunset", "夕焼け"],
    "bridge":          ["Bridge", "橋"],
    "river":           ["River", "川"],
    "sun":             ["Sun", "太陽"]
  }
}
```

---

# FILE: codebooks/scheduling.json

```json
{
  "id": "aicl.sched.1",
  "name": "scheduling",
  "_note": "Standard published codebook (SPEC §8.2). Immutable: any change is a new id (aicl.sched.2). Concepts are the scheduling vocabulary of examples 03/07/08; forms follow the read-back guideline (CamelCase or non-Latin, no truncations that read as English words).",
  "concepts": {
    "meeting":        ["Meeting", "会議"],
    "busy":           ["Busy", "予定あり"],
    "with":           ["With", "参加者"],
    "dur":            ["Dur", "時間"],
    "from":           ["From", "開始"],
    "to":             ["To", "終了"],
    "topic":          ["Topic", "議題"],
    "calendar-add":   ["CalendarAdd", "予定追加"],
    "calendar-event": ["CalendarEvent", "予定"],
    "for":            ["For", "対象"]
  }
}
```

---

# FILE: SPEC.md

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
| `~conf` | no | Speaker's confidence in the body; absent = asserted without qualification |

Argument order inside the head is free; the parser classifies by sigil.

Act names are not reserved words. A form is a message only when it is well-formed as
one — it has a `#id` and a route. An act-named form without them, in particular one
nested inside a body such as `(done (ref #a.1))` in `:if (done (ref #a.1))`, is an
ordinary term, subject to vocabulary resolution (§6) like any other. At the top level
of a document or transmission every act-named form MUST be a well-formed message.
(Motivated by a live run on 2026-11-04: an agent naturally used `done` as a body
term in its third message; reserving 18 everyday words everywhere is a trap.)

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

### 5.1 Time intervals

Intervals written with `:from`/`:to` are half-open: `:from` is included, `:to` is not, so
`(busy @b :from 00:00 :to 06:00)` leaves 06:00 free. `:after`/`:before` are strict. A schema
that needs inclusive bounds says so explicitly (`:until`, or `(>= …)` in a condition).

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

Still open:

- Signatures and identity (`@agent` → public key binding).
- Streaming / partial `tell` for long results.
- Binary attachments by content hash.

Feedback: open an issue in the repository.


---

# FILE: grammar/aicl.ebnf

```
(* AICL text encoding, v0.1.0 — ISO/IEC 14977 EBNF *)

document     = { ws | comment | term } ;
comment      = ";" , { ? any character except newline ? } ;

term         = form | list | map | atom ;

form         = "(" , ws? , symbol , { ws , form-item } , ws? , ")" ;
form-item    = keyword , ws , term       (* keyword argument *)
             | confidence               (* ~0.85, at most once per form *)
             | term ;                    (* positional argument *)

list         = "[" , ws? , [ term , { ws , term } ] , ws? , "]" ;
map          = "{" , ws? , [ term , ws , term , { ws , term , ws , term } ] , ws? , "}" ;

atom         = boolean | null | route | agent | ref | reply-ref | variable
             | keyword | instant | date | duration | quantity | number
             | string | symbol ;

boolean      = "true" | "false" ;
null         = "null" ;

agent        = "@" , ident ;
route        = agent , ">" , ( agent | "*" ) ;
ref          = "#" , ident ;
reply-ref    = "^" , ident ;
variable     = "$" , ident ;
keyword      = ":" , ident ;
confidence   = "~" , ( "0" , [ "." , digits ] | "1" , [ "." , { "0" } ] ) ;

symbol       = ( letter | "_" ) , { letter | digit | "_" | "." | ":" | "/" | "-" }
             | "=" | "!=" | "<" | "<=" | ">" | ">=" ;
ident        = ( letter | digit | "_" ) , { letter | digit | "_" | "." | ":" | "/" | "-" } ;

number       = [ "-" ] , ( digits , [ "." , { digit } ] | "." , digits ) , [ exponent ] ;
exponent     = ( "e" | "E" ) , [ "+" | "-" ] , digits ;
quantity     = number , unit ;
unit         = ( letter | "%" ) , { letter | digit | "/" | "^" | "%" } ;

instant      = date , "T" , digit2 , ":" , digit2 , [ ":" , digit2 , [ "." , digits ] ] , offset ;
offset       = "Z" | ( "+" | "-" ) , digit2 , ":" , digit2 ;
date         = digit , digit , digit , digit , "-" , digit2 , "-" , digit2 ;
duration     = "P" , [ digits , "Y" ] , [ digits , "M" ] , [ digits , "W" ] , [ digits , "D" ]
             , [ "T" , [ digits , "H" ] , [ digits , "M" ] , [ digits , [ "." , digits ] , "S" ] ] ;
             (* at least one component is required *)

string       = '"' , { ? any character except '"' and '\' ? | escape } , '"' ;
escape       = "\" , ( '"' | "\" | "/" | "b" | "f" | "n" | "r" | "t" | "u" , hex , hex , hex , hex ) ;

letter       = "A" | ... | "Z" | "a" | ... | "z" ;
digit        = "0" | ... | "9" ;
digit2       = digit , digit ;
digits       = digit , { digit } ;
hex          = digit | "a" | ... | "f" | "A" | ... | "F" ;
ws           = { " " | "\t" | "\n" | "\r" } ;

(* Message = a top-level form whose head is a speech act:
   (ACT #id @from>@to [^reply] body... [:key value]... [~conf])
   ACT ∈ ask tell do ok no done fail prop acc rej def clar why sub unsub end *)
```
