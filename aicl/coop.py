"""Cooperation layer (schemas/cooperation.md): bus, specialist agents, hub, planners.

Specialists with different strengths (image, video, code, …) cooperate through AICL
only. The bus validates every message; the hub plans, delegates in dependency order
and hands the artifacts back. No network, no LLM required: plug those in through
SkillAgent functions, LLMAgent and LLMPlanner.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Union

from .build import form, msg, nl
from .dense import expand as dense_expand
from .model import Agent as AgentId, Form, KList, KMap, Keyword, Message, ParseError, Ref, ReplyRef, Str, Symbol, Term, Var
from .parser import parse, parse_one
from .printer import to_text
from .validate import Issue, validate_conversation, validate_message


def _seq_of(mid: str, agent_id: str) -> int:
    """Numeric suffix of '<agent>.<n>' ids, so an LLM agent's own numbering stays monotonic."""
    try:
        prefix, n = mid.rsplit(".", 1)
        return int(n) if prefix == agent_id else 0
    except ValueError:
        return 0

NS = "coop"


def T(name: str) -> str:
    return f"{NS}:{name}"


class ProtocolError(Exception):
    def __init__(self, issues: List[Issue]):
        super().__init__("; ".join(str(i) for i in issues))
        self.issues = issues


# ------------------------------------------------------------------ helpers

def _is(term: Term, head: str) -> bool:
    return isinstance(term, Form) and term.head == T(head)


def _key(k: Term) -> str:
    if isinstance(k, (Symbol, Keyword)):
        return k.name
    if isinstance(k, Str):
        return k.text
    return to_text(k)


def kmap_to_dict(m: Optional[KMap]) -> Dict[str, Term]:
    return {_key(k): v for k, v in (m.items if m else [])}


def dict_to_kmap(d: Dict[str, Term]) -> KMap:
    return KMap([(Symbol(k), v) for k, v in d.items()])


def artifact(aid: str, type_: str, task: str, uri: str = None, content: str = None,
             mime: str = None, hash_: str = None) -> Form:
    kw: Dict[str, Term] = {"type": Symbol(type_), "task": Symbol(task)}
    if uri is not None:
        kw["uri"] = Str(uri)
    if content is not None:
        kw["content"] = Str(content)
    if mime is not None:
        kw["mime"] = Str(mime)
    if hash_ is not None:
        kw["hash"] = Str(hash_)
    return form(T("artifact"), Symbol(aid), kw=kw)


# -------------------------------------------------------------------- agents

class Agent:
    """Base: an id, a message counter and a handler that returns reply forms."""

    def __init__(self, agent_id: str, capabilities: Iterable[str] = ()):
        self.id = agent_id
        self.capabilities = list(capabilities)
        self.seq = 0
        self.bus: Optional["Bus"] = None

    def _next(self) -> str:
        self.seq += 1
        return f"{self.id}.{self.seq}"

    def msg(self, act: str, to: str, *body, reply: str = None, conf: float = None, kw: dict = None) -> Form:
        return msg(act, self._next(), self.id, to, *body, reply=reply, conf=conf, kw=kw)

    def announce(self, to: str = "*") -> List[Form]:
        return [self.msg("tell", to, form(T("capability"), Symbol(skill), kw={"agent": AgentId(self.id)}))
                for skill in self.capabilities]

    def handle(self, m: Message) -> List[Form]:
        if m.act == "ask" and m.body and _is(m.body[0], "capability"):
            return self._answer_capability_query(m)
        return []

    def _answer_capability_query(self, m: Message) -> List[Form]:
        q = m.body[0]
        skill_var = next((a for a in q.args if isinstance(a, Var)), None)
        agent_var = q.kw.get("agent") if isinstance(q.kw.get("agent"), Var) else None
        wanted = next((a.name for a in q.args if isinstance(a, Symbol)), None)
        rows = []
        for skill in self.capabilities:
            if wanted and skill != wanted:
                continue
            pairs = []
            if skill_var:
                pairs.append((skill_var, Symbol(skill)))
            if agent_var:
                pairs.append((agent_var, AgentId(self.id)))
            rows.append(KMap(pairs))
        body = form("none") if not rows else (rows[0] if len(rows) == 1 else KList(rows))
        return [self.msg("tell", m.sender, body, reply=m.id)]


