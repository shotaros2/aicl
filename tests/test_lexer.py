import unittest

from koine.lexer import ConfTok, classify_atom, normalize_instant, tokenize
from koine.model import (
    Agent, Date, Duration, Instant, Keyword, LexError, Quantity, Ref, ReplyRef,
    Route, Symbol, Var,
)


class ClassifyTests(unittest.TestCase):
    def test_sigils(self):
        self.assertEqual(classify_atom("@alice"), Agent("alice"))
        self.assertEqual(classify_atom("@a>@b"), Route("a", "b"))
        self.assertEqual(classify_atom("@a>*"), Route("a", "*"))
        self.assertEqual(classify_atom("#a.1"), Ref("a.1"))
        self.assertEqual(classify_atom("^a.1"), ReplyRef("a.1"))
        self.assertEqual(classify_atom("$t"), Var("t"))
        self.assertEqual(classify_atom(":unit"), Keyword("unit"))
        self.assertEqual(classify_atom("~0.85"), ConfTok(0.85))
        self.assertEqual(classify_atom("~1"), ConfTok(1.0))

    def test_literals(self):
        self.assertIs(classify_atom("true"), True)
        self.assertIs(classify_atom("null"), None)
        self.assertEqual(classify_atom("42"), 42)
        self.assertEqual(classify_atom("-3.5"), -3.5)
        self.assertEqual(classify_atom("6.02e23"), 6.02e23)
        self.assertEqual(classify_atom("18.5C"), Quantity(18.5, "C"))
        self.assertEqual(classify_atom("0.5%"), Quantity(0.5, "%"))
        self.assertEqual(classify_atom("3m/s^2"), Quantity(3, "m/s^2"))
        self.assertEqual(classify_atom("2026-11-04"), Date("2026-11-04"))
        self.assertEqual(classify_atom("PT30M"), Duration("PT30M"))
        self.assertEqual(classify_atom("P1DT2H"), Duration("P1DT2H"))
        self.assertEqual(classify_atom("PT"), Symbol("PT"))  # not a duration
        self.assertEqual(classify_atom("schema:Person"), Symbol("schema:Person"))
        self.assertEqual(classify_atom("<="), Symbol("<="))

    def test_instant_normalisation(self):
        self.assertEqual(normalize_instant("2026-11-04T08:50:00Z"), "2026-11-04T08:50Z")
        self.assertEqual(normalize_instant("2026-11-04T08:50:00+00:00"), "2026-11-04T08:50Z")
        self.assertEqual(normalize_instant("2026-11-04T08:50:30+09:00"), "2026-11-04T08:50:30+09:00")
        self.assertEqual(normalize_instant("2026-11-04T08:50+09:00"), "2026-11-04T08:50+09:00")
        self.assertEqual(normalize_instant("2026-11-04T08:50:00.500-05:00"), "2026-11-04T08:50:00.5-05:00")
        self.assertEqual(classify_atom("2026-11-04T08:50:00Z"), Instant("2026-11-04T08:50Z"))

    def test_rejects(self):
        for bad in ["~1.5", "5-3", "+", "2026-13-40", "@", "$", "#", "@a>", "1.2.3", "2026-11-04T09:00"]:
            with self.subTest(bad=bad):
                with self.assertRaises(LexError):
                    classify_atom(bad)

    def test_tokenize_positions_and_comments(self):
        toks = list(tokenize("(a ; comment\n  \"x\\ny\")"))
        self.assertEqual(len(toks), 4)
        self.assertEqual(toks[2].value.text, "x\ny")
        self.assertEqual((toks[2].line, toks[2].col), (2, 3))

    def test_unterminated_string(self):
        with self.assertRaises(LexError):
            list(tokenize('(a "abc)'))


if __name__ == "__main__":
    unittest.main()
