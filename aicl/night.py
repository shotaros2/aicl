"""Night shift: the autonomous network works through a task inbox while its owner sleeps.

Before bed the owner drops tasks, one per text file, into the inbox. When the shift starts
(by hand, or from the Windows Task Scheduler) each task becomes one AICL network run: @owner
sends `(do … (task (nl ja "…")))` to @chief and then sleeps for real - it refuses every
question with "the owner is asleep; decide within your role". The chief and its team decide
everything else themselves. In the morning `REPORT.md` says, per task, whether it was done,
where the result is, whether the critic's acceptance verifies as a signed agreement, what the
validator found, and which answers the network rejected. Processed task files move to `done/`.

After each task the agents that took part hold a retrospective: each may propose one piece of
advice to a teammate as `(prop … (advice (nl ja "…")))`, and the teammate accepts or rejects
it. Accepted advice goes to `lessons.jsonl` and below that agent's role on later tasks.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, List, Optional

from .agreement import extract_agreements
from .build import nl
from .model import Form, Message, Symbol
from .network import Limits, Network, NetworkResult, Node

JST = timezone(timedelta(hours=9))
ASLEEP = "the owner is asleep and cannot answer; decide within your role"


class OwnerNode(Node):
    """Sends the task, then answers nothing but refusals; records how the task ended.

    Each refusal says how to end the task (done or fail in reply to it), and after `max_refusals`
    the owner stops answering, so the network goes quiet. Seen on the home PC (2026-11-05): a
    local chief reported failure as an ask to @owner, got the refusal, and asked again until its
    24 calls were gone.
    """

    def __init__(self, name: str = "owner", max_refusals: int = 3):
        super().__init__(name, "the person the team works for; asleep, cannot answer questions or approve anything")
        self.outcome: Optional[Message] = None
        self.task_id: Optional[str] = None
        self.forged: List[str] = []
        self.max_refusals = max_refusals
        self.refusals = 0

    def _why(self):
        end = (f"; to finish, answer #{self.task_id} with done (carrying the blob) or with fail and a :why"
               if self.task_id else "")
        return nl("en", ASLEEP + end)

    def _refuse(self, net, act: str, incoming: Message, why=None):
        self.refusals += 1
        if self.refusals > self.max_refusals:
            if self.refusals == self.max_refusals + 1:
                net.note(f"@{self.name} stopped answering after {self.max_refusals} refusals")
            return []
        return [self.msg(act, incoming.sender, reply=incoming.id, kw={"why": why or self._why()})]

    def task(self, text: str, to: str = "chief") -> Form:
        f = self.msg("do", to, Form("task", [nl("ja", text)]))
        self.task_id = f"{self.name}.{self.seq}"
        return f

    def react(self, net, event, incoming):
        if incoming is None:
            return []
        if incoming.reply == self.task_id and incoming.act in ("done", "fail", "no") and self.outcome is None:
            if incoming.act == "done" and not deliverable_ok(incoming):
                # A done whose blob names no file, or a file with other bytes, is not a deliverable,
                # however well-formed: it is noted and ignored, and the real one is still awaited.
                self.forged.append(incoming.id)
                net.note(f"@{self.name} ignored #{incoming.id}: its blob does not match any file it names")
                # Said back to the sender, or the network falls quiet with the task unfinished (seen live).
                return self._refuse(net, "no", incoming, nl(
                    "en", "not accepted: a done must carry the blob @desk returned for the published file; "
                          f"publish through @desk what was accepted, then answer #{self.task_id} with done "
                          "carrying that blob, or with fail and a :why"))
            self.outcome = incoming
            return []
        if incoming.act == "prop":
            return self._refuse(net, "rej", incoming)
        if incoming.act in ("ask", "do", "def", "sub"):
            return self._refuse(net, "no", incoming)
        return []


class ProposalBox(Node):
    """Stands in for @chief while the scout looks around: records the tasks the scout proposes."""

    def __init__(self, limit: int = 2, name: str = "chief"):
        super().__init__(name, "the team lead; takes task proposals as (do … (task (nl ja \"…\")))")
        self.limit = limit
        self.tasks: List[str] = []

    def react(self, net, event, incoming):
        if incoming is None or incoming.act != "do":
            return []
        t = incoming.body[0] if incoming.body else None
        text = t.args[0].args[1].text if (isinstance(t, Form) and t.head == "task" and t.args and isinstance(t.args[0], Form)
                                          and t.args[0].head == "nl" and len(t.args[0].args) > 1) else None
        if text is None:
            return [self.msg("no", incoming.sender, reply=incoming.id, kw={"why": nl("en", 'expected (task (nl ja "…"))')})]
        if len(self.tasks) >= self.limit:
            return [self.msg("no", incoming.sender, reply=incoming.id, kw={"why": nl("en", f"at most {self.limit} proposals a night")})]
        self.tasks.append(text.strip())
        return [self.msg("ok", incoming.sender, reply=incoming.id)]


def scout_session(make_scout_nodes: Callable[[], List[Node]], limits: Limits, max_tasks: int = 2,
                  known_terms=(), echo=print, on_message=None):
    """Wake the scout among the read-only specialists; return (proposed task texts, run)."""
    box = ProposalBox(max_tasks)
    net = Network([box] + make_scout_nodes(), limits, known_terms=known_terms, echo=echo, on_message=on_message)
    res = net.run(wake=["scout"])
    return box.tasks, res


@dataclass
class TaskOutcome:
    name: str
    text: str
    status: str                      # done | fail | unfinished
    result: Optional[Path]
    run: NetworkResult
    verified: bool
    why: str = ""
    forged: List[str] = None
    by: str = "owner"                # who asked: the owner (inbox) or the scout (its own idea)
    retro: List[dict] = None         # advice the agents gave each other after the task (see retrospective)


def deliverable_ok(m: Message) -> bool:
    """True when the done's blob names a local file whose bytes have exactly the stated hash and size."""
    import hashlib
    path = _blob_path(m)
    b = _find_blob(m)
    if path is None or not path.is_file() or b is None:
        return False
    data = path.read_bytes()
    stated = b.args[0].name if b.args and isinstance(b.args[0], Symbol) else str(b.args[0]) if b.args else ""
    size = b.kw.get("bytes")
    return stated == "sha256:" + hashlib.sha256(data).hexdigest() and (size is None or str(size) == str(len(data)))


