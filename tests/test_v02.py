"""v0.2 rules: retract, status, why-needs-src, def scope, eta on open do."""
import unittest
from pathlib import Path

import aicl
from aicl.validate import validate_conversation, validate_message

ROOT = Path(__file__).resolve().parents[1]
KNOWN = ["meeting", "busy", "calendar-add", "temp", "calendar"]


def codes(issues, level=None):
    return sorted(i.code for i in issues if level is None or i.level == level)


def conv(src, known=KNOWN):
    return validate_conversation(aicl.parse_messages(src), known)


class RetractTests(unittest.TestCase):
    def test_retract_reopens_a_closed_proposal(self):
        src = ("(prop #a.1 @a>@b (meeting)) (acc #b.1 @b>@a ^a.1) "
               "(retract #b.2 @b>@a ^b.1 :why (busy @b)) (rej #b.3 @b>@a ^a.1 :why (busy @b))")
        self.assertEqual(codes(conv(src)), [])                       # no prop-closed any more
        without = "(prop #a.1 @a>@b (meeting)) (acc #b.1 @b>@a ^a.1) (rej #b.3 @b>@a ^a.1 :why (busy @b))"
        self.assertIn("prop-closed", codes(conv(without)))

    def test_retract_must_reference_own_message_and_give_why(self):
        self.assertIn("bad-reply", codes(conv("(prop #a.1 @a>@b (meeting)) (retract #b.1 @b>@a ^a.1 :why (x))", KNOWN + ["x"])))
        self.assertIn("why-required", codes(validate_message(aicl.parse_one("(retract #b.1 @b>@a ^b.0)"))))
        self.assertIn("reply-required", codes(validate_message(aicl.parse_one("(retract #b.1 @b>@a :why (x))"))))

    def test_retract_done_reopens_the_do(self):
        src = ("(do #a.1 @a>@b (calendar-add)) (ok #b.1 @b>@a ^a.1) (done #b.2 @b>@a ^a.1) "
               "(retract #b.3 @b>@a ^b.2 :why (busy @b))")
        self.assertEqual(codes(conv(src)), ["open-do"])             # back to accepted, still open
        self.assertEqual(codes(conv(src + " (fail #b.4 @b>@a ^a.1 :code internal :why (x))", KNOWN + ["x"])), [])

    def test_dense_code_for_retract(self):
        t = aicl.parse_one("(retract #b.2 @b>@a ^b.1 :why (busy @b))")
        self.assertTrue(aicl.to_dense(t).startswith("(B b.2>a ^b.1 "))
        self.assertEqual(aicl.to_text(aicl.from_dense(aicl.to_dense(t))[0]), aicl.to_text(t))


class StatusAndEtaTests(unittest.TestCase):
    def test_status_query_shape_and_values(self):
        self.assertEqual(codes(validate_message(aicl.parse_one("(ask #a.1 @a>@b (status (ref #a.0) $s))"))), [])
        self.assertIn("status-shape", codes(validate_message(aicl.parse_one("(ask #a.1 @a>@b (status a.0 $s))"))))
        good = "(do #a.1 @a>@b (calendar-add)) (ok #b.1 @b>@a ^a.1) (ask #a.2 @a>@b (status (ref #a.1) $s)) (tell #b.2 @b>@a ^a.2 {$s pending})"
        self.assertEqual(codes(conv(good)), ["open-do"])
        bad = good.replace("{$s pending}", "{$s waiting}")
        self.assertIn("status-value", codes(conv(bad)))

    def test_open_do_reports_promised_eta(self):
        issues = conv("(do #a.1 @a>@b (calendar-add)) (ok #b.1 @b>@a ^a.1 :eta PT5M)")
        self.assertEqual([i.code for i in issues], ["open-do"])
        self.assertIn("eta PT5M promised", issues[0].message)


class EvidenceTests(unittest.TestCase):
    def test_answer_to_why_needs_src(self):
        base = "(ask #a.1 @a>@b (temp tokyo $t)) (tell #b.1 @b>@a ^a.1 {$t 14C}) (why #a.2 @a>@b ^b.1) "
        self.assertIn("why-needs-src", codes(conv(base + "(tell #b.2 @b>@a ^a.2 {$t 14C})")))
        self.assertEqual(codes(conv(base + "(tell #b.2 @b>@a ^a.2 {$t 14C} :src (none))")), [])
        self.assertEqual(codes(conv(base + "(tell #b.2 @b>@a ^a.2 {$t 14C} :src (weathernews :kind hourly :value 14C))")), [])


class DefScopeTests(unittest.TestCase):
    def test_pair_def_does_not_bind_third_party(self):
        src = ('(def #a.1 @a>@b foo :gloss (nl en "x")) (ok #b.1 @b>@a ^a.1) '
               '(tell #a.2 @a>@b (foo 1)) (tell #c.1 @c>@b (foo 2))')
        issues = conv(src)
        self.assertEqual([(i.code, i.msg_id) for i in issues], [("unresolved-term", "c.1")])

    def test_broadcast_def_is_shared_at_once(self):
        src = '(def #a.1 @a>* foo :gloss (nl en "x")) (tell #c.1 @c>@b (foo 2))'
        self.assertEqual(codes(conv(src)), [])


class ExampleTests(unittest.TestCase):
    def test_example_08_is_clean(self):
        src = (ROOT / "examples" / "08_retract_and_status.aicl").read_text(encoding="utf-8")
        issues = conv(src)
        self.assertEqual([str(i) for i in issues], [])


if __name__ == "__main__":
    unittest.main()
