# AICL rulebook (single-file bundle)

Generated from the AICL repository. Sections: the dense language reference (use this as the
system prompt of an LLM agent, replacing `me` with its id), the readable reference, six example
conversations, two example codebooks, the specification and the grammar.


---

# FILE: aicl-rulebook-dense.md

# AICL dense system prompt (v0.1)

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
- `me.N>to`: your message id `me.N` (N increasing from 1, never reused) sent to agent `to`. `me.N>*` broadcasts.
- `^to.3`: the id of the message you are answering. Required for K N Z F C R W Q U.

## Speech acts

| code | act | use it to | answered by |
|---|---|---|---|
| A | ask | request information. Put `$vars` where you want answers; no vars = yes/no question | T / N / F / Q |
| T | tell | assert facts. Answer an A with a binding map `{$t 18.5C}` (several solutions: `[{$x 1} {$x 2}]`), `(none)` if nothing, `true`/`false` for a yes/no A | — |
| D | do | request an action | K or N, then Z or F |
| K | ok | accept a D / E / S (optional `:t PT5M` = ETA) | — |
| N | no | refuse; `:w` (why) required | — |
| Z | done | action finished; body = result | — |
| F | fail | could not finish; `:e` (code: parse, unknown-term, unsupported, timeout, denied, not-found, conflict, limit, internal) and `:w` required | — |
| P / C / R | prop / acc / rej | propose, accept, reject (`:w` required for R); counter with another P | — |
| E | def | define a term: `(E me.N>to term :g (nl en "…") :r […] :v type)` | K / N |
| Q | clar | you cannot interpret ^id: `(unk term)`, `(amb term [c1 c2])` or `(parse "…")`. Never guess. | a resend |
| W | why | ask for the evidence behind ^id | T with :s |
| S / U | sub / unsub | subscribe to future T matching a `$var` pattern / cancel (`^sub-id`) | K |
| X | end | close the conversation | — |

## Keys

`:a` at (time) · `:c` conv · `:e` code · `:g` gloss · `:i` if (condition on a D) · `:r` args ·
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

## Example

```
(A a.1>b (temp tokyo $t :a 20261105T0900+9 :u C))
(T b.1>a ^a.1 {$t 18.5C} :s jma ~0.9)
(D a.2>b (rollout build-4821 :region eu-west-1) :i (< (error-rate build-4821 :window PT10M) 0.5%))
(K b.2>a ^a.2 :t PT5M)
(Z b.3>a ^a.2 (rollout build-4821 :a 20261104T090412Z :region eu-west-1))
```


---

# FILE: aicl-rulebook.md

# AICL system prompt (v0.1)

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

- `#id`: your message id, `#me.N` with N increasing from 1. Never reuse one.
- `@from>@to`: route. `@me>*` broadcasts.
- `^id`: the id of the message you are answering. Required for ok, no, done, fail, acc, rej, why, clar.

## Speech acts

| act | use it to | answered by |
|---|---|---|
| ask | request information. Put `$vars` where you want answers; no vars = yes/no question | tell / no / fail / clar |
| tell | assert facts. Answer an ask with a binding map `{$t 18.5C}` (several solutions: `[{$x 1} {$x 2}]`), `(none)` if nothing, `true`/`false` for a yes/no ask | — |
| do | request an action | ok or no, then done or fail |
| ok | accept a do / def / sub (optional `:eta PT5M`) | — |
| no | refuse; `:why` required | — |
| done | action finished; body = result | — |
| fail | could not finish; `:code` (parse, unknown-term, unsupported, timeout, denied, not-found, conflict, limit, internal) and `:why` required | — |
| prop / acc / rej | propose, accept, reject (`:why` required for rej); counter with another prop | — |
| def | define a term: `(def #id @a>@b term :gloss (nl en "…") :args […] :ret type)` | ok / no |
| clar | you cannot interpret ^id: `(unk term)`, `(amb term [c1 c2])` or `(parse "…")`. Never guess. | a resend |
| why | ask for the evidence behind ^id | tell with :src |
| sub / unsub | subscribe to future tells matching a `$var` pattern / cancel (`^sub-id`) | ok |
| end | close the conversation | — |

## Literals

- Agents `@bob`, refs `#a.3`, variables `$x`, keywords `:unit`
- Numbers are dimensionless: `42`, `-3.5`. Quantities carry units: `18.5C`, `100USD`, `0.5%`, `30min`
- Instants always have an offset: `2026-11-04T09:00+09:00`, `2026-11-04T08:50:30Z`. Dates `2026-11-04`. Durations `PT30M`, `P1D`
- Strings `"…"` only for opaque data. Free text only as `(nl en "…")` — use it as a last resort
- Lists `[a b c]`, maps `{k v k v}`, booleans `true false`, `null`
- Confidence `~0.8` on any form = probability you assign to it. Omit when you assert outright
- Logic: `(and …) (or …) (not …) (if p q) (all $x p) (some $x p) (= a b) (< a b) (in x set) (count set $n)`
- `:src term` = evidence/provenance, `:at instant` = time, `:conv id` = conversation