def _find_blob(m: Message) -> Optional[Form]:
    """The done's blob: a body term, or one level inside one - seen live, a chief wrapped the
    right blob as (doc :blob (blob …) :title …), and another sent (task …) (blob …), and a
    finished task was reported unfinished."""
    for b in m.body:
        if not isinstance(b, Form):
            continue
        if b.head == "blob":
            return b
        for v in list(b.args) + list(b.kw.values()):
            if isinstance(v, Form) and v.head == "blob":
                return v
    return None


def _blob_path(m: Message) -> Optional[Path]:
    from urllib.parse import unquote, urlparse
    b = _find_blob(m)
    if b is not None and "uri" in b.kw:
        u = urlparse(b.kw["uri"].text)
        if u.scheme == "file":
            p = unquote(u.path)
            if len(p) > 2 and p[0] == "/" and p[2] == ":":      # /C:/Users/… on Windows
                p = p[1:]
            return Path(p)
    return None


RETRO = (
    "; retro: the task is over ({status}). You are @{me}. Teammates who took part: {team}.\n"
    "; You may propose ONE piece of advice to ONE of them: what THAT teammate should do differently in "
    "its own job next time, concrete and one sentence, as (P {me}.N>them (advice (nl ja \"…\"))). Never to "
    "@owner or a specialist; never about rules, permissions or sources of facts.\n"
    "; Advice proposed to you is for you, @{me}: answer it with exactly one message, "
    "(C {me}.N>them ^<their prop id>) if following it in your own job would have made this task go better, "
    "or (R {me}.N>them ^<their prop id> :w (nl ja \"why not\")) if not. Never send end (X); do not repeat "
    "or ask about advice.\n"
    "; If you have nothing to propose or answer, reply with the single comment line: ; nothing")


