import unittest
from pathlib import Path

import aicl
from aicl.validate import validate_conversation, validate_message

ROOT = Path(__file__).resolve().parents[1]

# Domain terms each example declares in its header comment.
KNOWN = {
    "01_weather.aicl": ["temp", "rain"],
    "02_deploy.aicl": ["deploy-status", "rollout", "error-rate"],
    "03_scheduling.aicl": ["meeting", "busy", "calendar-add", "calendar-event"],
    "04_def_and_clar.aicl": ["balance.available"],
    "05_subscription.aicl": ["alert"],
    "06_broadcast_and_fail.aicl": ["capability", "ocr"],
    "07_cross_vendor_negotiation.aicl": ["busy", "meeting", "calendar-add", "status"],
}

# Warnings an example produces on purpose (terms used before they are resolvable, caught by clar).
EXPECTED_WARNINGS = {
    "04_def_and_clar.aicl": ["unresolved-term", "unresolved-term"],
    "07_cross_vendor_negotiation.aicl": ["open-do"],
}


def codes(issues, level=None):
    return sorted(i.code for i in issues if level is None or i.level == level)


class MessageTests(unittest.TestCase):
    def check(self, src):
        return validate_message(aicl.parse_one(src))

    def test_ok(self):
        self.assertEqual(self.check("(ask #a.1 @a>@b (x $y))"), [])

    def test_missing_reply(self):
        self.assertIn("reply-required", codes(self.check("(ok #b.1 @b>@a)")))

    def test_missing_why_and_code(self):
        self.assertEqual(codes(self.check("(fail #b.1 @b>@a ^a.1)")), ["code-required", "why-required"])
        self.assertIn("unknown-code", codes(self.check("(fail #b.1 @b>@a ^a.1 :code oops :why (x))")))

    def test_var_in_tell(self):
        self.assertIn("var-in-tell", codes(self.check("(tell #b.1 @b>@a ^a.1 (x $y))")))
        self.assertIn("var-in-tell", codes(self.check("(tell #b.1 @b>@a ^a.1 {$y $z})")))
        self.assertEqual(self.check("(tell #b.1 @b>@a ^a.1 {$y 1})"), [])
        self.assertEqual(self.check("(tell #b.1 @b>@a ^a.1 [{$y 1} {$y 2}])"), [])

    def test_nl_shape(self):
        self.assertIn("nl-shape", codes(self.check('(tell #b.1 @b>@a (nl "no lang"))')))
        self.assertEqual(self.check('(tell #b.1 @b>@a (nl en "ok"))'), [])

    def test_nested_act(self):
        self.assertIn("nested-act", codes(self.check("(tell #b.1 @b>@a (ask #x @a>@b (y)))")))

    def test_def_requires_gloss(self):
        self.assertIn("def-gloss", codes(self.check("(def #a.1 @a>@b foo)")))
        self.assertEqual(self.check('(def #a.1 @a>@b foo :gloss (nl en "x"))'), [])

    def test_not_a_message(self):
        self.assertEqual(codes(self.check("(temp tokyo)")), ["structure"])
        self.assertEqual(codes(self.check("(ask (x))")), ["structure"])


class ConversationTests(unittest.TestCase):
    def conv(self, src, known=()):
        return validate_conversation(aicl.parse_messages(src), known)

    def test_examples_have_no_errors(self):
        for p in sorted((ROOT / "examples").glob("*.aicl")):
            with self.subTest(file=p.name):
                issues = self.conv(p.read_text(encoding="utf-8"), KNOWN[p.name])
                self.assertEqual(codes(issues, "error"), [], [str(i) for i in issues])
                self.assertEqual(codes(issues, "warning"), EXPECTED_WARNINGS.get(p.name, []), [str(i) for i in issues])

    def test_duplicate_id(self):
        self.assertIn("dup-id", codes(self.conv("(ask #a.1 @a>@b (x $y)) (ask #a.1 @a>@b (x $z))", ["x"])))

    def test_bad_reply(self):
        self.assertIn("bad-reply", codes(self.conv("(ask #a.1 @a>@b (x $y)) (tell #b.1 @b>@a ^a.9 (x 1))", ["x"])))
        # replying to your own message
        self.assertIn("bad-reply", codes(self.conv("(ask #a.1 @a>@b (x $y)) (tell #a.2 @a>@b ^a.1 (x 1))", ["x"])))

    def test_open_requests_are_warnings(self):
        self.assertEqual(codes(self.conv("(ask #a.1 @a>@b (x $y))", ["x"])), ["open-ask"])
        self.assertEqual(codes(self.conv("(do #a.1 @a>@b (x)) (ok #b.1 @b>@a ^a.1)", ["x"])), ["open-do"])
        self.assertEqual(codes(self.conv("(prop #a.1 @a>@b (x))", ["x"])), ["open-prop"])

    def test_done_without_ok(self):
        self.assertIn("done-without-ok", codes(self.conv("(do #a.1 @a>@b (x)) (done #b.1 @b>@a ^a.1)", ["x"])))

    def test_done_for_ask(self):
        self.assertIn("done-for-ask", codes(self.conv("(ask #a.1 @a>@b (x $y)) (done #b.1 @b>@a ^a.1 (x 1))", ["x"])))

    def test_closed_proposal_cannot_be_reversed(self):
        # Observed live: an agent accepted a proposal, learned a constraint, then sent rej to the same proposal.
        src = ("(prop #a.1 @a>@b (meeting :at 2026-11-06T03:00+09:00)) (acc #b.1 @b>@a ^a.1) "
               "(tell #a.2 @a>@b (busy @b :from 2026-11-06T00:00+09:00 :to 2026-11-06T06:00+09:00)) "
               "(rej #b.2 @b>@a ^a.1 :why (busy @b))")
        self.assertIn("prop-closed", codes(self.conv(src, ["meeting", "busy"])))
        ok = "(prop #a.1 @a>@b (meeting)) (rej #b.1 @b>@a ^a.1 :why (busy @b)) (prop #b.2 @b>@a (meeting)) (acc #a.2 @a>@b ^b.2)"
        self.assertEqual(codes(self.conv(ok, ["meeting", "busy"])), [])

    def test_def_makes_term_known(self):
        src = '(def #a.1 @a>@b foo :gloss (nl en "x")) (ok #b.1 @b>@a ^a.1) (ask #a.2 @a>@b (foo $v)) (tell #b.2 @b>@a ^a.2 (foo 1))'
        self.assertEqual(codes(self.conv(src)), [])
        src_no_ok = '(def #a.1 @a>@b foo :gloss (nl en "x")) (ask #a.2 @a>@b (foo $v)) (tell #b.2 @b>@a ^a.2 (foo 1))'
        self.assertIn("unresolved-term", codes(self.conv(src_no_ok)))

    def test_namespaced_terms_resolve(self):
        self.assertEqual(codes(self.conv("(tell #a.1 @a>@b (schema:Person :name \"x\"))")), [])

    def test_nl_ratio(self):
        msgs = aicl.parse_messages('(tell #a.1 @a>@b (nl en "hello"))')
        self.assertEqual(aicl.nl_ratio(msgs), 1.0)
        msgs = aicl.parse_messages('(tell #a.1 @a>@b (x 1))')
        self.assertEqual(aicl.nl_ratio(msgs), 0.0)


if __name__ == "__main__":
    unittest.main()
