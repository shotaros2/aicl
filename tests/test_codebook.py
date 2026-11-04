import unittest
from pathlib import Path

import koine
from koine.codebook import Codebook
from koine.model import ModelError

ROOT = Path(__file__).resolve().parents[1]
BENCH = Codebook.load(str(ROOT / "codebooks" / "bench.json"))
IMG = Codebook.load(str(ROOT / "codebooks" / "imagegen.json"))
FILES = sorted((ROOT / "examples").glob("*.koine")) + sorted((ROOT / "bench" / "cases").glob("*/koine.koine"))


class ValidationTests(unittest.TestCase):
    def test_rule_2_injective(self):
        with self.assertRaises(ModelError):
            Codebook({"a-thing": ["xx"], "b-thing": ["xx"]})
        with self.assertRaises(ModelError):
            Codebook({"a-thing": ["b-thing"], "b-thing": []})   # form equals another concept id

    def test_reserved_and_malformed(self):
        for concepts in [
            {"ask": ["q"]},                 # core act as concept
            {"at": ["when"]},               # head key as concept
            {"A": ["aa"]},                  # single capital
            {"thing": ["A"]},               # single-letter form
            {"thing": ["true"]},            # reserved word
            {"thing": ["12px"]},            # reads as a quantity
            {"thing": ["@me"]},             # sigil
            {"thing": ["src"]},             # head key name
            {"thing": ["a>b"]},             # would read as a dense header
            {"thing": ["x y"]},             # whitespace
        ]:
            with self.subTest(concepts=concepts):
                with self.assertRaises(ModelError):
                    Codebook(concepts)

    def test_non_ascii_forms_allowed(self):
        cb = Codebook({"night": ["夜", "Night"]})
        self.assertEqual(cb.form_to_concept["夜"], "night")

    def test_id_is_content_hash(self):
        a = Codebook({"x-thing": ["xt", "XT"]})
        b = Codebook({"x-thing": ["XT", "xt"]})   # same forms, different order -> different table
        self.assertTrue(a.id.startswith("sha256:"))
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(a.id, Codebook({"x-thing": ["xt", "XT"]}).id)


class PackTests(unittest.TestCase):
    def test_choose_cheapest_by_chars(self):
        best = IMG.choose(len)
        self.assertEqual(best["photorealistic"], "写実")   # 2 chars
        self.assertEqual(best["tokyo"], "東京")
        self.assertEqual(best["png"], "png")              # tie -> concept id itself

    def test_pack_unpack_round_trip_all_files(self):
        for cb in (BENCH, IMG):
            for counter in (len, koine.tokens.count):
                for p in FILES:
                    terms = koine.parse(p.read_text(encoding="utf-8"))
                    for dense in (True, False):
                        packed = "\n".join(cb.pack_text(t, counter, dense=dense) for t in terms)
                        back = cb.unpack(packed)
                        with self.subTest(file=p.name, cb=cb.name, dense=dense):
                            self.assertEqual([koine.to_text(t) for t in back], [koine.to_text(t) for t in terms])

    def test_keywords_are_packed_too(self):
        t = koine.parse_one("(do #u.1 @u>@g (generate-image :scene (cityscape tokyo :time night) :position background))")
        packed = IMG.pack_text(t, len)
        self.assertIn(":位置 背景", packed)
        self.assertIn("(city 東京 :時刻 夜)", packed)   # 'city' and '都市景観' tie on chars; lexicographic tie-break
        self.assertEqual(koine.to_text(IMG.unpack(packed)[0]), koine.to_text(t))

    def test_core_vocabulary_never_packed(self):
        t = koine.parse_one("(tell #b.1 @b>@a ^a.1 {$t 18.5C} ~0.9 :src jma :at 2026-11-05T09:00+09:00)")
        packed = BENCH.pack_text(t, len)
        self.assertTrue(packed.startswith("(T b.1>a ^a.1 {$t 18.5C} :a 20261105T0900+9 :s "))

    def test_rule_3_unknown_forms_are_reported_not_guessed(self):
        text = "(T b.1>a ^a.1 (気温 東京 夜))"          # 夜 is not in the bench codebook
        self.assertEqual(BENCH.unresolved_forms(text), ["夜"])
        with self.assertRaises(koine.LexError):
            BENCH.unpack(text)
        self.assertEqual(BENCH.unresolved_forms("(T b.1>a ^a.1 (気温 東京))"), [])

    def test_packing_is_a_pure_encoding(self):
        # Canonical form, digest and validation are unaffected by packing.
        src = (ROOT / "examples" / "02_deploy.koine").read_text(encoding="utf-8")
        msgs = koine.parse_messages(src)
        packed = "\n".join(BENCH.pack_text(m.to_form()) for m in msgs)
        back = [koine.Message.from_form(t) for t in BENCH.unpack(packed)]
        self.assertEqual([koine.digest(m.to_form()) for m in back], [koine.digest(m.to_form()) for m in msgs])
        issues = koine.validate_conversation(back, list(BENCH.concepts))
        self.assertEqual([i for i in issues if i.level == "error"], [])


if __name__ == "__main__":
    unittest.main()