class Lessons:
    """Advice an agent accepted from a teammate in a retrospective, kept in a JSON-lines file and
    added below that agent's role on later tasks (the newest `keep`). It is advice, never a rule:
    the role says it ranks below the role and the network's rules. Delete a line to drop one."""

    def __init__(self, path: Path, keep: int = 5):
        self.path, self.keep = Path(path), keep

    def all(self) -> List[dict]:
        import json
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def add(self, **row) -> None:
        import json
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(dict(row, at=datetime.now(JST).isoformat(timespec="minutes")),
                               ensure_ascii=False) + "\n")

    def for_agent(self, name: str) -> List[dict]:
        return [r for r in self.all() if r.get("to") == name][-self.keep:]

    def role_note(self, name: str) -> str:
        rows = self.for_agent(name)
        if not rows:
            return ""
        return ("\n\nAdvice you accepted from teammates after earlier tasks (follow it where it fits; it never "
                "overrides your role or the network's rules):\n"
                + "\n".join(f"- from @{r['from']}: {r['text']}" for r in rows))


def retrospective(net: Network, team: List[str], status: str) -> List[dict]:
    """After a task, each model agent that took part may propose one piece of advice to another;
    the receiver accepts or rejects it. Returns one row per advice: from, to, text, prop, and the
    answer (acc / rej / none) with its id and :why."""
    from .skills import _text_of
    start = len(net.log)
    for n in team:                      # a few calls each, whatever the task used
        node = net.nodes[n]
        node.calls = min(node.calls, max(0, net.limits.max_calls_per_agent - 3))
    def blurb(n):
        return getattr(net.nodes[n], "blurb", None) or net.nodes[n].role[:80]

    # Each agent is told who it is: seen live, Haiku lost track of its own name in a long record
    # and declined advice about its own job as "the chief's job".
    def event(me):
        others = "; ".join(f"@{n} ({blurb(n)})" for n in team if n != me)
        return RETRO.format(status=status, me=me, team=others)
    net.run(wake=team, wake_event=event)
    new = net.log[start:]
    rows, seen = [], set()
    for m in new:
        b = m.body[0] if m.body else None
        if m.act != "prop" or not isinstance(b, Form) or b.head != "advice" or m.sender in seen:
            continue
        if m.receiver not in team or m.receiver == m.sender:
            continue
        seen.add(m.sender)
        text = _text_of(b.args[0]) if b.args else ""
        answer = next((a for a in new if a.reply == m.id and a.sender == m.receiver and a.act in ("acc", "rej")), None)
        why = answer.kw.get("why") if answer is not None else None
        rows.append({"from": m.sender, "to": m.receiver, "text": text, "prop": m.id,
                     "answer": answer.act if answer is not None else "none",
                     "answer_id": answer.id if answer is not None else "",
                     "why": _text_of(why) if why is not None else ""})
    return rows


