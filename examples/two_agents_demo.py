"""Two rule-based agents talking Koine in-process, with full protocol validation.

Run:  python examples/two_agents_demo.py
No network, no LLM — this shows the library API and the message lifecycle.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import koine
from koine import Form, KMap, Message, Quantity, Symbol, Var
from koine.build import form, msg, nl, q


class Agent:
    def __init__(self, name: str, log: list):
        self.name = name
        self.seq = 0
        self.log = log
        self.known = set()

    def _id(self) -> str:
        self.seq += 1
        return f"{self.name}.{self.seq}"

    def send(self, act, to, *body, reply=None, conf=None, kw=None) -> Message:
        m = Message.from_form(msg(act, self._id(), self.name, to, *body, reply=reply, conf=conf, kw=kw))
        self.log.append(m)
        print(f"  {koine.to_text(m.to_form())}")
        return m


class WeatherService(Agent):
    """Answers temperature queries; refuses what it does not understand."""

    DATA = {("tokyo", "2026-11-05T09:00+09:00"): 18.5}

    def handle(self, m: Message):
        if m.act == "ask":
            body = m.body[0]
            if not isinstance(body, Form):
                return self.send("fail", m.sender, reply=m.id,
                                 kw={"code": Symbol("parse"), "why": nl("en", "body is not a form")})
            if body.head == "temp":
                city = body.args[0].name
                at = body.kw.get("at")
                key = (city, at.text if at else None)
                if key not in self.DATA:
                    return self.send("tell", m.sender, form("none"), reply=m.id)
                var = next(a for a in body.args if isinstance(a, Var))
                answer = KMap([(var, q(self.DATA[key], "C"))])           # binding map {$t 18.5C}
                return self.send("tell", m.sender, answer, reply=m.id, conf=0.9, kw={"src": Symbol("jma")})
            if body.head in self.known:                                   # defined, but no data
                return self.send("tell", m.sender, form("none"), reply=m.id)
            return self.send("clar", m.sender, form("unk", Symbol(body.head)), reply=m.id)
        if m.act == "def":
            self.known.add(m.body[0].name)
            return self.send("ok", m.sender, reply=m.id)
        if m.act == "do":
            self.send("ok", m.sender, reply=m.id, kw={"eta": koine.Duration("PT1S")})
            return self.send("done", m.sender, form("cache-cleared", kw={"entries": 3}), reply=m.id)
        if m.act == "end":
            return None
        return self.send("fail", m.sender, reply=m.id,
                         kw={"code": Symbol("unsupported"), "why": form("unk", Symbol(m.act))})


def main():
    log: list[Message] = []
    a = Agent("a", log)
    b = WeatherService("b", log)

    print("--- conversation ---")
    r = b.handle(a.send("ask", "b", form("temp", Symbol("tokyo"), Var("t"),
                                        kw={"unit": Symbol("C"), "at": koine.Instant("2026-11-05T09:00+09:00")})))
    bindings = dict(r.body[0].items)
    temp = bindings[Var("t")]
    assert isinstance(temp, Quantity) and temp.unit == "C"

    # Unknown term -> clar -> def -> ok -> retry
    r = b.handle(a.send("ask", "b", form("feels-like", Symbol("tokyo"), Var("t"))))
    assert r.act == "clar"
    r = b.handle(a.send("def", "b", Symbol("feels-like"),
                        kw={"gloss": nl("en", "apparent temperature combining air temperature, humidity and wind"),
                            "args": koine.KList([Symbol("place")]), "ret": Symbol("C")}))
    assert r.act == "ok"
    r = b.handle(a.send("ask", "b", form("feels-like", Symbol("tokyo"), Var("t"))))
    assert r.act == "tell" and r.body[0].head == "none"  # defined, but no data

    b.handle(a.send("do", "b", form("clear-cache")))
    b.handle(a.send("end", "b"))

    print("--- validation ---")
    issues = koine.validate_conversation(log, known_terms=["temp", "clear-cache", "cache-cleared"])
    for i in issues:
        print(" ", i)
    errors = [i for i in issues if i.level == "error"]
    print(f"{len(log)} messages, {len(errors)} errors, nl ratio {koine.nl_ratio(log):.1%}")
    assert not errors
    print("hash of first message:", koine.digest(log[0].to_form()))


if __name__ == "__main__":
    main()