SkillFn = Callable[[Dict[str, Term], str], Dict[str, str]]
"""fn(inputs, task_id) -> {"id": ..., "type": ..., "uri"?: ..., "content"?: ..., "mime"?: ..., "hash"?: ...}"""


class SkillAgent(Agent):
    """A specialist wrapping one function; executes coop:task requests for its skill."""

    def __init__(self, agent_id: str, skill: str, fn: SkillFn):
        super().__init__(agent_id, [skill])
        self.skill = skill
        self.fn = fn

    def handle(self, m: Message) -> List[Form]:
        if m.act == "do" and m.body and _is(m.body[0], "task"):
            task = m.body[0]
            tid, skill = task.args[0], task.args[1]
            if not isinstance(skill, Symbol) or skill.name != self.skill:
                return [self.msg("no", m.sender, reply=m.id, kw={"why": form("unk", skill)})]
            out = [self.msg("ok", m.sender, reply=m.id)]
            try:
                r = self.fn(kmap_to_dict(task.kw.get("in")), tid.name)
            except Exception as e:  # the specialist's own failure, reported, never hidden
                out.append(self.msg("fail", m.sender, reply=m.id,
                                    kw={"code": Symbol("internal"), "why": nl("en", str(e)[:200])}))
                return out
            art = artifact(r["id"], r["type"], tid.name, r.get("uri"), r.get("content"), r.get("mime"), r.get("hash"))
            out.append(self.msg("done", m.sender, art, reply=m.id))
            return out
        return super().handle(m)


class LLMAgent(Agent):
    """A specialist or peer backed by a language model that speaks AICL.

    `ask(system, history) -> str` is any provider call; `role` is appended to the dense
    rulebook. Replies are parsed and validated before they enter the bus.
    """

    def __init__(self, agent_id: str, ask: Callable[[str, List[dict]], str], rulebook: str,
                 role: str, capabilities: Iterable[str] = (), attempts: int = 2):
        super().__init__(agent_id, capabilities)
        self.ask = ask
        self.system = rulebook.replace("`me`", f"`{agent_id}`").replace("@me", f"@{agent_id}") + "\n\n" + role
        self.history: List[dict] = []
        self.attempts = attempts
        self.corrections = 0

    def _parse_reply(self, raw: str) -> List[Message]:
        if raw.startswith("```"):
            raw = raw.strip("`").removeprefix("aicl").strip()
        forms = parse(dense_expand(raw))              # the model may answer in dense or readable form
        if not forms:
            raise ParseError("empty reply")
        msgs = []
        for f in forms:
            errors = [i for i in validate_message(f) if i.level == "error"]
            if errors:
                raise ParseError("; ".join(str(e) for e in errors))
            msg_ = Message.from_form(f)
            if msg_.sender != self.id:
                raise ParseError(f"message claims to be from @{msg_.sender}")
            msgs.append(msg_)
        return msgs

    def handle(self, m: Message) -> List[Form]:
        # The harness owns message numbering: tell the model its next id (an AICL comment is valid input),
        # and renumber anyway if the model reuses an id, keeping its own ^reply references consistent.
        nxt = f"{self.id}.{self.seq + 1}"
        incoming = (to_text(m.to_form())
                    + f"\n; next-id {nxt}\n; reply header: {nxt}>{m.sender} ^{m.id}   (dense)  =  #{nxt} @{self.id}>@{m.sender} ^{m.id}   (readable)")
        msgs: List[Message] = []
        error = ""
        for attempt in range(self.attempts):
            # A malformed reply is not guessed at: the validator's verdict goes back to the model as an
            # AICL comment and it gets one more try (SPEC §4.4 'clar' applied to the model itself).
            content = incoming if attempt == 0 else f"; your reply was invalid AICL: {error}\n; resend.\n" + "\n".join(incoming.splitlines()[-2:])
            self.history.append({"role": "user", "content": content})
            raw = self.ask(self.system, self.history).strip()
            self.history.append({"role": "assistant", "content": raw})
            try:
                msgs = self._parse_reply(raw)
                break
            except Exception as e:
                error = str(e)[:200]
                self.corrections += 1
        else:
            return [self.msg("fail", m.sender, reply=m.id, kw={"code": Symbol("parse"), "why": nl("en", error)})]
        renamed: Dict[str, str] = {}
        for msg_ in msgs:
            if _seq_of(msg_.id, self.id) <= self.seq:
                new_id = self._next()
                renamed[msg_.id] = new_id
                msg_.id = new_id
            else:
                self.seq = _seq_of(msg_.id, self.id)
            if msg_.reply in renamed:
                msg_.reply = renamed[msg_.reply]
        return [msg_.to_form() for msg_ in msgs]