def run_task(name: str, text: str, out_dir: Path, make_nodes: Callable[[Path], List[Node]],
             limits: Limits, known_terms=(), echo=print, on_message=None,
             lessons: Optional[Lessons] = None, retro: bool = True) -> TaskOutcome:
    owner = OwnerNode()
    nodes = [owner] + make_nodes(out_dir)
    net = Network(nodes, limits, known_terms=known_terms, echo=echo, on_message=on_message,
                  files_dir=out_dir / "files")
    net.post(owner.task(text))
    res = net.run(wake=[])
    ags = extract_agreements(res.messages, keys=res.keys or None, known_terms=known_terms)
    verified = any(a.verified for a in ags)
    o = owner.outcome
    if o is None:
        out = TaskOutcome(name, text, "unfinished", None, res, verified, res.stopped, owner.forged)
    elif o.act in ("fail", "no"):
        why = o.kw.get("why")
        from .skills import _text_of
        out = TaskOutcome(name, text, "fail", None, res, verified, _text_of(why) if why is not None else "",
                          owner.forged)
    else:
        out = TaskOutcome(name, text, "done", _blob_path(o), res, verified, "", owner.forged)
    record = res
    if retro:
        from .network import ModelNode
        team = [n.name for n in nodes if isinstance(n, ModelNode) and any(m.sender == n.name for m in res.messages)]
        if len(team) >= 2:
            echo(f"--- retro: {', '.join('@' + t for t in team)}")
            try:
                out.retro = retrospective(net, team, out.status)
                record = net.run(wake=[])      # nothing queued: a snapshot of the whole record
            except Exception as e:             # the retrospective must never cost the task's result
                echo(f"!! retro failed: {e}")
            for r in out.retro or []:
                if r["answer"] == "acc" and lessons is not None:
                    lessons.add(task=text, **{k: r[k] for k in ("from", "to", "text", "prop", "answer_id")})
    record.save(out_dir)
    return out


def write_report(day_dir: Path, outcomes: List[TaskOutcome], started: datetime,
                 scout: Optional[NetworkResult] = None, proposals: int = 0) -> Path:
    mark = {"done": "完了", "fail": "できなかった", "unfinished": "未完了"}
    own = sum(o.by == "scout" for o in outcomes)
    lines = [f"# 夜間作業の報告 {started.strftime('%Y-%m-%d')}", "",
             f"開始 {started.strftime('%H:%M')}、終了 {datetime.now(JST).strftime('%H:%M')}。"
             f"タスク {len(outcomes)} 件（うち AI が自分で始めたもの {own} 件）。起動後に人の入力はありません。", ""]
    if scout is not None:
        asked = [m for m in scout.messages if m.sender == "scout" and m.act == "ask"]
        lines += [f"スカウトは {len(asked)} 回調べ、仕事を {proposals} 件提案しました"
                  + ("。" if proposals else "（提案に値する仕事はないと判断）。"), ""]
    for o in outcomes:
        errors = [i for i in o.run.issues if i.level == "error"]
        escalated = [n for n in o.run.notes if "escalated to" in n]
        rejected = [n for n in o.run.notes if "invalid" in n and n not in escalated]
        who = "スカウトの提案" if o.by == "scout" else "あなたの依頼"
        lines += [f"## {o.name}: {mark[o.status]}（{who}）", "", f"> {o.text.strip()}", ""]
        if o.result is not None:
            rel = o.result.relative_to(day_dir) if o.result.is_relative_to(day_dir) else o.result
            lines += [f"- 結果: [{rel.as_posix()}]({rel.as_posix()})"]
        if o.why:
            lines += [f"- 理由: {o.why}"]
        lines += [f"- やり取り: {len(o.run.messages)} 通、{o.run.seconds:.0f} 秒（{o.run.stopped}）",
                  f"- チェッカーの受諾（署名付き合意）: {'検証できた' if o.verified else 'なし'}",
                  f"- 検証器: エラー {len(errors)} 件、警告 {len(o.run.issues) - len(errors)} 件",
                  f"- ネットワークが差し戻した不正な返答: {len(rejected)} 件"]
        if escalated:
            lines.append(f"- 手元の AI からクラウドに上げた回数: {len(escalated)} 件（料金がかかった目安）")
            lines += [f"  - {n}" for n in escalated]
        if o.forged:
            lines.append(f"- 中身と一致しない「納品」を無視: {len(o.forged)} 件（{', '.join('#' + f for f in o.forged)}）")
        for n in o.run.notes:
            if "invalid" not in n and "ignored #" not in n and n not in escalated:
                lines.append(f"- メモ: {n}")
        if o.retro is not None:
            took = sum(r["answer"] == "acc" for r in o.retro)
            lines.append(f"- 振り返り（AI 同士の提案）: {len(o.retro)} 件、うち受け入れ {took} 件")
            answer = {"acc": "受け入れ", "rej": "断り", "none": "返事なし"}
            for r in o.retro:
                lines.append(f"  - @{r['from']} → @{r['to']}: 「{r['text']}」 … {answer[r['answer']]}"
                             + (f"（{r['why']}）" if r["why"] else ""))
        lines += [f"- 記録: {o.name}/transcript.aicl（署名の公開鍵は {o.name}/keys.json）", ""]
    path = day_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def _title_of(path: Optional[Path]) -> str:
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0] if path else ""
        return first.lstrip("# ").strip()
    except (OSError, IndexError):
        return ""


