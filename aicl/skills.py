"""Specialists for the autonomous network (aicl/network.py): real effects, no judgment.

- weather: current conditions and daily forecasts from open-meteo.com (no key), every answer
  carrying a :src that names the exact request it came from, and `(unk data)` when there is none;
- artist: draws one SVG illustration with a text model and returns it as a blob (SPEC §4.5);
- desk: publishes a document as a Markdown file and returns the file's blob.

Each is a SkillNode: it does what it advertises and says no, clar or fail when it cannot.
The model agents decide whether, when and why to call them. Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, List, Optional

from .build import form, nl
from .model import Form, KMap, Message, Str, Symbol, Var
from .network import Ask, SkillNode
from .parser import parse
from .printer import to_text

WMO = {0: "clear", 1: "mainly-clear", 2: "partly-cloudy", 3: "overcast", 45: "fog", 48: "fog",
       51: "drizzle", 53: "drizzle", 55: "drizzle", 56: "freezing-drizzle", 57: "freezing-drizzle",
       61: "rain", 63: "rain", 65: "heavy-rain", 66: "freezing-rain", 67: "freezing-rain",
       71: "snow", 73: "snow", 75: "heavy-snow", 77: "snow-grains", 80: "showers", 81: "showers",
       82: "heavy-showers", 85: "snow-showers", 86: "snow-showers", 95: "thunderstorm",
       96: "thunderstorm", 99: "thunderstorm"}


def http_json(url: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "aicl-network/0.3"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _term(text: str):
    return parse(text)[0]


def _text_of(t) -> str:
    """The prose inside (nl lang "…"), a plain string, or the canonical text of anything else."""
    if isinstance(t, Form) and t.head == "nl" and len(t.args) >= 2 and isinstance(t.args[1], Str):
        return t.args[1].text
    if isinstance(t, Str):
        return t.text
    return to_text(t)


def _blob(data: bytes, media: str, path: Path) -> Form:
    return _term(f'(blob sha256:{hashlib.sha256(data).hexdigest()} :media "{media}" '
                 f':bytes {len(data)} :uri "{path.resolve().as_uri()}")')


def _num(x: float) -> str:
    return f"{x:g}"


# ------------------------------------------------------------------ weather

def weather_node(name: str = "weather", fetch: Callable[[str], dict] = http_json) -> SkillNode:
    """Answers (ask … (weather-now <city> $w)) and (ask … (forecast <city> <date> $f))."""

    def handler(node: SkillNode, m: Message) -> List[Form]:
        if m.act != "ask":
            return [node.msg("no", m.sender, reply=m.id,
                             kw={"why": form("unsupported", Symbol(m.act))})] if m.act in ("do", "prop", "def", "sub") else []
        q = m.body[0] if m.body and isinstance(m.body[0], Form) else None
        if q is None or q.head not in ("weather-now", "forecast"):
            return [node.msg("clar", m.sender, form("unk", Symbol(q.head if q is not None else "query")), reply=m.id)]
        city = next((a.name for a in q.args if isinstance(a, Symbol)), None)
        var = next((a for a in q.args if isinstance(a, Var)), None)
        date = next((to_text(a) for a in q.args if re.fullmatch(r"\d{4}-\d{2}-\d{2}", to_text(a))), None)
        if city is None or var is None or (q.head == "forecast" and date is None):
            return [node.msg("clar", m.sender, form("parse", Str(to_text(q))), reply=m.id)]
        geo_url = ("https://geocoding-api.open-meteo.com/v1/search?"
                   + urllib.parse.urlencode({"name": city.replace("-", " "), "count": 1, "language": "en", "format": "json"}))
        found = (fetch(geo_url).get("results") or [None])[0]
        if not found:
            return [node.msg("no", m.sender, reply=m.id, kw={"why": form("unk", Symbol("data"))})]
        url = ("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": found["latitude"], "longitude": found["longitude"], "timezone": "auto",
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "wind_speed_unit": "ms", "forecast_days": 7}))
        data = fetch(url)
        off = int(data.get("utc_offset_seconds", 0))
        sign, off = ("+" if off >= 0 else "-"), abs(off)
        tz = f"{sign}{off // 3600:02d}:{off % 3600 // 60:02d}"
        fetched = datetime.now(timezone(timedelta(seconds=int(data.get("utc_offset_seconds", 0)))))
        src = _term(f'(source :uri "{url}" :kind forecast :at {fetched.strftime("%Y-%m-%dT%H:%M")}{tz})')
        if q.head == "weather-now":
            c = data["current"]
            value = (f'(weather :city {city} :at {c["time"]}{tz} :temp {_num(c["temperature_2m"])}C '
                     f':humidity {_num(c["relative_humidity_2m"])}% :wind {_num(c["wind_speed_10m"])}m/s '
                     f':sky {WMO.get(c["weather_code"], "unknown")})')
        else:
            d = data["daily"]
            if date not in d["time"]:
                return [node.msg("no", m.sender, reply=m.id, kw={"why": form("unk", Symbol("data"))})]
            i = d["time"].index(date)
            p = d["precipitation_probability_max"][i]
            value = (f'(forecast :city {city} :date {date} :max {_num(d["temperature_2m_max"][i])}C '
                     f':min {_num(d["temperature_2m_min"][i])}C'
                     + (f' :precip {_num(p)}%' if p is not None else "")
                     + f' :sky {WMO.get(d["weather_code"][i], "unknown")})')
        binding = KMap([(var, _term(value))])
        return [node.msg("tell", m.sender, binding, reply=m.id, kw={"src": src})]

    return SkillNode(name, "weather service backed by open-meteo.com (no model): answers weather-now and "
                           "forecast for a named city with the data it fetched and a :src naming the request; "
                           "answers (unk data) when it has none", handler,
                     offers=["(A x.1>weather (weather-now tokyo $w))",
                             "(A x.2>weather (forecast tokyo 2026-11-06 $f))"])


# ------------------------------------------------------------------- artist

SVG_SYSTEM = ("You are an illustrator. Answer with one complete <svg …>…</svg> element (viewBox 0 0 1600 900, "
              "no external references, no scripts, no text that claims facts) and nothing else.")


def artist_node(ask: Ask, out_dir: Path, name: str = "artist") -> SkillNode:
    """Answers (do … (draw (nl en "description"))) with ok, then done carrying the SVG's blob."""

    def handler(node: SkillNode, m: Message) -> List[Form]:
        if m.act != "do":
            return [node.msg("no", m.sender, reply=m.id, kw={"why": form("unsupported", Symbol(m.act))})] if m.act in ("ask", "prop", "def") else []
        job = m.body[0] if m.body and isinstance(m.body[0], Form) else None
        if job is None or job.head != "draw" or not job.args:
            return [node.msg("no", m.sender, reply=m.id, kw={"why": form("unk", Symbol(job.head if job else "do"))})]
        out = [node.msg("ok", m.sender, reply=m.id)]
        raw = ask(SVG_SYSTEM, [{"role": "user", "content": "Draw: " + _text_of(job.args[0])}])
        svg = re.search(r"<svg.*?</svg>", raw, re.S)
        if not svg:
            out.append(node.msg("fail", m.sender, reply=m.id,
                                kw={"code": Symbol("internal"), "why": nl("en", "the drawing model returned no <svg>")}))
            return out
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{m.id.replace('.', '-')}.svg"
        data = svg.group(0).encode("utf-8")
        path.write_bytes(data)
        out.append(node.msg("done", m.sender, _blob(data, "image/svg+xml", path), reply=m.id))
        return out

    return SkillNode(name, "illustrator: draws one SVG illustration of what you describe and replies done "
                           "with the image's blob; it draws, it does not judge or check facts", handler,
                     offers=['(D x.3>artist (draw (nl en "a calm night view of a harbour city")))'])


