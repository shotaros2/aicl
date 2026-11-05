import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aicl
from aicl.network import Limits, ModelNode, Network
from aicl.skills import artist_node, desk_node, weather_node

try:
    from aicl.signing import generate_key
    generate_key()
    HAVE_CRYPTO = True
except Exception:
    HAVE_CRYPTO = False

RULEBOOK = "Your agent id is `me`. Speak AICL."
JST = timezone(timedelta(hours=9))
CLOCK = lambda: datetime(2026, 11, 5, 12, 0, tzinfo=JST)


def fake_fetch(url):
    if "geocoding" in url:
        return {"results": [{"latitude": 35.68, "longitude": 139.69}]} if "tokyo" in url else {}
    return {"utc_offset_seconds": 32400,
            "current": {"time": "2026-11-05T12:00", "temperature_2m": 15.5, "relative_humidity_2m": 60,
                        "wind_speed_10m": 3.0, "weather_code": 1},
            "daily": {"time": ["2026-11-05", "2026-11-06"], "weather_code": [1, 61],
                      "temperature_2m_max": [18.0, 16.2], "temperature_2m_min": [10.0, 11.4],
                      "precipitation_probability_max": [5, 80]}}


def last(history):
    return history[-1]["content"]


def editor_ask(system, history):
    """A scripted editor: it only reacts to what it receives, like a model would."""
    e = last(history)
    if "; wake" in e:
        return "(A editor.1>weather (forecast tokyo 2026-11-06 $f))"
    if e.count("T weather.") and "^editor.1" in e:
        return ('(P editor.1>critic (doc :title (nl ja "明日の東京") :body (nl ja "明日は雨、最高16.2C")))\n'
                '; the id above is reused on purpose: the network must renumber it')
    if "C critic." in e:
        return '(D editor.3>desk (publish (doc :title (nl ja "明日の東京") :body (nl ja "明日は雨、最高16.2C"))))'
    return ""


def critic_ask(system, history):
    e = last(history)
    if "P editor." in e:
        return "(A critic.1>weather (forecast tokyo 2026-11-06 $f))"
    if "T weather." in e and "16.2C" in e:
        return "(C critic.2>editor ^editor.2)"
    return ""


