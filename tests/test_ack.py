"""One acknowledgement per request: ack-twice, ack-closed, ok-misplaced (SPEC §4.4)."""
import unittest
from pathlib import Path

import aicl
from aicl.validate import validate_conversation

ROOT = Path(__file__).resolve().parents[1]


def codes(src, known=("task", "haiku", "fx-rate"), level=None):
    issues = validate_conversation(aicl.parse_messages(src), known)
    return sorted(i.code for i in issues if level is None or i.level == level)


class AckTests(unittest.TestCase):
    def test_second_ok_to_a_def_is_ack_twice(self):
        # The live Gem slip: do answered with an ok that points at the already-acknowledged def.
        src = ('(def #u.1 @u>@g haiku :gloss (nl en "x")) (ok #g.1 @g>@u ^u.1) '
               '(do #u.2 @u>@g (haiku broccoli)) (ok #g.2 @g>@u ^u.1)')
        self.assertEqual(codes(src, level="error"), ["ack-twice"])
        self.assertIn("open-do", codes(src, level="warning"))            # the do itself was never accepted

    def test_second_ok_to_a_do_is_ack_twice(self):
        src = "(do #u.1 @u>@g (task)) (ok #g.1 @g>@u ^u.1) (ok #g.2 @g>@u ^u.1)"
        self.assertEqual(codes(src, level="error"), ["ack-twice"])

    def test_ok_after_close_is_ack_closed(self):
        for close in ("(done #g.2 @g>@u ^u.1)", "(fail #g.2 @g>@u ^u.1 :code internal :why (x))",
                      "(no #g.2 @g>@u ^u.1 :why (x))"):
            src = f"(do #u.1 @u>@g (task)) (ok #g.1 @g>@u ^u.1) {close} (ok #g.3 @g>@u ^u.1)"
            with self.subTest(close=close):
                self.assertIn("ack-closed", codes(src, known=("task", "x"), level="error"))

    def test_ok_after_retracted_do_is_ack_closed(self):
        src = "(do #u.1 @u>@g (task)) (retract #u.2 @u>@g ^u.1 :why (x)) (ok #g.1 @g>@u ^u.1)"
        self.assertEqual(codes(src, known=("task", "x"), level="error"), ["ack-closed"])

    def test_retracting_an_ok_allows_a_new_one(self):
        src = ("(do #u.1 @u>@g (task)) (ok #g.1 @g>@u ^u.1 :at 2026-11-05T09:00+09:00 :eta PT5M) "
               "(retract #g.2 @g>@u ^g.1 :why (x)) (ok #g.3 @g>@u ^u.1 :at 2026-11-05T09:01+09:00 :eta PT30M) "
               "(done #g.4 @g>@u ^u.1)")
        self.assertEqual(codes(src, known=("task", "x"), level="error"), [])

    def test_ok_to_a_tell_is_misplaced(self):
        src = "(tell #u.1 @u>@g (task)) (ok #g.1 @g>@u ^u.1)"
        self.assertEqual(codes(src), ["ok-misplaced"])

    def test_ok_for_ask_still_wins(self):
        src = "(ask #u.1 @u>@g (task $x)) (ok #g.1 @g>@u ^u.1)"
        self.assertEqual(codes(src, level="error"), ["ok-for-ask"])

    def test_example_16_specimen(self):
        src = (ROOT / "examples" / "16_gem_v03_acceptance.aicl").read_text(encoding="utf-8")
        issues = validate_conversation(aicl.parse_messages(src), ["fx-rate"])
        self.assertEqual(sorted(i.code for i in issues if i.level == "error"),
                         ["ack-twice", "body-required", "dup-id"])


if __name__ == "__main__":
    unittest.main()
