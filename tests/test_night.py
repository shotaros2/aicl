import re
import tempfile
import unittest
from pathlib import Path

import aicl
from aicl.network import Limits, ModelNode
from aicl.night import night_shift
from aicl.research import library_node, reader_node
from aicl.skills import desk_node

try:
    from aicl.signing import generate_key
    generate_key()
    HAVE_CRYPTO = True
except Exception:
    HAVE_CRYPTO = False

RULEBOOK = "Your agent id is `me`."
SUMMARY = {"title": "東京スカイツリー", "extract": "東京スカイツリーは高さ634メートルの電波塔。",
           "content_urls": {"desktop": {"page": "https://ja.wikipedia.org/wiki/T"}}}


def fake_wiki(url):
    return SUMMARY if "summary" in url else {"query": {"search": []}}


def last(h):
    return h[-1]["content"]


def chief(system, history):
    e = last(history)
    if "(task " in e and "高さ" in e:
        return '(A chief.1>library (summary "東京スカイツリー" $s))'
    if "(task " in e:
        return '(A chief.1>owner (prefer (nl ja "どちらの店？") $x))'
    if "T library." in e:
        return ('(P chief.2>critic (doc :title (nl ja "スカイツリー") :body (nl ja "高さは634メートル。") '
                ':sources [(source :uri "https://ja.wikipedia.org/wiki/T")]))')
    if "C critic." in e:
        return ('(D chief.3>desk (publish (doc :title (nl ja "スカイツリー") :body (nl ja "高さは634メートル。") '
                ':sources [(source :uri "https://ja.wikipedia.org/wiki/T")])))')
    if "Z desk." in e:
        blob = re.search(r"\(blob [^)]*\)", e).group(0)
        fake = ("(blob sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 "
                ':bytes 0 :media "text/html" :uri "https://desk.local/page/1")')
        return f"(Z chief.4>owner ^owner.1 {fake})\n(Z chief.5>owner ^owner.1 {blob})"   # a forgery first, as seen live
    if "N owner." in e:
        return '(N chief.2>owner ^owner.1 :e unsupported :w (nl en "needs the owner\'s preference"))'   # refused with no, as seen live
    return ""


def critic(system, history):
    e = last(history)
    if "P chief." in e:
        return '(A critic.1>library (summary "東京スカイツリー" $s))'
    if "T library." in e and "634" in e:
        return "(C critic.2>chief ^chief.2)"
    return ""