class NetworkTests(unittest.TestCase):
    def build(self, tmp, editor=editor_ask, critic=critic_ask, **limits):
        nodes = [ModelNode("editor", "newsroom editor", editor, RULEBOOK),
                 ModelNode("critic", "fact checker", critic, RULEBOOK),
                 weather_node(fetch=fake_fetch), desk_node(Path(tmp))]
        return Network(nodes, Limits(**limits), sign=HAVE_CRYPTO, clock=CLOCK, echo=None)

    def test_agents_decide_the_whole_exchange(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = self.build(tmp).run()
            acts = [(m.sender, m.act, m.receiver) for m in res.messages]
            self.assertEqual(acts, [
                ("editor", "ask", "weather"), ("weather", "tell", "editor"),
                ("editor", "prop", "critic"), ("critic", "ask", "weather"), ("weather", "tell", "critic"),
                ("critic", "acc", "editor"), ("editor", "do", "desk"), ("desk", "ok", "editor"),
                ("desk", "done", "editor")])
            self.assertTrue(res.stopped.startswith("quiet"))
            ids = [m.id for m in res.messages]
            self.assertEqual(len(ids), len(set(ids)))                  # the reused editor.1 was renumbered
            self.assertEqual(res.messages[2].id, "editor.2")
            self.assertEqual([i for i in res.issues if i.level == "error"], [])
            blob = res.messages[-1].body[0]
            path = Path(tmp) / "editor-3.md"
            self.assertTrue(path.exists())
            self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(), aicl.to_text(blob))
            self.assertIn("明日は雨", path.read_text(encoding="utf-8"))

    @unittest.skipUnless(HAVE_CRYPTO, "needs the cryptography package")
    def test_every_message_is_signed_and_the_review_is_a_verifiable_agreement(self):
        from aicl.agreement import extract_agreements
        with tempfile.TemporaryDirectory() as tmp:
            res = self.build(tmp).run()
            self.assertEqual(set(res.keys), {"editor", "critic", "weather", "desk"})
            ags = extract_agreements(res.messages, keys=res.keys, known_terms=("doc",))
            self.assertEqual(len(ags), 1)
            self.assertEqual(ags[0].parties, ("editor", "critic"))
            self.assertTrue(ags[0].verified)

    def test_budget_and_message_cap_stop_a_chatty_network(self):
        def ping(system, history):
            return "(T editor.9>critic true)"
        def pong(system, history):
            return "(T critic.9>editor true)"
        with tempfile.TemporaryDirectory() as tmp:
            res = self.build(tmp, editor=ping, critic=pong, max_calls_per_agent=4, max_messages=50).run()
            self.assertLessEqual(len(res.messages), 8)
            self.assertTrue(any("budget" in n for n in res.notes))
            res = self.build(tmp, editor=ping, critic=pong, max_calls_per_agent=100, max_messages=6).run()
            self.assertEqual(res.stopped, "message cap (6)")

    def test_stop_file_halts_the_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            stop = Path(tmp) / "STOP"
            stop.write_text("")
            res = self.build(tmp, stop_file=stop).run()
            self.assertEqual(len(res.messages), 1)                     # the wake-up answer, then nothing
            self.assertTrue(res.stopped.startswith("stop file"))

    def test_unknown_recipient_and_prose_get_one_correction(self):
        replies = iter(["Sure! Here is my plan: ask the weather.", "(A editor.1>oracle (x $y))",
                        "(A editor.1>weather (weather-now tokyo $w))"])
        def flaky(system, history):
            return next(replies, "")
        with tempfile.TemporaryDirectory() as tmp:
            res = self.build(tmp, editor=flaky, critic=lambda s, h: "").run()
            self.assertEqual(sum("invalid" in n for n in res.notes), 2)
            self.assertEqual(res.messages, [])                          # two bad answers: the wake-up is dropped
            nodes = [ModelNode("editor", "e", lambda s, h: next(replies, ""), RULEBOOK), weather_node(fetch=fake_fetch)]
            res = Network(nodes, sign=False, clock=CLOCK, echo=None).run()
            self.assertEqual([m.act for m in res.messages], ["ask", "tell"])

    def test_the_desk_publishes_only_what_the_critic_accepted(self):
        # Seen live: a chief sent the page to the desk before the critic had accepted it.
        def hasty(system, history):
            if "; wake" in history[-1]["content"]:
                return '(D editor.1>desk (publish (doc :title (nl ja "速報") :body (nl ja "未確認"))))'
            return ""
        with tempfile.TemporaryDirectory() as tmp:
            nodes = [ModelNode("editor", "e", hasty, RULEBOOK), ModelNode("critic", "c", lambda s, h: "", RULEBOOK),
                     desk_node(Path(tmp), require_acceptance_from="critic")]
            res = Network(nodes, sign=False, clock=CLOCK, echo=None).run(wake=["editor"])
            self.assertEqual([m.act for m in res.messages], ["do", "no"])
            self.assertIn("has not accepted this exact page", aicl.to_text(res.messages[1].to_form()))
            self.assertEqual(list(Path(tmp).glob("*.md")), [])
        with tempfile.TemporaryDirectory() as tmp:                      # the reviewed path still publishes
            nodes = [ModelNode("editor", "e", editor_ask, RULEBOOK), ModelNode("critic", "c", critic_ask, RULEBOOK),
                     weather_node(fetch=fake_fetch), desk_node(Path(tmp), require_acceptance_from="critic")]
            res = Network(nodes, sign=False, clock=CLOCK, echo=None).run()
            self.assertEqual(res.messages[-1].act, "done")

    def test_a_model_that_only_acknowledges_gets_a_turn_to_continue(self):
        # Seen live: the chief answered a task with ok alone and the network fell quiet.
        from aicl.night import OwnerNode
        def lazy(system, history):
            e = history[-1]["content"]
            if "(task " in e:
                return "(K chief.1>owner ^owner.1)"
            if "; continue" in e:
                return "(A chief.2>weather (weather-now tokyo $w))"
            if "T weather." in e:
                return '(F chief.3>owner ^owner.1 :e not-found :w (nl en "stop here"))'
            return ""
        owner = OwnerNode()
        net = Network([owner, ModelNode("chief", "lead", lazy, RULEBOOK), weather_node(fetch=fake_fetch)],
                      sign=False, clock=CLOCK, echo=None)
        net.post(owner.task("天気"))
        res = net.run(wake=[])
        self.assertEqual([m.act for m in res.messages], ["do", "ok", "ask", "tell", "fail"])
        self.assertEqual(owner.outcome.act, "fail")

    def test_the_owner_says_how_to_finish_then_stops_answering(self):
        # Seen on the home PC: a local chief reported failure as an ask to @owner, again and again,
        # until its call budget was gone.
        from aicl.night import OwnerNode
        calls = []

        def stubborn(system, history):
            calls.append(1)
            n = len(calls)
            return f'(A chief.{n}>owner (task :status failed :try {n}))'
        owner = OwnerNode()
        net = Network([owner, ModelNode("chief", "lead", stubborn, RULEBOOK)],
                      Limits(max_messages=40, max_calls_per_agent=20), sign=False, clock=CLOCK, echo=None)
        net.post(owner.task("東京タワー"))
        res = net.run(wake=[])
        refusals = [m for m in res.messages if m.sender == "owner" and m.act == "no"]
        self.assertEqual(len(refusals), 3)
        self.assertIn("answer #owner.1 with done", aicl.to_text(refusals[0].to_form()))
        self.assertEqual(len(calls), 4)                     # the task, then one call per refusal
        self.assertTrue(any("stopped answering after 3 refusals" in n for n in res.notes))
        self.assertTrue(res.stopped.startswith("quiet"))

    def test_an_ok_to_an_ask_also_gets_a_turn_to_continue(self):
        # Seen live: a chief sent (ask … (draft …)), the writer answered ok and never drafted.
        from aicl.network import Node
        def writer(system, history):
            e = history[-1]["content"]
            if "; continue" in e:
                return '(T writer.2>chief ^chief.1 {$d (doc :title (nl ja "t"))})'
            return "(K writer.1>chief ^chief.1)"
        chief = Node("chief", "lead")
        net = Network([chief, ModelNode("writer", "writes", writer, RULEBOOK)], sign=False, clock=CLOCK, echo=None)
        net.post(chief.msg("ask", "writer", aicl.parse_one("(draft :about (nl ja \"x\") $d)")))
        res = net.run(wake=[])
        self.assertEqual([m.act for m in res.messages], ["ask", "ok", "tell"])

    def test_a_forged_done_is_answered_so_the_chief_can_fix_it(self):
        from aicl.night import OwnerNode
        def chief(system, history):
            e = history[-1]["content"]
            if "(task " in e:
                return '(Z chief.1>owner ^owner.1 (task (nl ja "x")))'          # a done with no blob, as seen live
            if "not accepted" in e:
                return '(F chief.2>owner ^owner.1 :e not-found :w (nl en "nothing was published"))'
            return ""
        owner = OwnerNode()
        net = Network([owner, ModelNode("chief", "lead", chief, RULEBOOK)], sign=False, clock=CLOCK, echo=None)
        net.post(owner.task("東京タワー"))
        res = net.run(wake=[])
        self.assertEqual([m.act for m in res.messages], ["do", "done", "no", "fail"])
        self.assertEqual(owner.outcome.act, "fail")
        self.assertEqual(owner.forged, ["chief.1"])

    def test_an_unsupported_refusal_shows_how_to_ask(self):
        # Seen live: a critic sent the reader a do, read (unsupported do) as a bad address, and retried.
        from aicl.research import reader_node
        r = reader_node(fetch=lambda url: (url, "<title>t</title>x"), allow=lambda u: "ok")
        m = aicl.Message.from_form(aicl.parse_one('(do #c.1 @c>@reader (read "https://example.org/" $p))'))
        out = aicl.to_text(r.react(None, "", m)[0])
        self.assertIn("(unsupported do :use", out)
        self.assertIn("(A x.3>reader (read", out)

    def test_a_third_identical_request_is_bounced(self):
        # Seen with qwen3.5:9b, thinking off: the same draft request twelve times.
        from aicl.network import Node
        shown = []

        def repeater(system, history):
            shown.append(history[-1]["content"])
            return '(A chief.9>writer (draft :about (nl ja "x") $d))'
        writer = Node("writer", "writes")
        writer.react = lambda net, event, m: ([writer.msg("tell", m.sender, aicl.parse_one("{$d 1}"), reply=m.id)]
                                              if m is not None and m.act == "ask" else [])
        chief = ModelNode("chief", "lead", repeater, RULEBOOK)
        net = Network([chief, writer], Limits(max_messages=30, max_calls_per_agent=6), sign=False, clock=CLOCK, echo=None)
        res = net.run(wake=["chief"])
        asks = [m for m in res.messages if m.sender == "chief"]
        self.assertEqual(len(asks), 2)
        self.assertTrue(any("you already sent this exact ask to @writer twice" in n for n in res.notes))

    def test_an_act_letter_as_a_body_is_bounced(self):
        from aicl.night import OwnerNode
        chief = ModelNode("chief", "lead", lambda s, h: "", RULEBOOK)
        owner = OwnerNode()
        net = Network([owner, chief], sign=False, clock=CLOCK, echo=None)
        with self.assertRaises(aicl.ParseError) as cm:
            chief._parse("(A chief.1>owner ^owner.1 K (ok :a 20261105T221331+9))", net)
        self.assertIn("K is an act, not a body", str(cm.exception))

    def test_an_act_wrapped_in_an_ask_is_bounced_with_the_right_form(self):
        # Seen on the home PC: qwen3.5:9b wrote (A chief.6>owner (fail …)) and (A chief.3>critic (prop …)).
        from aicl.night import OwnerNode
        shown = []

        def wrapper(system, history):
            shown.append(history[-1]["content"])
            if len(shown) == 1:
                return '(A chief.1>owner (fail :e unsupported :w "no sources"))'
            return '(F chief.1>owner ^owner.1 :e unsupported :w (nl en "no sources"))'
        owner = OwnerNode()
        net = Network([owner, ModelNode("chief", "lead", wrapper, RULEBOOK)], sign=False, clock=CLOCK, echo=None)
        net.post(owner.task("東京タワー"))
        res = net.run(wake=[])
        self.assertIn("fail is an act: write (F chief.1>owner", shown[1])
        self.assertEqual(owner.outcome.act, "fail")
        self.assertTrue(any("invalid (attempt 1)" in n for n in res.notes))

    def test_weather_answers_only_what_it_has(self):
        w = weather_node(fetch=fake_fetch)
        ask = lambda s: aicl.Message.from_form(aicl.parse_one(s))
        out = [aicl.to_text(f) for f in w.react(None, "", ask("(ask #e.1 @e>@weather (forecast tokyo 2026-11-06 $f))"))]
        self.assertIn(":max 16.2C", out[0])
        self.assertIn(":src (source", out[0])
        self.assertIn("(no ", w.react(None, "", ask("(ask #e.2 @e>@weather (forecast atlantis 2026-11-06 $f))"))[0].head
                      .join(["(", " "]))
        self.assertEqual(w.react(None, "", ask("(ask #e.3 @e>@weather (crowd-index tokyo $x))"))[0].head, "clar")
        self.assertEqual(w.react(None, "", ask("(ask #e.4 @e>@weather (forecast tokyo 2027-01-01 $f))"))[0].head, "no")

    def test_artist_returns_a_blob_of_what_it_drew(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = artist_node(lambda s, h: '<svg viewBox="0 0 10 10"><rect width="10" height="10"/></svg>', Path(tmp))
            m = aicl.Message.from_form(aicl.parse_one('(do #e.5 @e>@artist (draw (nl en "a square")))'))
            ok, done = a.react(None, "", m)
            self.assertEqual((ok.head, done.head), ("ok", "done"))
            data = (Path(tmp) / "e-5.svg").read_bytes()
            self.assertIn(hashlib.sha256(data).hexdigest(), aicl.to_text(done))


if __name__ == "__main__":
    unittest.main()