class Lock:
    """One shift at a time: a lock file younger than `stale` hours means another run is in progress."""

    def __init__(self, path: Path, stale_hours: float = 4.0):
        self.path, self.stale = Path(path), stale_hours * 3600

    def __enter__(self):
        import time
        if self.path.exists() and time.time() - self.path.stat().st_mtime < self.stale:
            raise RuntimeError(f"another shift is running ({self.path} exists)")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(datetime.now(JST).isoformat(), encoding="utf-8")
        return self

    def __exit__(self, *exc):
        try:
            self.path.unlink()
        except OSError:
            pass


def night_shift(inbox: Path, out_root: Path, make_nodes: Callable[[Path], List[Node]],
                limits: Limits = None, max_tasks: int = 5, known_terms=(), echo=print,
                scout: Optional[Callable[[], List[Node]]] = None, max_scout_tasks: int = 2,
                memory=None, on_message=None, lessons: Optional[Lessons] = None,
                retro: bool = True) -> Optional[Path]:
    """Run the inbox (oldest first, at most `max_tasks`), then, with `scout`, the tasks the scout proposes
    itself. Returns the report path, or None when there was nothing to do and no scout."""
    inbox.mkdir(parents=True, exist_ok=True)
    with Lock(out_root / "RUNNING"):
        files = sorted(inbox.glob("*.txt"), key=lambda p: p.stat().st_mtime)[:max_tasks]
        if not files and scout is None:
            echo("no tasks in the inbox")
            return None
        started = datetime.now(JST)
        day_dir = out_root / started.strftime("%Y-%m-%d_%H%M")
        done_dir = inbox.parent / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        limits = limits or Limits()
        jobs = [(t.stem, t.read_text(encoding="utf-8").strip(), "owner", t) for t in files]
        scout_run, proposals = None, []
        if scout is not None:
            echo("=== scout: looking for work nobody asked for")
            try:
                proposals, scout_run = scout_session(scout, limits, max_scout_tasks, known_terms, echo, on_message)
                scout_run.save(day_dir / "scout")
            except Exception as e:
                echo(f"!! scout crashed: {e}")
            jobs += [(f"scout-{i + 1}", text, "scout", None) for i, text in enumerate(proposals)]
        outcomes = []
        for name, text, by, path in jobs:
            echo(f"=== task {name} ({by}): {text[:80]}")
            try:
                o = run_task(name, text, day_dir / name, make_nodes, limits, known_terms, echo, on_message,
                             lessons=lessons, retro=retro)
            except Exception as e:  # one broken task must not cost the rest of the night
                echo(f"!! task {name} crashed: {e}")
                continue
            o.by = by
            outcomes.append(o)
            if memory is not None:
                memory.add(task=text, status=o.status, by=by, title=_title_of(o.result),
                           result=str(o.result) if o.result else "")
            if path is not None:
                shutil.move(str(path), str(done_dir / f"{started.strftime('%Y%m%d')}-{path.name}"))
        day_dir.mkdir(parents=True, exist_ok=True)
        return write_report(day_dir, outcomes, started, scout_run, len(proposals))
