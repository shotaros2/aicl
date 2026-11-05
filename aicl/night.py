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
             limits: Limits, known_terms=(), echo=print) -> TaskOutcome:
    owner = OwnerNode()
    nodes = [owner] + make_nodes(out_dir)
    net = Network(nodes, limits, known_terms=known_terms, echo=echo)
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


def write_report(day_dir: Path, outcomes: List[TaskOutcome], started: datetime) -> Path:
    mark = {"done": "完了", "fail": "できなかった", "unfinished": "未完了"}
    lines = [f"# 夜間作業の報告 {started.strftime('%Y-%m-%d')}", "",
             f"開始 {started.strftime('%H:%M')}、終了 {datetime.now(JST).strftime('%H:%M')}。"
             f"タスク {len(outcomes)} 件。起動後に人の入力はありません。", ""]
    for o in outcomes:
        errors = [i for i in o.run.issues if i.level == "error"]
        rejected = [n for n in o.run.notes if "invalid" in n]
        lines += [f"## {o.name}: {mark[o.status]}", "", f"> {o.text.strip()}", ""]
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


def night_shift(inbox: Path, out_root: Path, make_nodes: Callable[[Path], List[Node]],
                limits: Limits = None, max_tasks: int = 5, known_terms=(), echo=print) -> Optional[Path]:
    """Run every task file in `inbox` (oldest first, at most `max_tasks`); return the report path."""
    inbox.mkdir(parents=True, exist_ok=True)
    tasks = sorted(inbox.glob("*.txt"), key=lambda p: p.stat().st_mtime)[:max_tasks]
    if not tasks:
        echo("no tasks in the inbox")
        return None
    started = datetime.now(JST)
    day_dir = out_root / started.strftime("%Y-%m-%d_%H%M")
    done_dir = inbox.parent / "done"
    done_dir.mkdir(parents=True, exist_ok=True)
    outcomes = []
    for t in tasks:
        text = t.read_text(encoding="utf-8").strip()
        echo(f"=== task {t.stem}: {text[:80]}")
        try:
            o = run_task(t.stem, text, day_dir / t.stem, make_nodes, limits or Limits(), known_terms, echo)
        except Exception as e:  # one broken task must not cost the rest of the night
            echo(f"!! task {t.stem} crashed: {e}")
            continue
        outcomes.append(o)
        shutil.move(str(t), str(done_dir / f"{started.strftime('%Y%m%d')}-{t.name}"))
    return write_report(day_dir, outcomes, started)
