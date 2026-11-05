import json
import unittest
from pathlib import Path

import aicl
from aicl.agreement import describe, extract_agreements
from aicl.signing import sign_form

ROOT = Path(__file__).resolve().parents[1]
DEMO = json.loads((ROOT / "examples" / "demo_keys.json").read_text(encoding="utf-8"))
KEYS = {"a": DEMO["a"], "b": DEMO["b"]}
PRIV = {"a": DEMO["_private_a"], "b": DEMO["_private_b"]}
KNOWN = ("meeting", "busy")

SRC = """
(prop #a.1 @a>@b (meeting :with [@a @b] :at 2026-11-10T15:30+09:00 :dur PT30M))
(rej  #b.1 @b>@a ^a.1 :why (busy @b :from 2026-11-10T14:00+09:00 :to 2026-11-10T15:30+09:00))
(prop #a.2 @a>@b (meeting :with [@a @b] :at 2026-11-10T16:00+09:00 :dur PT30M))
(acc  #b.2 @b>@a ^a.2)
(end  #a.3 @a>@b)
"""


def signed_messages(src=SRC):
    out = []
    for m in aicl.parse_messages(src):
        out.append(aicl.Message.from_form(sign_form(m.to_form(), PRIV[m.sender])))
    return out


class AgreementTests(unittest.TestCase):
    def test_extracts_the_accepted_proposal_only(self):
        ags = extract_agreements(aicl.parse_messages(SRC), known_terms=KNOWN)
        self.assertEqual(len(ags), 1)
        ag = ags[0]
        self.assertEqual((ag.proposal.id, ag.acceptance.id), ("a.2", "b.2"))
        self.assertEqual(ag.parties, ("a", "b"))
        self.assertEqual(aicl.to_text(ag.terms), "(meeting :at 2026-11-10T16:00+09:00 :dur PT30M :with [@a @b])")
        self.assertTrue(ag.digest.startswith("sha256:"))
        self.assertFalse(ag.verified)                      # no keys: unverified
        self.assertIn(":verified false", describe(ags))

    def test_verified_when_both_sign(self):
        ags = extract_agreements(signed_messages(), keys=KEYS, known_terms=KNOWN)
        self.assertEqual(ags[0].signed, {"a": True, "b": True})
        self.assertTrue(ags[0].verified)
        self.assertIn("{@a true @b true}", describe(ags))

    def test_tampering_breaks_verification_but_reencoding_does_not(self):
        msgs = signed_messages()
        text = "\n".join(aicl.to_text(m.to_form()) for m in msgs)
        tampered = aicl.parse_messages(text.replace("16:00+09:00 :dur PT30M :with", "16:30+09:00 :dur PT30M :with"))
        ag = extract_agreements(tampered, keys=KEYS, known_terms=KNOWN)[0]
        self.assertEqual(ag.signed["a"], False)            # the proposal was altered after signing
        self.assertFalse(ag.verified)
        # dense -> readable and JSON round trips keep the signatures valid
        dense = "\n".join(aicl.to_dense(m.to_form()) for m in msgs)
        again = [aicl.Message.from_form(t) for t in aicl.from_dense(dense)]
        self.assertTrue(extract_agreements(again, keys=KEYS, known_terms=KNOWN)[0].verified)
        via_json = [aicl.Message.from_form(aicl.from_json_text(aicl.to_json_text(m.to_form()))) for m in msgs]
        self.assertTrue(extract_agreements(via_json, keys=KEYS, known_terms=KNOWN)[0].verified)

    def test_retracted_acceptance_is_not_an_agreement(self):
        src = SRC.replace("(end  #a.3 @a>@b)", "(retract #b.3 @b>@a ^b.2 :why (busy @b)) (end #a.3 @a>@b)")
        ag = extract_agreements(signed_messages(src), keys=KEYS, known_terms=KNOWN)[0]
        self.assertEqual(ag.retracted_by, "b.3")
        self.assertFalse(ag.verified)
        self.assertIn(":retracted-by (ref #b.3)", describe([ag]))

    def test_unsigned_party_is_unknown_not_false(self):
        msgs = [m if m.sender == "a" else aicl.Message.from_form(sign_form(m.to_form(), PRIV["b"]))
                for m in aicl.parse_messages(SRC)]
        ag = extract_agreements(msgs, keys=KEYS, known_terms=KNOWN)[0]
        self.assertEqual(ag.signed, {"a": False, "b": True})   # a has a key but did not sign: not verified
        self.assertFalse(ag.verified)

    def test_example_19_browser_relay_verifies(self):
        keys = {k: v for k, v in json.loads((ROOT / "examples" / "19_keys.json").read_text(encoding="utf-8")).items()
                if not k.startswith("_")}
        msgs = aicl.parse_messages((ROOT / "examples" / "19_browser_relay_agreement.aicl").read_text(encoding="utf-8"))
        ags = extract_agreements(msgs, keys=keys, known_terms=KNOWN)
        self.assertEqual(len(ags), 1)
        self.assertTrue(ags[0].verified)
        self.assertEqual((ags[0].proposal.id, ags[0].acceptance.id), ("a.2", "b.2"))

    def test_example_17_live_run_verifies(self):
        keys = {k: v for k, v in json.loads((ROOT / "examples" / "17_keys.json").read_text(encoding="utf-8")).items()
                if not k.startswith("_")}
        msgs = aicl.parse_messages((ROOT / "examples" / "17_signed_agreement.aicl").read_text(encoding="utf-8"))
        ags = extract_agreements(msgs, keys=keys, known_terms=KNOWN)
        self.assertEqual(len(ags), 1)
        self.assertTrue(ags[0].verified)
        self.assertEqual(ags[0].parties, ("a", "b"))
        self.assertIn(":at 2026-11-12T10:30+09:00", aicl.to_text(ags[0].terms))


if __name__ == "__main__":
    unittest.main()