# ---------------------------------------------------------------------- bus

class Bus:
    """Synchronous in-process delivery with validation and a transcript."""

    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.transcript: List[Message] = []

    def add(self, *agents: Agent) -> None:
        for a in agents:
            self.agents[a.id] = a
            a.bus = self

    def send(self, f: Form) -> None:
        issues = [i for i in validate_message(f) if i.level == "error"]
        if issues:
            raise ProtocolError(issues)
        m = Message.from_form(f)
        self.transcript.append(m)
        if m.receiver == "*":
            targets = [a for a in self.agents.values() if a.id != m.sender]
        else:
            if m.receiver not in self.agents:
                raise ProtocolError([Issue("error", "no-such-agent", f"@{m.receiver} is not on the bus", m.id)])
            targets = [self.agents[m.receiver]]
        for t in targets:
            for reply in t.handle(m):
                self.send(reply)

    def check(self, known: Iterable[str] = ()) -> List[Issue]:
        return validate_conversation(self.transcript, known)

    def text(self) -> str:
        return "\n".join(to_text(m.to_form()) for m in self.transcript)


# ------------------------------------------------------------------ planning

@dataclass
class TaskRef:
    """Marks an input that is the artifact of another task."""
    task: str


@dataclass
class TaskSpec:
    id: str
    skill: str
    inputs: Dict[str, Union[Term, TaskRef]] = field(default_factory=dict)

    @property
    def needs(self) -> List[str]:
        return [v.task for v in self.inputs.values() if isinstance(v, TaskRef)]

    def to_form(self, artifacts: Dict[str, Form] = None) -> Form:
        kw: Dict[str, Term] = {}
        resolved = {}
        for k, v in self.inputs.items():
            if isinstance(v, TaskRef):
                resolved[k] = artifacts[v.task] if artifacts and v.task in artifacts else form(T("from"), Symbol(v.task))
            else:
                resolved[k] = v
        if resolved:
            kw["in"] = dict_to_kmap(resolved)
        if self.needs:
            kw["needs"] = KList([Symbol(t) for t in self.needs])
        return form(T("task"), Symbol(self.id), Symbol(self.skill), kw=kw)


Planner = Callable[[str, Dict[str, str]], List[TaskSpec]]
"""planner(goal_text, registry{skill: agent_id}) -> ordered TaskSpecs"""


class RecipePlanner:
    """Keyword -> fixed recipe. For demos and tests; a real hub uses LLMPlanner."""

    def __init__(self, recipes: List[tuple]):
        """recipes: [(keywords, lambda goal: [TaskSpec...]), ...]; first match wins."""
        self.recipes = recipes

    def __call__(self, goal: str, registry: Dict[str, str]) -> List[TaskSpec]:
        g = goal.lower()
        for keywords, make in self.recipes:
            if any(k.lower() in g for k in keywords):
                return make(goal)
        return []


class LLMPlanner:
    """Ask a language model for (coop:plan [...]) in AICL; parse and validate it."""

    PROMPT = """You are the planner of an AICL hub. Given a goal and the available skills, answer with ONE
AICL form and nothing else:
(coop:plan [(coop:task <id> <skill> :in {{<key> <value> ...}}) ...])
Use only the skills listed. To pass the result of an earlier task as an input, use the value
(coop:from <task-id>). Ids are t1, t2, ... Strings are double-quoted; quantities carry units (10s, 1920px).
Available skills: {skills}
Goal: {goal}"""

    def __init__(self, ask: Callable[[str], str]):
        self.ask = ask

    def __call__(self, goal: str, registry: Dict[str, str]) -> List[TaskSpec]:
        raw = self.ask(self.PROMPT.format(skills=" ".join(sorted(registry)), goal=goal)).strip()
        plan = parse_one(raw)
        if not _is(plan, "plan") or not plan.args or not isinstance(plan.args[0], KList):
            raise ValueError(f"planner did not return (coop:plan [...]): {raw[:120]}")
        specs = []
        for t in plan.args[0].items:
            if not _is(t, "task") or len(t.args) < 2:
                raise ValueError(f"bad task in plan: {to_text(t)}")
            inputs = {}
            for k, v in kmap_to_dict(t.kw.get("in")).items():
                inputs[k] = TaskRef(v.args[0].name) if _is(v, "from") and v.args else v
            specs.append(TaskSpec(t.args[0].name, t.args[1].name, inputs))
        unknown = {s.skill for s in specs} - set(registry)
        if unknown:
            raise ValueError(f"plan uses skills not in registry: {sorted(unknown)}")
        return specs