# --------------------------------------------------------------------- desk

def accepted_by(log: List[Message], reviewer: str, doc: Form) -> bool:
    """True when `reviewer` sent an acc for a prop whose body is exactly `doc` (canonical form)."""
    target = to_text(doc)
    props = {m.id: m for m in log if m.act == "prop" and m.body and to_text(m.body[0]) == target}
    retracted = {m.reply for m in log if m.act == "retract"}
    return any(m.act == "acc" and m.sender == reviewer and m.reply in props and m.id not in retracted
               for m in log)


def desk_node(out_dir: Path, name: str = "desk", require_acceptance_from: Optional[str] = None,
              app_reviewer: Optional[str] = None) -> SkillNode:
    """Answers (do … (publish (doc :title … :body … [:sources […]] [:image (blob …)]))) by
    writing a Markdown file, with ok, then done carrying the file's blob.

    With `require_acceptance_from="critic"` the desk enforces the review rule in code: it publishes
    only a doc that the reviewer accepted, word for word, earlier in this run - a role text alone is
    not enough, because a model can ignore it (seen live: a chief published before the critic agreed).

    With `app_reviewer="tester"` it also publishes apps, (publish (app :title … :file (blob …))): only
    an app the tester accepted, word for word, whose file still matches its blob; it is copied into
    the output folder as an .html page and returned as a blob."""

    def publish_app(node: SkillNode, m: Message, app: Form) -> List[Form]:
        from .apps import blob_ok
        if app_reviewer is None:
            return [node.msg("no", m.sender, reply=m.id, kw={"why": nl("en", "this desk does not publish apps")})]
        if not accepted_by(getattr(getattr(node, "net", None), "log", []), app_reviewer, app):
            return [node.msg("no", m.sender, reply=m.id, kw={"why": nl(
                "en", f"@{app_reviewer} has not accepted this exact app: propose it to @{app_reviewer} first")})]
        data, why = blob_ok(app.kw.get("file"))
        if data is None:
            return [node.msg("no", m.sender, reply=m.id, kw={"why": nl("en", why)})]
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{m.id.replace('.', '-')}.html"
        path.write_bytes(data)
        return [node.msg("ok", m.sender, reply=m.id),
                node.msg("done", m.sender, _blob(data, "text/html", path), reply=m.id)]

    def handler(node: SkillNode, m: Message) -> List[Form]:
        if m.act != "do":
            return [node.msg("no", m.sender, reply=m.id, kw={"why": form("unsupported", Symbol(m.act))})] if m.act in ("ask", "prop", "def") else []
        job = m.body[0] if m.body and isinstance(m.body[0], Form) else None
        doc = job.args[0] if job is not None and job.head == "publish" and job.args and isinstance(job.args[0], Form) else None
        if doc is not None and doc.head == "app":
            return publish_app(node, m, doc)
        if doc is None or "title" not in doc.kw or "body" not in doc.kw:
            return [node.msg("no", m.sender, reply=m.id,
                             kw={"why": nl("en", "expected (publish (doc :title … :body …))")})]
        if require_acceptance_from and not accepted_by(getattr(getattr(node, "net", None), "log", []),
                                                       require_acceptance_from, doc):
            return [node.msg("no", m.sender, reply=m.id, kw={"why": nl(
                "en", f"@{require_acceptance_from} has not accepted this exact page: propose it to "
                      f"@{require_acceptance_from} first and publish exactly what was accepted")})]
        out = [node.msg("ok", m.sender, reply=m.id)]
        lines = [f"# {_text_of(doc.kw['title'])}", "", _text_of(doc.kw["body"]), ""]
        image = doc.kw.get("image")
        if isinstance(image, Form) and image.head == "blob" and isinstance(image.kw.get("uri"), Str):
            lines += [f"![illustration]({image.kw['uri'].text})", ""]
        sources = doc.kw.get("sources")
        if sources is not None:
            items = list(getattr(sources, "items", [sources]))
            lines += ["## Sources", ""] + [f"- {_text_of(s.kw['uri']) if isinstance(s, Form) and 'uri' in s.kw else to_text(s)}"
                                            for s in items] + [""]
        lines.append(f"_Published by @{node.name} for @{m.sender} in reply to #{m.id}. "
                     "No human wrote or edited this page._")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{m.id.replace('.', '-')}.md"
        data = ("\n".join(lines) + "\n").encode("utf-8")
        path.write_bytes(data)
        out.append(node.msg("done", m.sender, _blob(data, "text/markdown", path), reply=m.id))
        return out

    return SkillNode(name, "publishing desk (no model): publishes the document you send as a page and replies "
                           "done with the page's blob; it publishes exactly what it receives", handler,
                     offers=['(D x.4>desk (publish (doc :title (nl ja "…") :body (nl ja "…") '
                             ':sources [(source :uri "…")] :image (blob sha256:… :uri "…"))))'])
