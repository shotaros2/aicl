import unittest
from pathlib import Path

import aicl
from aicl import dense
from aicl.model import ModelError, LexError

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted((ROOT / "examples").glob("*.aicl")) + sorted((ROOT / "bench" / "cases").glob("*/aicl.aicl"))


class DenseTests(unittest.TestCase):
    def test_examples_round_trip(self):
        self.assertTrue(FILES)
        for p in FILES:
            terms = aicl.parse(p.read_text(encoding="utf-8"))
            d = dense.dense_document(terms)
            with self.subTest(file=str(p.relative_to(ROOT))):
                self.assertEqual([aicl.to_text(t) for t in dense.from_dense(d)],
                                 [aicl.to_text(t) for t in terms])
                self.assertLess(len(d), len(aicl.canonical_document(terms)))

    def test_shape(self):
        t = aicl.parse_one("(tell #b.1 @b>@a ^a.1 {$t 18.5C} ~0.9 :src jma :at 2026-11-05T09:00+09:00)")
        self.assertEqual(dense.to_dense(t), "(T b.1>a ^a.1 {$t 18.5C} :a 20261105T0900+9 :s jma ~0.9)")

    def test_header_fallback_when_id_does_not_name_sender(self):
        t = aicl.parse_one("(ask #m7 @alice>@bob (x $y))")
        self.assertEqual(dense.to_dense(t), "(A #m7 @alice>@bob (x $y))")
        self.assertEqual(aicl.to_text(dense.from_dense(dense.to_dense(t))[0]), aicl.to_text(t))
        t = aicl.parse_one("(ask #a.1 @a>* (x $y))")
        self.assertEqual(dense.to_dense(t), "(A a.1>* (x $y))")

    def test_header_with_stray_at_is_accepted(self):
        for src in ["(K code.1>@hub ^hub.4)", "(K code.1>hub ^hub.4)"]:
            self.assertEqual(aicl.to_text(dense.from_dense(src)[0]), "(ok #code.1 @code>@hub ^hub.4)")
        self.assertEqual(aicl.to_text(dense.from_dense("(A a.1>@* (x $y))")[0]), "(ask #a.1 @a>* (x $y))")
        with self.assertRaises(aicl.LexError):
            dense.from_dense("(K code.1>#hub ^hub.4)")      # '#' is the ref sigil: still an error

    def test_instants(self):
        cases = {
            "2026-11-05T09:00+09:00": "20261105T0900+9",
            "2026-11-04T08:50Z": "20261104T0850Z",
            "2026-11-04T09:04:12Z": "20261104T090412Z",
            "1969-12-31T23:59-05:30": "19691231T2359-530",
            "2000-02-29T00:00+13:45": "20000229T0000+1345",
        }
        for iso, d in cases.items():
            self.assertEqual(dense.encode_instant(iso), d)
            self.assertEqual(dense.decode_instant(d), iso)
        self.assertEqual(dense.encode_instant("2026-11-04T08:50:00.5-05:00"), "2026-11-04T08:50:00.5-05:00")
        with self.assertRaises(LexError):
            dense.decode_instant("20261104T0850")       # offset is mandatory
        with self.assertRaises(LexError):
            dense.from_dense("(T b.1>a (x :a 20261399T0850Z))")  # invalid calendar date

    def test_act_codes_only_at_head_position(self):
        # 'T' as a plain argument symbol is left alone; only (T … is an act.
        t = dense.from_dense("(T b.1>a ^a.1 [A T X])")[0]
        self.assertEqual(aicl.to_text(t), "(tell #b.1 @b>@a ^a.1 [A T X])")

    def test_reserved_heads_rejected(self):
        with self.assertRaises(ModelError):
            dense.to_dense(aicl.parse_one("(tell #b.1 @b>@a (T 1))"))

    def test_looks_dense(self):
        self.assertTrue(dense.looks_dense("(A a.1>b (x $y))"))
        self.assertTrue(dense.looks_dense("(tell #b.1 @b>@a (x :at 20261105T0900+9))"))
        self.assertFalse(dense.looks_dense("(ask #a.1 @a>@b (x $y))"))


if __name__ == "__main__":
    unittest.main()
