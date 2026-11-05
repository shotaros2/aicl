import json
import re
import tempfile
import unittest
from pathlib import Path

import aicl
from aicl.actions import StructuredModelNode, schema
from aicl.network import Limits, Network, Node
from aicl.night import run_task
from aicl.research import library_node
from aicl.skills import desk_node

try:
    from aicl.signing import generate_key
    generate_key()
    HAVE_CRYPTO = True
except Exception:
    HAVE_CRYPTO = False


def act(a, to, **kw):
    base = {"act": a, "to": to, "reply_to": None, "request": None, "draft": None, "doc": None,
            "copy_of": None, "publish_accepted": None, "advice": None, "why": None, "code": None}
    base.update(kw)
    return base


def answer(*actions):
    return json.dumps({"messages": list(actions)}, ensure_ascii=False)


class SchemaTests(unittest.TestCase):
    def test_every_object_is_closed_and_fully_required(self):
        def walk(s):
            if isinstance(s, dict):
                if s.get("type") == "object":
                    self.assertIs(s["additionalProperties"], False)
                    self.assertEqual(sorted(s["required"]), sorted(s["properties"]))
                for v in s.values():
                    walk(v)
            elif isinstance(s, list):
                for v in s:
                    walk(v)
        sc = schema(["owner", "writer"])
        walk(sc)
        self.assertEqual(sc["properties"]["messages"]["items"]["properties"]["to"]["enum"], ["owner", "writer"])


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.owner = Node("owner", "the person")
        self.writer = Node("writer", "writes")
        self.chief = StructuredModelNode("chief", "lead", lambda s, h, schema=None: "", "")
        self.net = Network([self.owner, self.writer, self.chief], sign=False, echo=None)
        self.net.post(self.owner.msg("do", "chief", aicl.parse_one('(task (nl ja "東京タワー"))')))

    def text(self, raw):
        return [aicl.to_text(m.to_form()) for m in self.chief._parse(raw, self.net)]

    def test_long_text_never_needs_hand_balanced_parentheses(self):
        out = self.text(answer(
            act("ok", "owner", reply_to="owner.1"),
            act("do", "writer", draft={"about": "東京タワーの要点（3つ）", "facts": ["高さは333m（海抜351m）。"],
                                        "sources": ["https://ja.wikipedia.org/wiki/東京タワー"]})))
        self.assertEqual(out[0], "(ok #chief.1 @chief>@owner ^owner.1)")
        self.assertIn('(draft :about (nl ja "東京タワーの要点（3つ）") :facts [(nl ja "高さは333m（海抜351m）。")]', out[1])
        self.assertTrue(out[1].startswith("(do #chief.2 @chief>@writer"))

    def test_copy_of_and_publish_accepted_refer_by_id(self):
        self.net.post(self.writer.msg("done", "chief", aicl.parse_one('(doc :title (nl ja "t") :body (nl ja "b"))'),
                                      reply="owner.1"))
        out = self.text(answer(act("prop", "owner", copy_of="#writer.1"),
                               act("do", "owner", publish_accepted="^writer.1")))
        self.assertEqual(out[0], '(prop #chief.1 @chief>@owner (doc :body (nl ja "b") :title (nl ja "t")))')
        self.assertEqual(out[1], "(do #chief.2 @chief>@owner (publish (ref #writer.1)))")

    def test_unknown_ids_and_bad_requests_are_bounced(self):
        with self.assertRaises(aicl.ParseError):
            self.text(answer(act("prop", "writer", copy_of="writer.9")))
        with self.assertRaises(aicl.ParseError):
            self.text(answer(act("ok", "owner", reply_to="owner.7")))
        with self.assertRaises(aicl.ParseError):
            self.text(answer(act("ask", "writer", request="(search (nl ja \"x\") $r")))
        with self.assertRaises(aicl.ParseError):
            self.text("not json")

    def test_why_and_code(self):
        out = self.text(answer(act("fail", "owner", reply_to="owner.1", why="出典が読めなかった", code="not-found")))
        self.assertEqual(out[0], '(fail #chief.1 @chief>@owner ^owner.1 :code not-found :why (nl ja "出典が読めなかった"))')

    def test_the_schema_is_passed_to_the_model(self):
        seen = {}

        def ask(system, history, schema=None):
            seen["schema"], seen["system"] = schema, system
            if "; continue" in history[-1]["content"]:
                return answer(act("done", "owner", reply_to="owner.1", request='(none)'))
            return answer(act("ok", "owner", reply_to="owner.1"))
        chief = StructuredModelNode("chief", "lead", ask, "")
        owner = Node("owner", "the person")
        net = Network([owner, chief], sign=False, echo=None)
        net.post(owner.msg("do", "chief", aicl.parse_one('(task (nl ja "x"))')))
        res = net.run(wake=[])
        self.assertEqual(seen["schema"]["properties"]["messages"]["items"]["properties"]["to"]["enum"], ["owner"])
        self.assertIn("Your agent name is @chief", seen["system"])
        self.assertEqual([m.act for m in res.messages], ["do", "ok", "done"])


