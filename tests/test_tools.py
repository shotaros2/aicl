import json
import tempfile
import unittest
from pathlib import Path

import aicl
from aicl.network import Limits, ModelNode
from aicl.night import night_shift
from aicl.skills import desk_node
from aicl.tools import Memory, calc_node, fx_node, memory_node, news_node, safe_eval

try:
    from aicl.signing import generate_key
    generate_key()
    HAVE_CRYPTO = True
except Exception:
    HAVE_CRYPTO = False


def ask(node, text):
    return [aicl.to_text(f) for f in node.react(None, "", aicl.Message.from_form(aicl.parse_one(text)))]


RSS = """<rss><channel><item><title>探査機が水星を撮影へ - 例新聞</title><link>https://news.example/a</link>
<pubDate>Wed, 04 Nov 2026 10:13:08 GMT</pubDate></item></channel></rss>"""


class ToolTests(unittest.TestCase):
    def test_calculator_is_exact_and_refuses_code(self):
        c = calc_node()
        self.assertIn("{$x 90.3904}", ask(c, '(ask #e.1 @e>@calc (calc "(634-333)/333*100" $x))')[0])
        self.assertIn("{$n 50}", ask(c, "(ask #e.2 @e>@calc (days-between 2026-11-05 2026-12-25 $n))")[0])
        self.assertIn("{$w friday}", ask(c, "(ask #e.3 @e>@calc (weekday 2026-12-25 $w))")[0])
        for bad in ("__import__('os')", "open('x')", "2**10000", "a+1"):
            with self.assertRaises(ValueError):
                safe_eval(bad)
        self.assertTrue(ask(c, '(ask #e.4 @e>@calc (calc "1/0" $x))')[0].startswith("(clar"))

    def test_fx_and_news_carry_their_sources_and_times(self):
        fx = fx_node(fetch=lambda u: json.dumps({"date": "2026-11-04", "rates": {"JPY": 158.25}}))
        out = ask(fx, "(ask #e.1 @e>@fx (fx-rate USD JPY $r))")[0]
        self.assertIn(":rate 158.25", out)
        self.assertIn('kind exchange-rate', out)
        news = news_node(fetch=lambda u: RSS)
        out = ask(news, "(ask #e.2 @e>@news (headlines $h :topic science))")[0]
        self.assertIn(":at 2026-11-04T19:13+09:00", out)                  # GMT converted, so staleness is visible
        self.assertIn('"https://news.example/a"', out)
        self.assertTrue(ask(news, "(ask #e.3 @e>@news (headlines $h :topic gossip))")[0].startswith("(clar"))

    def test_memory_recalls_by_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = Memory(Path(tmp) / "m.jsonl")
            mem.add(task="東京スカイツリーの要点", status="done", by="owner", title="スカイツリー案内")
            mem.add(task="明日の天気", status="done", by="scout")
            node = memory_node(mem)
            hit = ask(node, '(ask #e.1 @e>@memory (recall (nl ja "スカイツリー") $m))')[0]
            self.assertIn("スカイツリー案内", hit)
            self.assertNotIn("明日の天気", hit)
            self.assertIn(":by scout", ask(node, "(ask #e.2 @e>@memory (recent $m))")[0])


def scout(system, history):
    e = history[-1]["content"]
    if "; wake" in e:
        return "(A scout.1>memory (recent $m))"
    if "T memory." in e:
        return '(D scout.2>chief (task (nl ja "明日の東京の天気を調べて")))\n(D scout.3>chief (task (nl ja "二件目")))\n(D scout.4>chief (task (nl ja "三件目は上限超え")))'
    return ""


def chief(system, history):
    e = history[-1]["content"]
    if "(task " in e:
        return ('(K chief.1>owner ^owner.1)\n(D chief.2>desk (publish (doc :title (nl ja "天気") :body (nl ja "晴れ"))))')
    if "Z desk." in e:
        import re
        return f"(Z chief.3>owner ^owner.1 {re.search(r'[(]blob [^)]*[)]', e).group(0)})"
    return ""


class ScoutTests(unittest.TestCase):
    def test_the_scout_starts_work_nobody_asked_for_and_the_team_remembers_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mem = Memory(root / "memory.jsonl")
            make = lambda out: [ModelNode("chief", "lead", chief, "id `me`"), desk_node(out)]
            make_scout = lambda: [ModelNode("scout", "scout", scout, "id `me`"), memory_node(mem)]
            report = night_shift(root / "inbox", root, make, Limits(max_messages=30), echo=lambda s: None,
                                 scout=make_scout, max_scout_tasks=2, memory=mem,
                                 known_terms=("task", "doc", "publish", "recent", "done-before"))
            text = report.read_text(encoding="utf-8")
            self.assertIn("うち AI が自分で始めたもの 2 件", text)
            self.assertIn("仕事を 2 件提案しました", text)
            self.assertIn("## scout-1: 完了（スカウトの提案）", text)
            self.assertNotIn("三件目", text)                                 # the third proposal was refused
            entries = mem.all()
            self.assertEqual([e["by"] for e in entries], ["scout", "scout"])
            self.assertEqual(entries[0]["title"], "天気")
            self.assertFalse((root / "RUNNING").exists())                   # the lock is released

    def test_a_running_shift_blocks_a_second_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "RUNNING").write_text("busy")
            with self.assertRaises(RuntimeError):
                night_shift(root / "inbox", root, lambda out: [], echo=lambda s: None, scout=lambda: [])


if __name__ == "__main__":
    unittest.main()
