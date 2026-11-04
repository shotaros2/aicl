import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aicl
from aicl.codebook import Codebook
from aicl.dialogue import AiclAgent, Clock, DialogueResult, run_dialogue

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))


def scripted(*replies):
    """An ask(system, history) function that plays back canned replies."""
    it = iter(replies)

    def ask(system, history):
        return next(it)
    return ask


def agent(name, *replies):
    return AiclAgent(name, scripted(*replies), system=f"you are @{name}")


class RunDialogueTests(unittest.TestCase):
    def test_clean_exchange_ends_on_end(self):
        a = agent("a", "(ask #a.1 @a>@b (temp tokyo $t))", "(end #a.2 @a>@b)")
        b = agent("b", '(tell #b.1 @b>@a ^a.1 {$t 18.5C} :src jma)')
        r = run_dialogue({"a": a, "b": b}, "a", known_terms=("temp",), echo=None)
        self.assertEqual([m.act for m in r.messages], ["ask", "tell", "end"])
        self.assertTrue(r.ok, [str(i) for i in r.issues] + r.notes)
        self.assertEqual(r.wire, [aicl.to_text(m.to_form()) for m in r.messages])

    def test_invalid_message_is_bounced_once_then_accepted(self):
        a = agent("a", "this is not AICL", "(ask #a.1 @a>@b (temp tokyo $t))", "(end #a.2 @a>@b)")
        b = agent("b", "(tell #b.1 @b>@a ^a.1 {$t 18.5C} :src jma)")
        r = run_dialogue({"a": a, "b": b}, "a", known_terms=("temp",), echo=None)
        self.assertEqual(len(r.messages), 3)
        self.assertEqual(len(r.notes), 1)
        self.assertIn("harness", a.history[2]["content"])     # the bounce named the error
        self.assertFalse(r.ok)                                # a retry is on the record

    def test_abort_after_retries_exhausted(self):
        a = agent("a", "nope", "still nope")
        b = agent("b")
        r = run_dialogue({"a": a, "b": b}, "a", echo=None)
        self.assertEqual(r.messages, [])
        self.assertIn("aborted", r.notes[-1])

    def test_clock_is_injected_and_advances(self):
        a = agent("a", "(ask #a.1 @a>@b (temp tokyo $t))", "(end #a.2 @a>@b)")
        b = agent("b", "(tell #b.1 @b>@a ^a.1 {$t 18.5C} :src jma)")
        clock = Clock(datetime(2026, 11, 4, 10, 0, tzinfo=JST), timedelta(minutes=4))
        run_dialogue({"a": a, "b": b}, "a", known_terms=("temp",), clock=clock, echo=None)
        self.assertTrue(a.history[0]["content"].startswith("; now 2026-11-04T10:00+09:00"))
        self.assertTrue(b.history[0]["content"].startswith("; now 2026-11-04T10:04+09:00"))

    def test_codebook_wire_is_unpacked_and_checked(self):
        cb = Codebook.load(str(ROOT / "codebooks" / "scheduling.json"))
        a = agent("a", "(P a.1>b (Meeting :With [@a @b] :Dur PT30M))", "(end #a.2 @a>@b)")
        b = agent("b", "(C b.1>a ^a.1)")
        r = run_dialogue({"a": a, "b": b}, "a", known_terms=list(cb.concepts), codebook=cb, echo=None)
        self.assertEqual(aicl.to_text(r.messages[0].to_form()),
                         "(prop #a.1 @a>@b (meeting :dur PT30M :with [@a @b]))")
        self.assertTrue(r.ok, [str(i) for i in r.issues] + r.notes)
        # an abbreviation outside the codebook is recorded as a rule-3 violation
        a2 = agent("a", "(P a.1>b (Mtg :With [@a @b]))", "(end #a.2 @a>@b)")
        b2 = agent("b", "(C b.1>a ^a.1)")
        r2 = run_dialogue({"a": a2, "b": b2}, "a", known_terms=list(cb.concepts), codebook=cb, echo=None)
        self.assertFalse(any("rule-3" in n for n in r2.notes))   # Mtg lexes fine, just unresolved vocabulary
        self.assertIn("unresolved-term", [i.code for i in r2.issues])

    def test_save_writes_canonical_and_wire(self):
        import tempfile
        a = agent("a", "(A a.1>b (temp tokyo $t))", "(end #a.2 @a>@b)")
        b = agent("b", "(tell #b.1 @b>@a ^a.1 {$t 18.5C} :src jma)")
        r = run_dialogue({"a": a, "b": b}, "a", known_terms=("temp",), echo=None)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "t.aicl"
            r.save(out)
            self.assertEqual(aicl.to_text(aicl.parse(out.read_text(encoding="utf-8"))[0]),
                             "(ask #a.1 @a>@b (temp tokyo $t))")
            self.assertTrue((Path(d) / "t.aicl.wire.txt").exists())   # dense wire differs from canonical


if __name__ == "__main__":
    unittest.main()
