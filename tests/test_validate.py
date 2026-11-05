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
    "08_retract_and_status.aicl": ["meeting", "busy", "calendar-add", "temp"],
    "09_dola_image_specialist.aicl": [],
    "10_deadline_negotiation.aicl": ["log-summary"],
    "11_standard_codebook.aicl": ["meeting", "busy", "calendar-add", "calendar-event"],
    "12_typed_def.aicl": [],
    "13_dola_research_task.aicl": [],
    "14_signed_identity.aicl": ["temp"],
    "15_blob_and_part.aicl": ["top-terms", "term"],
    "16_gem_v03_acceptance.aicl": ["fx-rate"],
    "17_signed_agreement.aicl": ["meeting", "busy"],
    "18_muse_v03_acceptance.aicl": ["temp", "haiku"],
    "19_browser_relay_agreement.aicl": ["meeting", "busy"],
    "20_two_windows_agreement.aicl": ["meeting", "busy"],
    "21_dola_agreement.aicl": ["meeting", "busy"],
    "22_gemini_drives_claude.aicl": ["meeting", "busy"],
    "23_autonomous_network.aicl": ["doc", "publish", "weather-now", "weather", "source"],
}

# Warnings an example produces on purpose (terms used before they are resolvable, caught by clar;
# 09 is a verbatim record from before :at-anchored etas; 10 documents its own warnings in its header).
EXPECTED_WARNINGS = {
    "04_def_and_clar.aicl": ["unresolved-term", "unresolved-term"],
    "07_cross_vendor_negotiation.aicl": ["open-do"],
    "09_dola_image_specialist.aicl": ["eta-unanchored"],
    "10_deadline_negotiation.aicl": ["eta-overrun", "stale-reply", "unresolved-term", "unresolved-term"],
    "11_standard_codebook.aicl": ["open-ask", "open-do", "status-unclosed"],
    "13_dola_research_task.aicl": ["open-ask", "unresolved-term", "unresolved-term", "unresolved-term"],
    "16_gem_v03_acceptance.aicl": ["open-do", "status-unclosed"],
    "18_muse_v03_acceptance.aicl": ["eta-unanchored", "unresolved-term"],
}

