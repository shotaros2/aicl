import unittest
from pathlib import Path

import aicl
from aicl.codebook import Codebook
from aicl.model import ModelError

ROOT = Path(__file__).resolve().parents[1]
BENCH = Codebook.load(str(ROOT / "codebooks" / "bench.json"))
IMG = Codebook.load(str(ROOT / "codebooks" / "imagegen.json"))
FILES = sorted((ROOT / "examples").glob("*.aicl")) + sorted((ROOT / "bench" / "cases").glob("*/aicl.aicl"))


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

    def test_truncation_forms_warn(self):
        cb = Codebook({"deploy-status": ["deploy", "DeployStatus"], "rollout": ["roll", "展開"], "error-rate": ["err"]})
        self.assertEqual(len(cb.warnings), 3)
        self.assertTrue(all("truncation" in w for w in cb.warnings))
        self.assertEqual(Codebook({"deploy-status": ["DeployStatus", "デプロイ状態"]}).warnings, [])
        self.assertEqual(BENCH.warnings, [])
        self.assertEqual(IMG.warnings, [])

    def test_non_ascii_forms_allowed(self):
        cb = Codebook({"night": ["夜", "Night"]})
        self.assertEqual(cb.form_to_concept["夜"], "night")

    def test_id_is_content_hash(self):
        a = Codebook({"x-thing": ["xt", "XT"]})
        b = Codebook({"x-thing": ["XT", "xt"]})   # same forms, different order -> different table
        self.assertTrue(a.id.startswith("sha256:"))
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(a.id, Codebook({"x-thing": ["xt", "XT"]}).id)


class StandardCodebookTests(unittest.TestCase):
    """SPEC §8.2: standard codebooks are immutable — the id names the exact table.

    If one of these digest assertions fails, you changed a published table: revert it
    and publish the change as a NEW codebook with a new id (aicl.sched.2, …)."""

    SCHED = Codebook.load(str(ROOT / "codebooks" / "scheduling.json"))
    DEPLOY = Codebook.load(str(ROOT / "codebooks" / "deployment.json"))

    def test_published_ids_and_frozen_digests(self):
        self.assertEqual(self.SCHED.published_id, "aicl.sched.1")
        self.assertEqual(self.SCHED.id, "sha256:ce5a0e068cc7f8db")
        self.assertEqual(self.DEPLOY.published_id, "aicl.deploy.1")
        self.assertEqual(self.DEPLOY.id, "sha256:9a2788c5d6f9c34c")

    def test_no_warnings_and_ids_are_symbols(self):
        from aicl.lexer import classify_atom
        from aicl.model import Symbol
        for cb in (self.SCHED, self.DEPLOY):
            self.assertEqual(cb.warnings, [])
            self.assertIsInstance(classify_atom(cb.published_id), Symbol)

    def test_cover_their_domain_examples(self):
        sched = aicl.parse((ROOT / "examples" / "03_scheduling.aicl").read_text(encoding="utf-8"))
        packed = "\n".join(self.SCHED.pack_text(t, len) for t in sched)
        self.assertEqual([aicl.to_text(t) for t in self.SCHED.unpack(packed)],
                         [aicl.to_text(t) for t in sched])
        deploy = aicl.parse((ROOT / "examples" / "02_deploy.aicl").read_text(encoding="utf-8"))
        packed = "\n".join(self.DEPLOY.pack_text(t, len) for t in deploy)
        self.assertEqual([aicl.to_text(t) for t in self.DEPLOY.unpack(packed)],
                         [aicl.to_text(t) for t in deploy])

    def test_handshake_form_parses(self):
        t = aicl.parse_one("(ask #a.1 @a>@b (codebook aicl.sched.1 $digest))")
        self.assertEqual(aicl.to_text(t), "(ask #a.1 @a>@b (codebook aicl.sched.1 $digest))")
        self.assertEqual(aicl.validate_message(t), [])


class PackTests(unittest.TestCase):
    def test_choose_cheapest_by_chars(self):
        best = IMG.choose(len)
        self.assertEqual(best["photorealistic"], "写実")   # 2 chars
        self.assertEqual(best["tokyo"], "東京")
        self.assertEqual(best["png"], "png")              # tie -> concept id itself

    def test_pack_unpack_round_trip_all_files(self):
        for cb in (BENCH, IMG):
            for counter in (len, aicl.tokens.count):
                for p in FILES:
                    terms = aicl.parse(p.read_text(encoding="utf-8"))
                    for dense in (True, False):
                        packed = "\n".join(cb.pack_text(t, counter, dense=dense) for t in terms)
                        back = cb.unpack(packed)
                        with self.subTest(file=p.name, cb=cb.name, dense=dense):
                            self.assertEqual([aicl.to_text(t) for t in back], [aicl.to_text(t) for t in terms])

    def test_keywords_are_packed_too(self):
        t = aicl.parse_one("(do #u.1 @u>@g (generate-image :scene (cityscape tokyo :time night) :position background))")
        packed = IMG.pack_text(t, len)
        self.assertIn(":位置 背景", packed)
        self.assertIn("(都市景観 東京 :時刻 夜)", packed)
        self.assertEqual(aicl.to_text(IMG.unpack(packed)[0]), aicl.to_text(t))

    def test_core_vocabulary_never_packed(self):
        t = aicl.parse_one("(tell #b.1 @b>@a ^a.1 {$t 18.5C} ~0.9 :src jma :at 2026-11-05T09:00+09:00)")
        packed = BENCH.pack_text(t, len)
        self.assertTrue(packed.startswith("(T b.1>a ^a.1 {$t 18.5C} :a 20261105T0900+9 :s "))

    def test_rule_3_unknown_forms_are_reported_not_guessed(self):
        text = "(T b.1>a ^a.1 (気温 東京 夜))"          # 夜 is not in the bench codebook
        self.assertEqual(BENCH.unresolved_forms(text), ["夜"])
        with self.assertRaises(aicl.LexError):
            BENCH.unpack(text)
        self.assertEqual(BENCH.unresolved_forms("(T b.1>a ^a.1 (気温 東京))"), [])

    def test_packing_is_a_pure_encoding(self):
        # Canonical form, digest and validation are unaffected by packing.
        src = (ROOT / "examples" / "02_deploy.aicl").read_text(encoding="utf-8")
        msgs = aicl.parse_messages(src)
        packed = "\n".join(BENCH.pack_text(m.to_form()) for m in msgs)
        back = [aicl.Message.from_form(t) for t in BENCH.unpack(packed)]
        self.assertEqual([aicl.digest(m.to_form()) for m in back], [aicl.digest(m.to_form()) for m in msgs])
        issues = aicl.validate_conversation(back, list(BENCH.concepts))
        self.assertEqual([i for i in issues if i.level == "error"], [])


if __name__ == "__main__":
    unittest.main()
