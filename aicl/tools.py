"""More specialists for the network: calculation, exchange rates, news, and the team's memory.

- calc: arithmetic and dates, computed (never estimated): (calc "634/333" $x), (days-between d1 d2 $n),
  (weekday d $w). Only numbers and + - * / // % ** ( ) are accepted - no names, no calls.
- fx: exchange rates from the European Central Bank via frankfurter (no key): (fx-rate USD JPY $r).
- news: current headlines from Google News's public RSS feeds (Japan edition), each with its link
  and publication time: (headlines $h :topic science).
- memory: what the team has done on earlier nights, kept in a local JSON-lines file:
  (recent $m), (recall (nl ja "スカイツリー") $m). The night shift writes to it; agents only read.

All are SkillNodes: no model, no judgment, read-only towards the outside world. Every answer from
outside data carries a :src; no data is `(unk data)`; anything malformed gets `clar`.
"""
from __future__ import annotations

import ast
import json
import operator
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, List

from . import tls
from .build import form
from .model import Form, KList, KMap, Message, Str, Symbol, Var
from .network import SkillNode
from .parser import parse
from .printer import to_text
from .skills import _text_of

JST = timezone(timedelta(hours=9))
UA = "aicl-network/0.3 (https://github.com/shotaros2/aicl)"


def _now_term():
    return parse(datetime.now(JST).strftime("%Y-%m-%dT%H:%M+09:00"))[0]


def _src(uri: str, kind: str) -> Form:
    return Form("source", [], {"uri": Str(uri), "kind": Symbol(kind), "at": _now_term()})


def _get(url: str) -> str:
    with tls.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def _q(m: Message):
    return m.body[0] if m.body and isinstance(m.body[0], Form) else None


def _var(q: Form):
    return next((a for a in q.args if isinstance(a, Var)), None)


def _refuse_non_ask(node: SkillNode, m: Message) -> List[Form]:
    if m.act in ("do", "prop", "def", "sub"):
        return [node.msg("no", m.sender, reply=m.id, kw={"why": form("unsupported", Symbol(m.act))})]
    return []


def _clar(node, m, what):
    return [node.msg("clar", m.sender, form("unk", Symbol(what)), reply=m.id)]


def _tell(node, m, var, value, src=None):
    return [node.msg("tell", m.sender, KMap([(var, value)]), reply=m.id, kw={"src": src} if src is not None else None)]


def _num(x: float):
    x = round(x, 6)
    return parse(f"{int(x)}" if float(x).is_integer() else f"{x:g}")[0]


# --------------------------------------------------------------------- calc

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
        ast.USub: operator.neg, ast.UAdd: operator.pos}