# Errors an example keeps on purpose, as a specimen its header explains (11: a live run where
# the performer answered an ask with `done`; 13: one where it acknowledged an ask with `ok`).
EXPECTED_ERRORS = {
    "11_standard_codebook.aicl": ["done-for-ask"],
    "13_dola_research_task.aicl": ["ok-for-ask"],
    "16_gem_v03_acceptance.aicl": ["ack-twice", "body-required", "dup-id"],
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
                self.assertEqual(codes(issues, "error"), EXPECTED_ERRORS.get(p.name, []), [str(i) for i in issues])
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

    def test_ok_for_ask(self):
        # Observed live: Dola acknowledged an ask with ok, then lost track of it.
        self.assertIn("ok-for-ask", codes(self.conv("(ask #a.1 @a>@b (x $y)) (ok #b.1 @b>@a ^a.1)", ["x"])))
        self.assertNotIn("ok-for-ask", codes(self.conv("(do #a.1 @a>@b (x)) (ok #b.1 @b>@a ^a.1)", ["x"])))

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

    def test_eta_unanchored(self):
        self.assertIn("eta-unanchored", codes(self.conv("(do #a.1 @a>@b (x)) (ok #b.1 @b>@a ^a.1 :eta PT5M) "
                                                        "(done #b.2 @b>@a ^a.1 (x))", ["x"])))

    def test_eta_overrun_is_message_arithmetic(self):
        # Observed live: do :by 10:15, ok :at 10:04 :eta PT25M — the conflict is checkable with no clock.
        src = ("(do #a.1 @a>@b (x) :by 2026-11-04T10:15+09:00) "
               "(ok #b.1 @b>@a ^a.1 :at 2026-11-04T10:04+09:00 :eta PT25M) "
               "(done #b.2 @b>@a ^a.1 (x))")
        self.assertIn("eta-overrun", codes(self.conv(src, ["x"])))
        fits = ("(do #a.1 @a>@b (x) :by 2026-11-04T10:15+09:00) "
                "(ok #b.1 @b>@a ^a.1 :at 2026-11-04T10:04+09:00 :eta PT5M) "
                "(done #b.2 @b>@a ^a.1 (x))")
        self.assertNotIn("eta-overrun", codes(self.conv(fits, ["x"])))

    def test_stale_reply_after_retract(self):
        # Observed live: a performer answered a retract with fail "cannot retract".
        src = ("(do #a.1 @a>@b (x)) (ok #b.1 @b>@a ^a.1) "
               "(retract #a.2 @a>@b ^a.1 :why (y)) "
               "(fail #b.2 @b>@a ^a.1 :code conflict :why (y))")
        self.assertIn("stale-reply", codes(self.conv(src, ["x", "y"])))

    def test_deadlines_with_now(self):
        from aicl.validate import parse_now, validate_conversation
        msgs = aicl.parse_messages("(do #a.1 @a>@b (x) :by 2026-11-04T10:15+09:00) "
                                   "(ok #b.1 @b>@a ^a.1 :at 2026-11-04T10:04+09:00 :eta PT5M)")
        before = validate_conversation(msgs, ["x"], now=parse_now("2026-11-04T10:00+09:00"))
        self.assertNotIn("deadline-passed", codes(before))
        after = validate_conversation(msgs, ["x"], now=parse_now("2026-11-04T10:16+09:00"))
        self.assertIn("deadline-passed", codes(after))
        # :at + :eta elapsed on a do without :by
        msgs = aicl.parse_messages("(do #a.1 @a>@b (x)) "
                                   "(ok #b.1 @b>@a ^a.1 :at 2026-11-04T10:04+09:00 :eta PT5M)")
        self.assertIn("eta-expired", codes(validate_conversation(msgs, ["x"], now=parse_now("2026-11-04T10:30+09:00"))))

    def test_typed_signature_checks(self):
        define = ('(def #a.1 @a>@b fx-rate :gloss (nl en "units of quote currency per unit of base") '
                  ':args [(base symbol) (quote symbol) (at instant)] :ret number) '
                  '(ok #b.1 @b>@a ^a.1) ')
        good = define + ('(ask #a.2 @a>@b (fx-rate usd jpy 2026-11-04T10:00+09:00 $r)) '
                         '(tell #b.2 @b>@a ^a.2 {$r 152.31} :src (boj :uri "https://example" :kind daily))')
        self.assertEqual(codes(self.conv(good)), [])
        # a number where (base symbol) is declared
        bad_arg = good.replace("(fx-rate usd", "(fx-rate 840")
        self.assertIn("sig-type", codes(self.conv(bad_arg)))
        # a quantity bound where :ret number is declared
        bad_ret = good.replace("{$r 152.31}", "{$r 152.31JPY}")
        self.assertIn("sig-ret", codes(self.conv(bad_ret)))
        # one positional argument too many
        bad_arity = good.replace("2026-11-04T10:00+09:00 $r", "2026-11-04T10:00+09:00 extra $r")
        self.assertIn("sig-arity", codes(self.conv(bad_arity)))

    def test_typed_signature_qty_and_list(self):
        src = ('(def #a.1 @a>@b balance.available :gloss (nl en "spendable balance of an account") '
               ':args [(acct symbol)] :ret (qty USD)) (ok #b.1 @b>@a ^a.1) '
               '(ask #a.2 @a>@b (balance.available acct-1 $b)) ')
        self.assertEqual(codes(self.conv(src + "(tell #b.2 @b>@a ^a.2 {$b 1520.4USD})")), [])
        self.assertIn("sig-ret", codes(self.conv(src + "(tell #b.2 @b>@a ^a.2 {$b 1520.4})")))
        self.assertIn("sig-ret", codes(self.conv(src + "(tell #b.2 @b>@a ^a.2 {$b 1520.4EUR})")))
        lst = ('(def #a.1 @a>@b attendees :gloss (nl en "who is in the meeting") '
               ':args [(mtg ref)] :ret (list agent)) (ok #b.1 @b>@a ^a.1) '
               '(ask #a.2 @a>@b (attendees (ref #a.1) $who)) ')
        self.assertEqual(codes(self.conv(lst + "(tell #b.2 @b>@a ^a.2 {$who [@a @b]})")), [])
        self.assertIn("sig-ret", codes(self.conv(lst + "(tell #b.2 @b>@a ^a.2 {$who [@a bob]})")))

    def test_untyped_args_still_work_and_sorts_are_unchecked(self):
        # pre-0.3 defs: bare names, or sort names as types -> documentation, no checks
        src = ('(def #a.1 @a>@b risk-score :gloss (nl en "x") :args [transaction] :ret number) '
               '(ok #b.1 @b>@a ^a.1) (ask #a.2 @a>@b (risk-score txn-77 $r)) '
               '(tell #b.2 @b>@a ^a.2 {$r 0.12})')
        self.assertEqual(codes(self.conv(src)), [])
        self.assertIn("sig-ret", codes(self.conv(src.replace("{$r 0.12}", '{$r "low"}'))))

    def test_def_sig_malformed(self):
        self.assertIn("def-sig", codes(validate_message(aicl.parse_one(
            '(def #a.1 @a>@b foo :gloss (nl en "x") :args [(x number extra)])'))))
        self.assertIn("def-sig", codes(validate_message(aicl.parse_one(
            '(def #a.1 @a>@b foo :gloss (nl en "x") :ret [number])'))))

    def test_part_slices(self):
        base = ("(ask #a.1 @a>@b (x $v)) "
                "(tell #b.1 @b>@a ^a.1 {$v [1 2]} :part [1 2]) ")
        # incomplete: the ask stays open and the missing slice is named
        half = codes(self.conv(base, ["x"]))
        self.assertIn("open-ask", half)
        self.assertIn("part-missing", half)
        # complete: clean
        full = base + "(tell #b.2 @b>@a ^a.1 {$v [3]} :part [2 2])"
        self.assertEqual(codes(self.conv(full, ["x"])), [])
        # conflicting n, repeated i
        clash = base + "(tell #b.2 @b>@a ^a.1 {$v [3]} :part [1 3])"
        self.assertIn("part-mismatch", codes(self.conv(clash, ["x"])))

    def test_part_shape_and_done_slices(self):
        self.assertIn("part-shape", codes(validate_message(aicl.parse_one(
            "(tell #b.1 @b>@a ^a.1 (x) :part [3 2])"))))
        self.assertIn("part-shape", codes(validate_message(aicl.parse_one(
            "(ask #a.1 @a>@b (x $v) :part [1 2])"))))
        src = ("(do #a.1 @a>@b (x)) (ok #b.1 @b>@a ^a.1) "
               "(done #b.2 @b>@a ^a.1 (x 1) :part [1 2])")
        self.assertIn("part-missing", codes(self.conv(src, ["x"])))
        done = src + " (done #b.3 @b>@a ^a.1 (x 2) :part [2 2])"
        self.assertEqual(codes(self.conv(done, ["x"])), [])

    def test_blob_shape(self):
        ok = "(tell #b.1 @b>@a ^a.1 (blob sha256:" + "0" * 64 + " :media \"image/png\" :bytes 10))"
        self.assertEqual(codes(validate_message(aicl.parse_one(ok))), [])
        for bad in ["(blob sha999:" + "0" * 64 + ")", "(blob sha256:abc)", "(blob)",
                    "(blob sha256:" + "0" * 64 + " :bytes -1)"]:
            with self.subTest(bad=bad):
                self.assertIn("blob-shape", codes(validate_message(aicl.parse_one(
                    f"(tell #b.1 @b>@a ^a.1 {bad})"))))

    def test_status_unclosed(self):
        # Observed live: status answered {$s done}, but the real done never came.
        src = ("(do #a.1 @a>@b (x)) (ok #b.1 @b>@a ^a.1) "
               "(ask #a.2 @a>@b (status (ref #a.1) $s)) (tell #b.2 @b>@a ^a.2 {$s done})")
        self.assertIn("status-unclosed", codes(self.conv(src, ["x"])))
        closed = src + " (done #b.3 @b>@a ^a.1 (x))"
        self.assertNotIn("status-unclosed", codes(self.conv(closed, ["x"])))
        pending = src.replace("{$s done}", "{$s pending}")
        self.assertNotIn("status-unclosed", codes(self.conv(pending, ["x"])))

    def test_nl_ratio(self):
        msgs = aicl.parse_messages('(tell #a.1 @a>@b (nl en "hello"))')
        self.assertEqual(aicl.nl_ratio(msgs), 1.0)
        msgs = aicl.parse_messages('(tell #a.1 @a>@b (x 1))')
        self.assertEqual(aicl.nl_ratio(msgs), 0.0)


if __name__ == "__main__":
    unittest.main()