@unittest.skipUnless(HAVE_CRYPTO, "needs the cryptography package")
class StructuredNightTaskTests(unittest.TestCase):
    """A whole page task with JSON agents: facts from the library, a draft, the critic's
    acceptance, publication by reference, and the desk's blob passed to the owner by id."""

    def test_page_task_done_with_publish_by_reference(self):
        def last(h):
            return h[-1]["content"]

        def chief(system, history, schema=None):
            e = last(history)
            ids = lambda pat: re.findall(pat, e)
            if "(do #owner.1" in e:
                return answer(act("ok", "owner", reply_to="owner.1"),
                              act("ask", "library", request='(summary "東京スカイツリー" $s)'))
            if "@library>@chief" in e:
                return answer(act("do", "writer", draft={"about": "スカイツリー", "facts": ["高さは634m。"],
                                                         "sources": ["https://ja.wikipedia.org/wiki/T"]}))
            if "(done #writer." in e:
                return answer(act("prop", "critic", copy_of=ids(r"#(writer\.\d+)")[0]))
            if "(acc #critic." in e:
                return answer(act("do", "desk", publish_accepted=ids(r"\^(chief\.\d+)")[0]))
            if "(done #desk." in e:
                return answer(act("done", "owner", reply_to="owner.1", copy_of=ids(r"#(desk\.\d+)")[0]))
            return answer()

        def writer(system, history, schema=None):
            e = last(history)
            if "(do #chief." in e:
                rid = re.findall(r"#(chief\.\d+)", e)[0]
                return answer(act("ok", "chief", reply_to=rid),
                              act("done", "chief", reply_to=rid, doc={"title": "スカイツリー", "body": "高さは634メートル。",
                                                                    "sources": ["https://ja.wikipedia.org/wiki/T"]}))
            return answer()

        def critic(system, history, schema=None):
            e = last(history)
            if "(prop #chief." in e:
                return answer(act("acc", "chief", reply_to=re.findall(r"#(chief\.\d+)", e)[0]))
            return answer()

        summary = {"title": "東京スカイツリー", "extract": "高さ634メートル。",
                   "content_urls": {"desktop": {"page": "https://ja.wikipedia.org/wiki/T"}}}
        with tempfile.TemporaryDirectory() as tmp:
            def make(out_dir):
                return [StructuredModelNode("chief", "lead", chief, ""),
                        StructuredModelNode("writer", "writes", writer, ""),
                        StructuredModelNode("critic", "checks", critic, ""),
                        library_node(fetch=lambda url: summary),
                        desk_node(out_dir, require_acceptance_from="critic")]
            o = run_task("t", "スカイツリー", Path(tmp) / "t", make, Limits(max_messages=40, max_calls_per_agent=10),
                         known_terms=["summary", "draft", "doc", "publish", "source", "article"],
                         echo=lambda s: None, retro=False)
            self.assertEqual(o.status, "done", [aicl.to_text(m.to_form()) for m in o.run.messages])
            self.assertTrue(o.verified)
            self.assertIn("高さは634メートル。", o.result.read_text(encoding="utf-8"))
            self.assertEqual([i for i in o.run.issues if i.level == "error"], [])


class DeskByReferenceTests(unittest.TestCase):
    def test_desk_refuses_a_reference_to_an_unaccepted_or_unknown_prop(self):
        with tempfile.TemporaryDirectory() as tmp:
            chief, critic = Node("chief", "lead"), Node("critic", "checks")
            desk = desk_node(Path(tmp), require_acceptance_from="critic")
            net = Network([chief, critic, desk], sign=False, echo=None)
            net.post(chief.msg("prop", "critic", aicl.parse_one('(doc :title (nl ja "t") :body (nl ja "b"))')))
            net.post(chief.msg("do", "desk", aicl.parse_one("(publish (ref #chief.1))")))
            net.post(chief.msg("do", "desk", aicl.parse_one("(publish (ref #chief.9))")))
            res = net.run(wake=[])
            refusals = [aicl.to_text(m.to_form()) for m in res.messages if m.sender == "desk"]
            self.assertIn("has not accepted this exact page", refusals[0])
            self.assertIn("#chief.9 is not a proposal", refusals[1])


if __name__ == "__main__":
    unittest.main()