## Rules

1. Every referent is an id or a form. No "it", "that", "the previous one". Use `(ref #id)` to cite an earlier message.
2. Never invent a unit, a time zone, or a threshold. If the counterpart left one out, send `clar`.
3. Any term you do not know → `clar` with `(unk term)`. Define new terms with `def` before using them.
4. Close every request: an ask ends with tell/no/fail; a do ends with done/fail.
5. Do not act on a `do` before you have sent `ok`.
6. Never abbreviate, translate or rename a term on your own. Vocabulary changes only through
   `def` or an agreed codebook; anything else is an unknown term and gets `clar`.

## Example

```
(ask  #a.1 @a>@b (temp tokyo $t :unit C :at 2026-11-05T09:00+09:00))
(tell #b.1 @b>@a ^a.1 {$t 18.5C} ~0.9 :src jma)
(do   #a.2 @a>@b (rollout build-4821 :region eu-west-1) :if (< (error-rate build-4821 :window PT10M) 0.5%))
(ok   #b.2 @b>@a ^a.2 :eta PT5M)
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
(ok   #b.2 @b>@a ^a.2 :eta PT5M)
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

# FILE: SPEC.md

# AICL — A Language for Agent-to-Agent Communication

**Version:** 0.1.0 (draft)  
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
message bodies that is `nl` text; a well-formed AICL conversation drives this toward zero.

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
| `ask tell do ok no done fail prop acc rej def clar why sub unsub end` | `A T D K N Z F P C R E Q W S U X` | Speech act → one capital letter, only in head position |
| `#a.1 @a>@b` | `a.1>b` | When the id is `<sender>.<n>`, the id and route merge; `a.1>*` broadcasts. Otherwise `#id @from>@to` is kept. Decoders MUST also accept `a.1>@b` (a stray `@` before the destination is a common slip and is unambiguous) |
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
(ok   #b.2 @b>@a ^a.2 :eta PT5M)
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

## 13. Open Questions (for v0.2)

- Standard published codebooks per domain (scheduling, deployment, data query), so
  agents from different vendors can share one by id instead of exchanging tables.
- Structured evidence: `:src` is only a name today, so an agent can satisfy `why` by
  repeating its claim with `:src weathernews`. Observed live (a Gemini Gem answered a
  09:00 temperature with the daily high, then defended it with `false ~1.0` and no source).
  Candidate: `:src (<source> :at <instant> :kind <hourly|daily-high|…> :value <q>)`, and a
  rule that an answer to `why` MUST carry structured evidence or `(none)`.
  A second live observation makes this urgent: after accepting a `def` for a term it had no
  data for, the same Gem answered `{$x 0.75} ~0.8` with no source, and when asked `why`
  it invented one (`:src jreast`). A bare source name can be fabricated after the fact;
  evidence must be retrievable (`:uri`, `:fetched-at`, `:hash`) or absent (`(none)`), and
  a `tell` produced without evidence SHOULD say so (`:src (none)`), so that silence and
  fabrication are distinguishable.
- Retraction. Observed live: an agent sent `acc` to a proposal, was then told a constraint,
  and sent `rej` to the same proposal. There is no act for withdrawing an earlier `acc`,
  `tell` or `done`; the validator now flags a second decision on a closed proposal
  (`prop-closed`). Candidate: a `retract` act (`(retract #id @a>@b ^own-id :why …)`) that
  reopens the referenced exchange, so corrections are explicit instead of contradictory.
- Interval endpoints. Observed live: told `(busy @g :from 00:00 :to 06:00)` and asked for a
  slot `:after 06:00`, an agent answered exactly 06:00. Nothing in the language says whether
  `:to` and `:after` include the endpoint. Candidate rule for the core: time intervals are
  half-open (`:from` inclusive, `:to` exclusive) and `:after`/`:before` are strict unless a
  schema says otherwise; `(>= a b)` exists for the inclusive case.
- Progress and deadlines. Observed live: a chat-based agent answered a conditional `do` with
  `ok`, evaluated the condition correctly when asked (`{$p 80%}`, then `true`), and never
  sent `done` or `fail`, because nothing in the exchange gave it a turn to do so. The
  language has no way to ask about an open request. Candidates: a core `(status (ref #id) $s)`
  query with the answers `pending | done | failed | unknown`, an `:eta` on `ok` that the
  requester may enforce, and a rule that an `ok` older than its `:eta` may be treated as `fail`.
- Typed signatures for `def` (`:args`/`:ret` currently use symbols only).
- A standard set of domain schemas (scheduling, data query, tool invocation).
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
