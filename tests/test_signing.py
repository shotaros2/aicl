import json
import unittest
from pathlib import Path

import aicl
from aicl import dense, json_codec
from aicl.model import Message
from aicl.validate import validate_conversation

try:
    from aicl.signing import generate_key, load_keys, payload, sig_of, sign_form, verify_form
    HAVE_CRYPTO = True
    try:
        generate_key()
    except Exception:
        HAVE_CRYPTO = False
except Exception:                                    # pragma: no cover
    HAVE_CRYPTO = False

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "14_signed_identity.aicl"
DEMO = json.loads((ROOT / "examples" / "demo_keys.json").read_text(encoding="utf-8"))


def codes(issues, level=None):
    return sorted(i.code for i in issues if level is None or i.level == level)


@unittest.skipUnless(HAVE_CRYPTO, "pip install aicl-lang[crypto]")
class SigningTests(unittest.TestCase):
    def test_sign_verify_and_payload_excludes_sig(self):
        priv, pub = generate_key()
        t = aicl.parse_one("(tell #b.1 @b>@a ^a.1 {$t 18.5C} :src jma)")
        signed = sign_form(t, priv)
        self.assertIsNotNone(sig_of(signed))
        self.assertTrue(verify_form(signed, pub))
        self.assertEqual(payload(signed), payload(t))          # :sig itself is not signed
        _, other = generate_key()
        self.assertFalse(verify_form(signed, other))

    def test_signature_survives_reencoding_and_breaks_on_change(self):
        priv, pub = generate_key()
        signed = sign_form(aicl.parse_one("(ask #a.1 @a>@b (temp tokyo $t :unit C))"), priv)
        via_dense = dense.from_dense(dense.to_dense(signed))[0]
        via_json = json_codec.loads(json_codec.dumps(signed))
        self.assertTrue(verify_form(via_dense, pub))
        self.assertTrue(verify_form(via_json, pub))
        tampered = aicl.parse_one(aicl.to_text(signed).replace("tokyo", "osaka"))
        self.assertFalse(verify_form(tampered, pub))

    def test_example_14_verifies_and_regenerates_byte_identical(self):
        keys = load_keys(str(ROOT / "examples" / "demo_keys.json"))
        msgs = aicl.parse_messages(EXAMPLE.read_text(encoding="utf-8"))
        issues = validate_conversation(msgs, ["temp"], keys=keys)
        self.assertEqual([str(i) for i in issues], [])
        # Ed25519 is deterministic: re-signing the bare messages reproduces the file exactly.
        priv = {"a": DEMO["_private_a"], "b": DEMO["_private_b"]}
        for m in msgs:
            bare = m.to_form()
            del bare.kw["sig"]
            self.assertEqual(aicl.to_text(sign_form(bare, priv[m.sender])), aicl.to_text(m.to_form()))

    def test_validator_flags_missing_invalid_and_unknown(self):
        keys = load_keys(str(ROOT / "examples" / "demo_keys.json"))
        text = EXAMPLE.read_text(encoding="utf-8")
        tampered = aicl.parse_messages(text.replace("18.5C", "99.9C"))
        self.assertIn("sig-invalid", codes(validate_conversation(tampered, ["temp"], keys=keys), "error"))
        unsigned = aicl.parse_messages("(ask #a.1 @a>@b (temp tokyo $t))")
        self.assertIn("sig-missing", codes(validate_conversation(unsigned, ["temp"], keys=keys), "error"))
        stranger = aicl.parse_messages("(ask #c.1 @c>@b (temp tokyo $t))")
        self.assertIn("sig-no-key", codes(validate_conversation(stranger, ["temp"], keys=keys), "warning"))

    def test_dialogue_harness_can_sign(self):
        from aicl.dialogue import AiclAgent, run_dialogue
        priv_a, pub_a = generate_key()
        a = AiclAgent("a", lambda s, h: {1: "(ask #a.1 @a>@b (temp tokyo $t))",
                                         2: "(end #a.2 @a>@b)"}[(len(h) + 1) // 2], "sys")
        b = AiclAgent("b", lambda s, h: "(tell #b.1 @b>@a ^a.1 {$t 18.5C} :src jma)", "sys")
        r = run_dialogue({"a": a, "b": b}, "a", known_terms=("temp",), echo=None,
                         signers={"a": priv_a})
        self.assertTrue(verify_form(r.messages[0].to_form(), pub_a))
        self.assertIsNone(sig_of(r.messages[1].to_form()))     # @b has no signer
        issues = validate_conversation(r.messages, ["temp"], keys={"a": pub_a})
        self.assertEqual(codes(issues, "error"), [])
