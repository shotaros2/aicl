import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

import koine
from koine.codebook import Codebook

import readback  # evals/readback.py

CB = Codebook.load(str(ROOT / "codebooks" / "bench.json"))


class ReadbackEvalTests(unittest.TestCase):
    def test_cases_cover_every_message_and_round_trip(self):
        cases = readback.build_cases(CB, len)
        self.assertGreater(len(cases), 30)
        for c in cases:
            for enc, inp in c["inputs"].items():
                # the library itself must read every encoding back perfectly
                got = koine.to_text(CB.unpack(inp)[0])
                self.assertEqual(got, c["expected"], (enc, inp))

    def test_score_canonicalises_and_tolerates_fences(self):
        exp = "(ask #a.1 @a>@b (temp tokyo $t :unit C))"
        self.assertEqual(readback.score("(ask #a.1 @a>@b (temp tokyo $t :unit C))", exp), (True, exp))
        self.assertEqual(readback.score("(ask @a>@b #a.1 (temp tokyo :unit C $t))", exp)[0], True)   # header/keyword order is free
        self.assertEqual(readback.score("(ask #a.1 @a>@b (temp $t tokyo :unit C))", exp)[0], False)  # positional order is not
        self.assertEqual(readback.score("```koine\n(ask #a.1 @a>@b (temp tokyo $t :unit C))\n```", exp)[0], True)
        self.assertEqual(readback.score("(ask #a.1 @a>@b (temp tokyo $t", exp)[0], False)
        self.assertEqual(readback.score("Sure! (ask ...)", exp)[0], False)

    def test_run_with_stub_models(self):
        cases = readback.build_cases(CB, len)[:5]
        perfect = lambda system, user: koine.to_text(CB.unpack(user)[0])   # a model that decodes correctly
        lazy = lambda system, user: user                                     # a model that echoes the input
        r = readback.run(cases, perfect, counter=len)
        self.assertTrue(all(v["ok"] == v["n"] == 5 for v in r.values()))
        r = readback.run(cases, lazy, counter=len)
        self.assertEqual(r["readable"]["ok"], 5)
        self.assertEqual(r["packed-chars"]["ok"], 0)
        self.assertEqual(len(r["packed-chars"]["failures"]), 5)
        self.assertIn("accuracy", readback.report(r))

    def test_system_prompt_lists_codes_and_forms(self):
        s = readback.system_prompt(CB)
        self.assertIn("T=tell", s)
        self.assertIn(":s=:src", s)
        self.assertIn("deploy-status:", s)


if __name__ == "__main__":
    unittest.main()
