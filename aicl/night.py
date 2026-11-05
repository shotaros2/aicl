"""Night shift: the autonomous network works through a task inbox while its owner sleeps.

Before bed the owner drops tasks, one per text file, into the inbox. When the shift starts
(by hand, or from the Windows Task Scheduler) each task becomes one AICL network run: @owner
sends `(do … (task (nl ja "…")))` to @chief and then sleeps for real - it refuses every
question with "the owner is asleep; decide within your role". The chief and its team decide
everything else themselves. In the morning `REPORT.md` says, per task, whether it was done,
where the result is, whether the critic's acceptance verifies as a signed agreement, what the
validator found, and which answers the network rejected. Processed task files move to `done/`.
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
    """Sends the task, then answers nothing but refusals; records how the task ended."""

    def __init__(self, name: str = "owner"):
        super().__init__(name, "the person the team works for; asleep, cannot answer questions or approve anything")
        self.outcome: Optional[Message] = None
        self.task_id: Optional[str] = None
        self.forged: List[str] = []

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
                return []
            self.outcome = incoming
            return []
        if incoming.act == "prop":
            return [self.msg("rej", incoming.sender, reply=incoming.id, kw={"why": nl("en", ASLEEP)})]
        if incoming.act in ("ask", "do", "def", "sub"):
            return [self.msg("no", incoming.sender, reply=incoming.id, kw={"why": nl("en", ASLEEP)})]
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


def deliverable_ok(m: Message) -> bool:
    """True when the done's blob names a local file whose bytes have exactly the stated hash and size."""
    import hashlib
    path = _blob_path(m)
    b = m.body[0] if m.body else None
    if path is None or not path.is_file() or not isinstance(b, Form):
        return False
    data = path.read_bytes()
    stated = b.args[0].name if b.args and isinstance(b.args[0], Symbol) else str(b.args[0]) if b.args else ""
    size = b.kw.get("bytes")
    return stated == "sha256:" + hashlib.sha256(data).hexdigest() and (size is None or str(size) == str(len(data)))


def _blob_path(m: Message) -> Optional[Path]:
    from urllib.parse import unquote, urlparse
    b = m.body[0] if m.body else None
    if isinstance(b, Form) and b.head == "blob" and "uri" in b.kw:
        u = urlparse(b.kw["uri"].text)
        if u.scheme == "file":
            p = unquote(u.path)
            if len(p) > 2 and p[0] == "/" and p[2] == ":":      # /C:/Users/… on Windows
                p = p[1:]
            return Path(p)
    return None


def run_task(name: str, text: str, out_dir: Path, make_nodes: Callable[[Path], List[Node]],
             limits: Limits, known_terms=(), echo=print, on_message=None) -> TaskOutcome:
    owner = OwnerNode()
    nodes = [owner] + make_nodes(out_dir)
    net = Network(nodes, limits, known_terms=known_terms, echo=echo, on_message=on_message)
    net.post(owner.task(text))
    res = net.run(wake=[])
    res.save(out_dir)
    ags = extract_agreements(res.messages, keys=res.keys or None, known_terms=known_terms)
    verified = any(a.verified for a in ags)
    o = owner.outcome
    if o is None:
        return TaskOutcome(name, text, "unfinished", None, res, verified, res.stopped, owner.forged)
    if o.act in ("fail", "no"):
        why = o.kw.get("why")
        from .skills import _text_of
        return TaskOutcome(name, text, "fail", None, res, verified, _text_of(why) if why is not None else "",
                           owner.forged)
    return TaskOutcome(name, text, "done", _blob_path(o), res, verified, "", owner.forged)


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
        rejected = [n for n in o.run.notes if "invalid" in n]
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
        if o.forged:
            lines.append(f"- 中身と一致しない「納品」を無視: {len(o.forged)} 件（{', '.join('#' + f for f in o.forged)}）")
        for n in o.run.notes:
            if "invalid" not in n and "ignored #" not in n:
                lines.append(f"- メモ: {n}")
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
                memory=None, on_message=None) -> Optional[Path]:
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
                o = run_task(name, text, day_dir / name, make_nodes, limits, known_terms, echo, on_message)
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
