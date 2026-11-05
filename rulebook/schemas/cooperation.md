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

## Retrospective: advice between teammates

After a task, the agents that took part may each propose **one** piece of advice to another
agent that took part. The receiver decides; nothing is imposed.

| Form | Meaning |
|---|---|
| `(prop … (advice (nl lang "…")))` | "Next time, do this differently." Concrete and short; never about rules, permissions or where facts come from. |
| `(acc … ^<prop>)` | Taken on. In `aicl/night.py` it is stored in `lessons.jsonl` and added below the receiver's role on later tasks (the newest five), worded as advice that never overrides the role or the network's rules. |
| `(rej … ^<prop> :why …)` | Declined, with the reason. |

`advice` is a plain term the night shift's agents know by agreement (its `known_terms`), not a
`coop:` term. Worked example: `examples/24_retro_advice.aicl`. The owner can drop any lesson by
deleting its line.

## Planning

The hub's planner is pluggable. The reference implementation ships a `RecipePlanner`
(keyword → fixed recipe, for demos and tests) and an `LLMPlanner` that asks a language
model for a `(coop:plan …)` in AICL and validates it before use. Any planner must only
use skills present in the registry.