class NightShiftTests(unittest.TestCase):
    def nodes(self, out_dir):
        return [ModelNode("chief", "lead", chief, RULEBOOK), ModelNode("critic", "checker", critic, RULEBOOK),
                library_node(fetch=fake_wiki), reader_node(fetch=lambda u: (u, "<title>x</title>x"), allow=lambda u: True),
                desk_node(out_dir)]

    def test_tasks_are_done_or_refused_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / "inbox"
            inbox.mkdir()
            (inbox / "a_skytree.txt").write_text("東京スカイツリーの高さを調べて", encoding="utf-8")
            (inbox / "b_lunch.txt").write_text("明日のランチの店を予約して", encoding="utf-8")
            report = night_shift(inbox, root, self.nodes, Limits(max_messages=40), echo=lambda s: None,
                                 known_terms=("task", "doc", "publish", "summary", "article", "source", "prefer"))
            text = report.read_text(encoding="utf-8")
            self.assertIn("## a_skytree: 完了", text)
            self.assertIn("## b_lunch: できなかった", text)
            self.assertIn("needs the owner's preference", text)
            page = next((report.parent / "a_skytree").glob("chief-3.md"))
            self.assertIn("634", page.read_text(encoding="utf-8"))
            self.assertIn("a_skytree/chief-3.md", text)
            self.assertIn("中身と一致しない「納品」を無視: 1 件（#chief.4）", text)
            self.assertEqual(list(inbox.glob("*.txt")), [])                 # both moved to done/
            self.assertEqual(len(list((root / "done").glob("*.txt"))), 2)
            if HAVE_CRYPTO:
                self.assertIn("署名付き合意）: 検証できた", text.split("## b_lunch")[0])
            transcript = (report.parent / "b_lunch" / "transcript.aicl").read_text(encoding="utf-8")
            self.assertIn("(no #owner.2 @owner>@chief ^chief.1", transcript)   # the sleeping owner refused

    def test_a_blob_wrapped_in_a_doc_is_still_checked_against_the_file(self):
        import hashlib
        from aicl.night import _blob_path, deliverable_ok
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "page.md"
            p.write_bytes("東京タワー".encode("utf-8"))
            digest = hashlib.sha256(p.read_bytes()).hexdigest()

            def done(h):
                return aicl.Message.from_form(aicl.parse_one(
                    f'(done #chief.9 @chief>@owner ^owner.1 (doc :blob (blob sha256:{h} :bytes {p.stat().st_size} '
                    f':media "text/markdown" :uri "{p.resolve().as_uri()}") :title (nl ja "t")))'))
            self.assertTrue(deliverable_ok(done(digest)))
            self.assertEqual(_blob_path(done(digest)), p.resolve())
            self.assertFalse(deliverable_ok(done("0" * 64)))
            beside = aicl.Message.from_form(aicl.parse_one(
                f'(done #chief.11 @chief>@owner ^owner.1 (task (nl ja "t")) (blob sha256:{digest} '
                f':bytes {p.stat().st_size} :media "text/markdown" :uri "{p.resolve().as_uri()}"))'))
            self.assertTrue(deliverable_ok(beside))          # seen live: the blob second in the body

    @unittest.skipUnless(HAVE_CRYPTO, "needs the cryptography package")
    def test_retrospective_advice_is_decided_by_the_receiver_and_kept_only_when_accepted(self):
        from datetime import datetime
        from aicl.network import Limits as L
        from aicl.night import Lessons, run_task, write_report

        def chief(system, history):
            e = last(history)
            if "; retro" in e:
                return '(P chief.3>writer (advice (nl ja "出典のURLはそのまま書いて")))'
            if "P writer." in e:
                return '(R chief.4>writer ^writer.2 :w (nl ja "速さより正確さを優先する"))'
            if "(task " in e:
                return '(A chief.1>writer (draft :about (nl ja "x") $d))'
            if "T writer." in e:
                return '(F chief.2>owner ^owner.1 :e not-found :w (nl en "test"))'
            return ""

        def writer(system, history):
            e = last(history)
            if "; retro" in e:
                return '(P writer.2>chief (advice (nl ja "もっと早く頼んで")))'
            if "P chief." in e:
                return "(C writer.3>chief ^chief.3)"
            if "(draft" in e:
                return '(T writer.1>chief ^chief.1 {$d (doc :title (nl ja "t"))})'
            return ""

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            lessons = Lessons(tmp / "lessons.jsonl")
            make = lambda out: [ModelNode("chief", "lead", chief, RULEBOOK), ModelNode("writer", "writes", writer, RULEBOOK)]
            o = run_task("t1", "テスト", tmp / "t1", make, L(max_messages=40, max_calls_per_agent=10),
                         known_terms=["draft", "doc", "advice"], echo=lambda s: None, lessons=lessons)
            self.assertEqual(o.status, "fail")
            self.assertEqual([(r["from"], r["to"], r["answer"]) for r in o.retro],
                             [("chief", "writer", "acc"), ("writer", "chief", "rej")])
            self.assertEqual(o.retro[1]["why"], "速さより正確さを優先する")
            kept = lessons.all()
            self.assertEqual([(r["from"], r["to"], r["text"]) for r in kept], [("chief", "writer", "出典のURLはそのまま書いて")])
            self.assertIn("from @chief: 出典のURLはそのまま書いて", lessons.role_note("writer"))
            self.assertIn("never overrides your role", lessons.role_note("writer"))
            self.assertEqual(lessons.role_note("chief"), "")
            self.assertIn("(prop #chief.3 @chief>@writer (advice", (tmp / "t1" / "transcript.aicl").read_text(encoding="utf-8"))
            report = write_report(tmp, [o], datetime.now()).read_text(encoding="utf-8")
            self.assertIn("振り返り（AI 同士の提案）: 2 件、うち受け入れ 1 件", report)
            self.assertIn("@writer → @chief: 「もっと早く頼んで」 … 断り（速さより正確さを優先する）", report)

    def test_empty_inbox_does_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(night_shift(Path(tmp) / "inbox", Path(tmp), self.nodes, echo=lambda s: None))

    def test_reader_reports_dns_failure_as_fail_not_denial(self):
        r = reader_node(fetch=lambda u: (u, ""), allow=lambda u: "unresolved")
        m = aicl.Message.from_form(aicl.parse_one('(ask #e.1 @e>@reader (read "https://example.org/" $p))'))
        out = r.react(None, "", m)[0]
        self.assertEqual(out.head, "fail")
        self.assertIn("resolve", aicl.to_text(out))

    def test_reader_refuses_local_addresses(self):
        from aicl.research import _public_http
        for u in ("http://127.0.0.1/", "http://localhost:8000/x", "file:///etc/passwd", "ftp://example.com/"):
            self.assertFalse(_public_http(u), u)


if __name__ == "__main__":
    unittest.main()
