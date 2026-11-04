import unittest
from pathlib import Path

import koine
from koine import cbor_codec, json_codec
from koine.model import Form, KList, KMap, ParseError, Quantity, Str, Symbol

EXAMPLES = sorted((Path(__file__).resolve().parents[1] / "examples").glob("*.koine"))


class ParseTests(unittest.TestCase):
    def test_form_kw_and_conf(self):
        f = koine.parse_one("(temp tokyo 18.5C :unit C ~0.9)")
        self.assertEqual(f.head, "temp")
        self.assertEqual(f.args, [Symbol("tokyo"), Quantity(18.5, "C")])
        self.assertEqual(f.kw, {"unit": Symbol("C")})
        self.assertEqual(f.conf, 0.9)

    def test_list_and_map(self):
        t = koine.parse_one("[1 [2 3] {k \"v\" 2 (f)}]")
        self.assertIsInstance(t, KList)
        self.assertIsInstance(t.items[2], KMap)
        self.assertEqual(koine.to_text(t), '[1 [2 3] {2 (f) k "v"}]')

    def test_errors(self):
        for bad in ["(", "(1 2)", "(a :k)", "(a :k 1 :k 2)", "(a ~0.5 ~0.6)", "{a}", "~0.5", "(a))"]:
            with self.subTest(bad=bad):
                with self.assertRaises(ParseError):
                    koine.parse_one(bad)


class CanonicalTests(unittest.TestCase):
    def test_reorders_message_head_and_sorts_kw(self):
        src = "(tell @b>@a ^a.1 (x) :src s #b.1 :conv c ~0.5)"
        self.assertEqual(koine.to_text(koine.parse_one(src)),
                         "(tell #b.1 @b>@a ^a.1 (x) :conv c :src s ~0.5)")

    def test_numbers(self):
        self.assertEqual(koine.to_text(koine.parse_one("[-0.0 18.0 1e3 1e21 0.1 +5 6.02e23]")),
                         "[0 18 1000 1e21 0.1 5 6.02e23]")

    def test_strings(self):
        s = Str('a"b\\c\n\té')
        self.assertEqual(koine.to_text(koine.parse_one(koine.to_text(s))), koine.to_text(s))

    def test_known_digest(self):
        # Guards against accidental changes to the canonical form.
        self.assertEqual(koine.digest(koine.parse_one("(ask #a.1 @a>@b (deploy-status build-4821 $s))")),
                         "707c831f31a572f9be8cdbe6c994e6d60ed29b888410efaa663a0805b1b42575")

    def test_pretty_is_semantically_identical(self):
        for p in EXAMPLES:
            for t in koine.parse(p.read_text(encoding="utf-8")):
                self.assertEqual(koine.to_text(koine.parse_one(koine.pretty(t, width=40))), koine.to_text(t))


class RoundTripTests(unittest.TestCase):
    def test_examples_round_trip_all_encodings(self):
        self.assertTrue(EXAMPLES)
        for p in EXAMPLES:
            for t in koine.parse(p.read_text(encoding="utf-8")):
                c = koine.to_text(t)
                with self.subTest(file=p.name, msg=c[:40]):
                    self.assertEqual(koine.to_text(koine.parse_one(c)), c)
                    self.assertEqual(koine.to_text(json_codec.loads(json_codec.dumps(t))), c)
                    self.assertEqual(koine.to_text(cbor_codec.from_cbor(cbor_codec.to_cbor(t))), c)
                    self.assertEqual(koine.digest(json_codec.loads(json_codec.dumps(t))), koine.digest(t))

    def test_binding_map(self):
        t = koine.parse_one("(tell #b.1 @b>@a ^a.1 {$t 18.5C $s (finished :at 2026-11-04T08:50Z)})")
        self.assertEqual(koine.to_text(t), "(tell #b.1 @b>@a ^a.1 {$s (finished :at 2026-11-04T08:50Z) $t 18.5C})")
        self.assertEqual(json_codec.to_json(t)["a"][3], {"map": [["$t", {"q": 18.5, "u": "C"}],
                                                                  ["$s", {"f": "finished", "a": [], "k": {"at": {"t": "2026-11-04T08:50Z"}}}]]})

    def test_json_shape(self):
        t = koine.parse_one('(tell #b.1 @b>@a ^a.1 (temp tokyo 18.5C :at 2026-11-04T00:00:00Z) ~0.9 :src jma)')
        self.assertEqual(json_codec.to_json(t), {
            "f": "tell",
            "a": ["#b.1", "@b>@a", "^a.1",
                  {"f": "temp", "a": ["tokyo", {"q": 18.5, "u": "C"}], "k": {"at": {"t": "2026-11-04T00:00Z"}}}],
            "k": {"src": "jma"}, "c": 0.9,
        })
        self.assertEqual(json_codec.to_json(Str("x")), {"s": "x"})

    def test_cbor_primitives(self):
        for obj in [0, 23, 24, 255, 256, 65536, -1, -500, 1.5, 0.1, 1e300, "é", [], {}, {"b": 1, "a": [None, True]}]:
            with self.subTest(obj=obj):
                self.assertEqual(cbor_codec.decode(cbor_codec.encode(obj)), obj)
        self.assertEqual(cbor_codec.encode({"b": 1, "a": 2}), bytes.fromhex("a2616102616201"))  # keys sorted
        self.assertEqual(cbor_codec.encode(1.5), bytes.fromhex("f93e00"))  # shortest float


if __name__ == "__main__":
    unittest.main()