def safe_eval(expr: str) -> float:
    """Evaluate arithmetic only: numbers and + - * / // % ** with parentheses. Anything else is rejected."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            l, r = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(r) > 100 or abs(l) > 1e6):
                raise ValueError("exponent too large")
            return _OPS[type(n.op)](l, r)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        raise ValueError(f"not arithmetic: {type(n).__name__}")
    if len(expr) > 200:
        raise ValueError("expression too long")
    return ev(ast.parse(expr.replace("×", "*").replace("÷", "/"), mode="eval"))


def _date(t) -> date:
    return date.fromisoformat(to_text(t)[:10])


def calc_node(name: str = "calc") -> SkillNode:
    def handler(node, m):
        if m.act != "ask":
            return _refuse_non_ask(node, m)
        q = _q(m)
        if q is None or q.head not in ("calc", "days-between", "weekday"):
            return _clar(node, m, q.head if q is not None else "query")
        var = _var(q)
        args = [a for a in q.args if not isinstance(a, Var)]
        try:
            if q.head == "calc":
                value = _num(safe_eval(_text_of(args[0])))
            elif q.head == "days-between":
                value = _num((_date(args[1]) - _date(args[0])).days)
            else:
                value = Symbol(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][_date(args[0]).weekday()])
        except (ValueError, IndexError, ZeroDivisionError, SyntaxError) as e:
            return [node.msg("clar", m.sender, form("parse", Str(str(e)[:120])), reply=m.id)]
        if var is None:
            return [node.msg("clar", m.sender, form("parse", Str("put a $var where the answer goes")), reply=m.id)]
        return _tell(node, m, var, value)

    return SkillNode(name, "calculator (no model): exact arithmetic and date arithmetic; use it instead of "
                           "computing in your head", handler,
                     offers=['(A x.1>calc (calc "(634-333)/333*100" $x))', "(A x.2>calc (days-between 2026-11-05 2026-12-25 $n))",
                             "(A x.3>calc (weekday 2026-12-25 $w))"])


# ----------------------------------------------------------------------- fx

def fx_node(name: str = "fx", fetch: Callable[[str], str] = _get) -> SkillNode:
    def handler(node, m):
        if m.act != "ask":
            return _refuse_non_ask(node, m)
        q = _q(m)
        if q is None or q.head != "fx-rate":
            return _clar(node, m, q.head if q is not None else "query")
        codes = [a.name.upper() for a in q.args if isinstance(a, Symbol)]
        var = _var(q)
        if len(codes) != 2 or var is None or not all(re.fullmatch(r"[A-Z]{3}", c) for c in codes):
            return [node.msg("clar", m.sender, form("parse", Str("expected (fx-rate USD JPY $r)")), reply=m.id)]
        url = "https://api.frankfurter.dev/v1/latest?" + urllib.parse.urlencode({"base": codes[0], "symbols": codes[1]})
        data = json.loads(fetch(url))
        rate = (data.get("rates") or {}).get(codes[1])
        if rate is None:
            return [node.msg("no", m.sender, reply=m.id, kw={"why": form("unk", Symbol("data"))})]
        value = Form("fx", [], {"from": Symbol(codes[0]), "to": Symbol(codes[1]), "rate": _num(rate),
                                "date": parse(data.get("date", ""))[0] if data.get("date") else Symbol("unknown")})
        return _tell(node, m, var, value, _src(url, "exchange-rate"))

    return SkillNode(name, "exchange rates (no model) from the European Central Bank's reference rates; "
                           "updated once per working day", handler, offers=["(A x.1>fx (fx-rate USD JPY $r))"])


# --------------------------------------------------------------------- news

TOPICS = {"main": None, "nation": "NATION", "world": "WORLD", "business": "BUSINESS", "technology": "TECHNOLOGY",
          "science": "SCIENCE", "health": "HEALTH", "entertainment": "ENTERTAINMENT", "sports": "SPORTS"}
GN = "hl=ja&gl=JP&ceid=JP:ja"


def news_node(name: str = "news", fetch: Callable[[str], str] = _get, limit: int = 8) -> SkillNode:
    def handler(node, m):
        if m.act != "ask":
            return _refuse_non_ask(node, m)
        q = _q(m)
        if q is None or q.head != "headlines":
            return _clar(node, m, q.head if q is not None else "query")
        var = _var(q)
        topic = q.kw["topic"].name if isinstance(q.kw.get("topic"), Symbol) else "main"
        if var is None or topic not in TOPICS:
            return [node.msg("clar", m.sender, form("parse", Str("expected (headlines $h :topic " + "|".join(TOPICS) + ")")),
                             reply=m.id)]
        url = (f"https://news.google.com/rss?{GN}" if TOPICS[topic] is None
               else f"https://news.google.com/rss/headlines/section/topic/{TOPICS[topic]}?{GN}")
        xml = fetch(url)
        rows = []
        for item in re.findall(r"(?s)<item>(.*?)</item>", xml)[:limit]:
            title = re.search(r"(?s)<title>(.*?)</title>", item)
            link = re.search(r"(?s)<link>(.*?)</link>", item)
            if title and link:
                t = re.sub(r"<!\[CDATA\[|\]\]>", "", title.group(1)).strip()
                kw = {"title": Str(t), "uri": Str(link.group(1).strip())}
                pub = re.search(r"(?s)<pubDate>(.*?)</pubDate>", item)
                if pub:   # feeds can be stale: the date lets agents tell old news from new
                    from email.utils import parsedate_to_datetime
                    try:
                        kw["at"] = parse(parsedate_to_datetime(pub.group(1).strip()).astimezone(JST)
                                         .strftime("%Y-%m-%dT%H:%M+09:00"))[0]
                    except (TypeError, ValueError):
                        pass
                rows.append(Form("headline", [], kw))
        if not rows:
            return [node.msg("no", m.sender, reply=m.id, kw={"why": form("unk", Symbol("data"))})]
        return _tell(node, m, var, KList(rows), _src(url, "news-feed"))

    return SkillNode(name, "current news headlines (no model) from Google News (Japan), each with its link and "
                           "time; topics: " + ", ".join(TOPICS) + "; headlines only - open a link with @reader for details", handler,
                     offers=["(A x.1>news (headlines $h :topic science))"])


# ------------------------------------------------------------------- memory

class Memory:
    """The team's memory across nights: one JSON object per line, written by the night shift."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def add(self, **entry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry.setdefault("at", datetime.now(JST).strftime("%Y-%m-%dT%H:%M+09:00"))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def all(self) -> List[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out


def memory_node(memory: Memory, name: str = "memory", limit: int = 10) -> SkillNode:
    def row(e: dict) -> Form:
        kw = {"task": Form("nl", [Symbol("ja"), Str(e.get("task", ""))]), "status": Symbol(e.get("status", "unknown")),
              "at": parse(e["at"])[0] if e.get("at") else Symbol("unknown"), "by": Symbol(e.get("by", "owner"))}
        if e.get("title"):
            kw["title"] = Str(e["title"])
        return Form("done-before", [], kw)

    def handler(node, m):
        if m.act != "ask":
            return _refuse_non_ask(node, m)
        q = _q(m)
        if q is None or q.head not in ("recent", "recall"):
            return _clar(node, m, q.head if q is not None else "query")
        var = _var(q)
        if var is None:
            return [node.msg("clar", m.sender, form("parse", Str("put a $var where the answer goes")), reply=m.id)]
        entries = memory.all()
        if q.head == "recall":
            words = [w for w in re.split(r"\s+", _text_of(next((a for a in q.args if not isinstance(a, Var)), Str("")))) if w]
            entries = [e for e in entries if any(w in (e.get("task", "") + e.get("title", "")) for w in words)]
        rows = [row(e) for e in entries[-limit:]]
        return _tell(node, m, var, KList(rows) if rows else Form("none", []))

    return SkillNode(name, "the team's memory (no model): what was done on earlier nights - task, who asked, "
                           "status, page title; ask before proposing work, to avoid repeating it", handler,
                     offers=["(A x.1>memory (recent $m))", '(A x.2>memory (recall (nl ja "スカイツリー") $m))'])
