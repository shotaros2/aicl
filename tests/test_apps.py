import hashlib
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import aicl
from aicl.apps import check_html, tester_node
from aicl.network import Limits, ModelNode, Network
from aicl.night import OwnerNode
from aicl.skills import desk_node

GOOD = """<!doctype html><html><head><meta name="viewport" content="width=device-width">
<style>canvas{background:#000}</style></head><body><canvas id="c"></canvas>
<script>const c = document.getElementById("c"); let score = 0;
function tick() { score += 1; requestAnimationFrame(tick); } tick();</script></body></html>"""


class CheckTests(unittest.TestCase):
    def test_a_clean_offline_app_passes(self):
        problems, notes = check_html(GOOD)
        self.assertEqual(problems, [])

    def test_anything_that_leaves_the_device_is_a_problem(self):
        for bad in ('<script src="https://cdn.example/x.js"></script>',
                    '<link rel="stylesheet" href="//fonts.example/a.css">',
                    "<style>body{background:url(http://img.example/a.png)}</style>",
                    "<script>fetch('/api/keys')</script>",
                    "<script>new WebSocket('wss://x')</script>"):
            problems, _ = check_html("<html><body>" + bad + "</body></html>", node=None)
            self.assertTrue(problems, bad)

    @unittest.skipUnless(shutil.which("node"), "Node.js not installed")
    def test_javascript_syntax_errors_are_found_without_running_the_code(self):
        problems, _ = check_html("<html><body><script>function ( { </script></body></html>")
        self.assertTrue(any("syntax error" in p for p in problems))

    def test_without_node_the_report_says_syntax_was_not_checked(self):
        _, notes = check_html(GOOD, node=None)
        self.assertTrue(any("not checked" in n for n in notes))


def coder(system, history):
    e = history[-1]["content"]
    if "(build-app" in e or "(fix-app" in e:
        rid = re.search(r"\(D (chief\.\d+)>coder", e).group(1)
        return (f'(K coder.1>chief ^{rid})\n(Z coder.2>chief ^{rid} (app :title (nl ja "クリック数") '
                f':about (nl ja "押した回数を数える") :file (file 1)))\n```html\n{GOOD}\n```')
    return ""


def chief(system, history):
    e = history[-1]["content"]
    if "(task " in e:
        return '(K chief.1>owner ^owner.1)\n(D chief.2>coder (build-app :spec (nl ja "クリック数を数えるアプリ")))'
    if "Z coder." in e:
        app = re.search(r"\(app .*\)\)", e).group(0)[:-1]
        return f"(P chief.3>tester {app})"
    if "C tester." in e:
        return "(D chief.4>desk (publish " + chief.app + "))"
    if "Z desk." in e:
        return f"(Z chief.5>owner ^owner.1 {re.search(r'[(]blob [^)]*[)]', e).group(0)})"
    return ""


class AppFlowTests(unittest.TestCase):
    def test_a_model_attaches_a_file_and_the_network_puts_a_blob_in_its_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            n = ModelNode("coder", "c", lambda s, h: "(T coder.1>x (app :file (file 1)))\n```html\n<p>hi</p>\n```", "id `me`")
            x = ModelNode("x", "x", lambda s, h: "", "id `me`")
            res = Network([n, x], sign=False, echo=None, files_dir=Path(tmp)).run(wake=["coder"])
            text = aicl.to_text(res.messages[0].to_form())
            self.assertIn("sha256:" + hashlib.sha256(b"<p>hi</p>\n").hexdigest(), text)
            self.assertTrue(list(Path(tmp).glob("coder-1-file1.html")))
            bad = ModelNode("coder", "c", lambda s, h: "(T coder.1>x (app :file (file 2)))\n```html\nx\n```", "id `me`")
            res = Network([bad, x], sign=False, echo=None, files_dir=Path(tmp)).run(wake=["coder"])
            self.assertEqual(res.messages, [])
            self.assertTrue(any("(file 2) has no matching" in n for n in res.notes))

    def test_the_tester_rejects_a_file_changed_after_it_was_hashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.html"
            f.write_bytes(GOOD.encode("utf-8"))
            blob = f'(blob sha256:{hashlib.sha256(GOOD.encode()).hexdigest()} :bytes {len(GOOD.encode())} :uri "{f.resolve().as_uri()}")'
            prop = aicl.Message.from_form(aicl.parse_one(f"(prop #c.1 @c>@tester (app :title (nl ja \"x\") :file {blob}))"))
            self.assertEqual(tester_node(node=None).react(None, "", prop)[0].head, "acc")
            f.write_bytes((GOOD + "<script>fetch('x')</script>").encode("utf-8"))
            out = tester_node(node=None).react(None, "", prop)[0]
            self.assertEqual(out.head, "rej")
            self.assertIn("sha256 does not match", aicl.to_text(out))

    def test_a_task_becomes_a_tested_published_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            owner = OwnerNode()
            def chief_with_memory(system, history):
                e = history[-1]["content"]
                m = re.search(r"\(app .*\)\)", e)
                if "Z coder." in e and m:
                    chief.app = m.group(0)[:-1]
                return chief(system, history)
            nodes = [owner, ModelNode("chief", "lead", chief_with_memory, "id `me`"), ModelNode("coder", "c", coder, "id `me`"),
                     tester_node(node=None), desk_node(out_dir, require_acceptance_from="critic", app_reviewer="tester")]
            net = Network(nodes, Limits(max_messages=30), sign=False, echo=None, files_dir=out_dir / "files")
            net.post(owner.task("クリック数を数えるアプリを作って"))
            res = net.run(wake=[])
            acts = [(m.sender, m.act) for m in res.messages]
            self.assertIn(("tester", "acc"), acts)
            self.assertEqual(owner.outcome.act, "done")
            page = next(out_dir.glob("chief-4.html"))
            self.assertEqual(page.read_text(encoding="utf-8"), GOOD + "\n")

    def test_the_desk_refuses_an_app_the_tester_did_not_accept(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.html"
            f.write_bytes(GOOD.encode("utf-8"))
            blob = f'(blob sha256:{hashlib.sha256(GOOD.encode()).hexdigest()} :uri "{f.resolve().as_uri()}")'
            hasty = ModelNode("chief", "c", lambda s, h: f'(D chief.1>desk (publish (app :title (nl ja "x") :file {blob})))'
                              if "; wake" in h[-1]["content"] else "", "id `me`")
            res = Network([hasty, tester_node(node=None), desk_node(Path(tmp), app_reviewer="tester")],
                          sign=False, echo=None).run(wake=["chief"])
            self.assertEqual([m.act for m in res.messages], ["do", "no"])
            self.assertEqual(list(Path(tmp).glob("chief-1.html")), [])


if __name__ == "__main__":
    unittest.main()