# ---------------------------------------------------------------------- hub

@dataclass
class Job:
    requester: str
    goal_id: str
    tasks: Dict[str, TaskSpec]
    order: List[str]
    artifacts: Dict[str, Form] = field(default_factory=dict)
    started: Dict[str, str] = field(default_factory=dict)   # task id -> do message id
    failed: bool = False


class Hub(Agent):
    """Registry + planner + delegation in dependency order."""

    def __init__(self, planner: Planner, agent_id: str = "hub"):
        super().__init__(agent_id)
        self.planner = planner
        self.registry: Dict[str, str] = {}
        self.jobs: Dict[str, Job] = {}
        self.task_of_msg: Dict[str, tuple] = {}   # do message id -> (goal id, task id)

    def handle(self, m: Message) -> List[Form]:
        if m.act == "tell" and m.body and _is(m.body[0], "capability"):
            cap = m.body[0]
            agent = cap.kw.get("agent")
            if cap.args and isinstance(cap.args[0], Symbol) and isinstance(agent, AgentId):
                self.registry[cap.args[0].name] = agent.name
            return []
        if m.act == "do" and m.body and _is(m.body[0], "goal"):
            return self._start(m)
        if m.act in ("done", "fail") and m.reply in self.task_of_msg:
            return self._progress(m)
        return super().handle(m)

    def _goal_text(self, goal: Form) -> str:
        for a in goal.args:
            if isinstance(a, Form) and a.head == "nl" and len(a.args) == 2 and isinstance(a.args[1], Str):
                return a.args[1].text
        return to_text(goal)

    def _start(self, m: Message) -> List[Form]:
        goal = m.body[0]
        try:
            specs = self.planner(self._goal_text(goal), dict(self.registry))
        except Exception as e:
            return [self.msg("fail", m.sender, reply=m.id, kw={"code": Symbol("internal"), "why": nl("en", str(e)[:200])})]
        if not specs:
            return [self.msg("no", m.sender, reply=m.id, kw={"why": form("unk", goal)})]
        missing = sorted({s.skill for s in specs} - set(self.registry))
        if missing:
            return [self.msg("no", m.sender, reply=m.id, kw={"why": form("unk", *[Symbol(s) for s in missing])})]
        job = Job(m.sender, m.id, {s.id: s for s in specs}, [s.id for s in specs])
        self.jobs[m.id] = job
        out = [self.msg("ok", m.sender, reply=m.id),
               self.msg("tell", m.sender, form(T("plan"), KList([s.to_form() for s in specs])))]
        out += self._dispatch(job)
        return out

    def _dispatch(self, job: Job) -> List[Form]:
        out = []
        for tid in job.order:
            spec = job.tasks[tid]
            if tid in job.started or job.failed:
                continue
            if all(n in job.artifacts for n in spec.needs):
                f = self.msg("do", self.registry[spec.skill], spec.to_form(job.artifacts))
                do_id = Message.from_form(f).id
                job.started[tid] = do_id
                self.task_of_msg[do_id] = (job.goal_id, tid)
                out.append(f)
        return out

    def _progress(self, m: Message) -> List[Form]:
        goal_id, tid = self.task_of_msg[m.reply]
        job = self.jobs[goal_id]
        if m.act == "fail":
            job.failed = True
            code = m.kw.get("code", Symbol("internal"))
            return [self.msg("fail", job.requester, reply=goal_id,
                             kw={"code": code, "why": form("ref", Ref(m.id))})]
        art = m.body[0] if m.body and _is(m.body[0], "artifact") else None
        if art is None:
            job.failed = True
            return [self.msg("fail", job.requester, reply=goal_id,
                             kw={"code": Symbol("parse"), "why": nl("en", f"done for {tid} carries no coop:artifact")})]
        job.artifacts[tid] = art
        out = self._dispatch(job)
        if len(job.artifacts) == len(job.tasks):
            out.append(self.msg("done", job.requester, KList([job.artifacts[t] for t in job.order]), reply=goal_id))
        return out
